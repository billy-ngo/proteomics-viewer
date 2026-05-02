"""Parse MaxQuant proteinGroups.txt — and many MaxQuant-like variants —
into structured data for the frontend.

Robustness goals:
- Tolerate non-standard identity columns (e.g. ``Combined_locus_tag`` from
  custom pipelines) by falling back when ``Protein IDs`` / ``Majority protein
  IDs`` / ``Fasta headers`` are absent.
- Tolerate missing peptide-count columns by setting a sensible default
  (``peptides=1`` for every detected protein) so downstream filters do not
  drop everything.
- Distinguish per-sample quant columns (``Intensity Sample1``) from
  per-group aggregate columns (``Intensity GroupName`` where GroupName
  is also a prefix of one or more sample names) and exclude the latter
  from the sample list.
- Keep a quant type even if it is missing for a few samples — pad with
  zeros instead of dropping the entire type.
"""

import csv
import math
import re
from collections import defaultdict

# Per-sample column prefixes in MaxQuant proteinGroups.txt
QUANT_PREFIXES = [
    "MS/MS count",
    "LFQ intensity",
    "Intensity",
    "iBAQ",
    "Razor + unique peptides",
    "Unique peptides",
    "Peptides",
]

# Prefixes that have [%] after sample name
PCT_PREFIXES = [
    "Sequence coverage",
]

# Identity columns to try, in priority order
ID_COLUMNS = [
    "Protein IDs", "Majority protein IDs", "Combined_locus_tag",
    "Locus tag", "Locus", "Accession", "Protein ID", "ID", "id",
]

GENE_NAME_COLUMNS = [
    "Gene names", "Gene name", "Gene", "Symbol", "Protein name", "Protein names",
]


def _float(val):
    """Parse a cell as float. NaN, +/-Inf, and parse failures all collapse to 0.0
    so downstream JSON serialisation (Starlette rejects non-finite floats) and
    plotting (D3 scales blow up on Inf) stay safe."""
    try:
        f = float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0
    return f if math.isfinite(f) else 0.0


def _int(val):
    """Parse a cell as int. Inf via overflow path is also coerced to 0."""
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def _extract_gene_name(fasta_header):
    """Extract a short display name from the fasta header."""
    if not fasta_header:
        return ""
    first = fasta_header.split(";")[0].strip()
    parts = first.split(None, 1)
    if len(parts) > 1:
        return parts[1]
    return first


def _detect_samples(headers):
    """Detect sample names from per-sample quant column headers."""
    samples = set()
    for header in headers:
        for prefix in QUANT_PREFIXES:
            if header.startswith(prefix + " "):
                sample = header[len(prefix) + 1:]
                if sample and not sample.startswith("[") and not sample.startswith("("):
                    samples.add(sample)
    return sorted(samples)


def _filter_aggregate_samples(samples):
    """Drop names that look like per-group aggregates rather than per-sample.

    Heuristic: ``S`` is an aggregate if some other detected name ``S2`` starts
    with ``S`` followed by a separator ([space, underscore, hyphen, digit]) —
    e.g. drop ``"Se"`` when ``"Se M1"``, ``"Se M2"`` exist; drop ``"TM7x"``
    when ``"TM7x A1"`` exists. Returns (kept, aggregates).
    """
    aggregates = set()
    for s in samples:
        for s2 in samples:
            if s2 == s:
                continue
            if s2.startswith(s) and len(s2) > len(s):
                next_ch = s2[len(s)]
                if next_ch in (" ", "_", "-", ".") or next_ch.isdigit():
                    aggregates.add(s)
                    break
    return [s for s in samples if s not in aggregates], sorted(aggregates)


def _detect_quant_columns(headers, samples):
    """Map quantification types to their per-sample columns.

    Keep a quant type if AT LEAST 2 samples have a column for it (was: all).
    Missing samples are padded with zeros at parse time.
    """
    quant_columns = {}
    for prefix in QUANT_PREFIXES:
        cols = {}
        for sample in samples:
            col_name = f"{prefix} {sample}"
            if col_name in headers:
                cols[sample] = col_name
        if len(cols) >= 2:
            quant_columns[prefix] = cols

    for prefix in PCT_PREFIXES:
        cols = {}
        for sample in samples:
            for pattern in (f"{prefix} {sample} [%]", f"{prefix} {sample}"):
                if pattern in headers:
                    cols[sample] = pattern
                    break
        if len(cols) >= 2:
            quant_columns[f"{prefix} [%]"] = cols

    return quant_columns


def _auto_groups(samples):
    """Auto-detect sample groups by stripping the trailing replicate index.

    Replicate index = an optional separator (space/underscore/hyphen) followed
    by trailing digits. Letters are NOT consumed, so naming conventions that
    encode the condition with a letter prefix (e.g. ``Se M1`` vs ``Se S1``)
    correctly resolve into separate groups:

        "Sample1", "Sample2", "Sample3"               -> "Sample"
        "A1", "A2", "B1", "B2"                        -> "A", "B"
        "Se M1"…"Se M4", "Se S1"…"Se S4"              -> "Se M", "Se S"
        "TM7x A1"…"A4", "TM7x B1"…"B4"                -> "TM7x A", "TM7x B"
        "Ctrl_1"…"Ctrl_3", "Treated_1"…"Treated_3"    -> "Ctrl", "Treated"

    Falls back to leading-letters grouping when stripping yields an empty stem.
    """
    groups = defaultdict(list)
    for sample in samples:
        stem = re.sub(r"[\s_\-]?\d+\s*$", "", sample).rstrip(" _-")
        if not stem:
            m = re.match(r"^([A-Za-z]+)", sample)
            stem = m.group(1) if m else "Ungrouped"
        groups[stem].append(sample)
    return dict(groups)


def _pick_first_present(row, candidates, default=""):
    """Return the first candidate column's value that is non-empty."""
    for c in candidates:
        v = row.get(c, "")
        if v:
            return v
    return default


def _detect_encoding(filepath):
    """Sniff for a BOM at the start of the file. Common case: Excel "Save As
    Tab-delimited Text" emits UTF-16 LE with BOM, which fails to parse as
    UTF-8. Returns the encoding name to pass to ``open()``."""
    try:
        with open(filepath, "rb") as f:
            head = f.read(4)
    except OSError:
        return "utf-8"
    if head[:2] == b"\xff\xfe":
        return "utf-16"        # UTF-16 LE BOM
    if head[:2] == b"\xfe\xff":
        return "utf-16"        # UTF-16 BE BOM
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"     # UTF-8 BOM — strip it transparently
    return "utf-8"


def parse_protein_groups(filepath):
    """Parse a MaxQuant proteinGroups.txt (or variant) and return structured data."""
    csv.field_size_limit(10_000_000)
    encoding = _detect_encoding(filepath)

    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        if not headers:
            raise ValueError("Empty file or unrecognized format")

        header_set = set(headers)

        # Detect samples, then strip per-group aggregate columns
        raw_samples = _detect_samples(headers)
        if not raw_samples:
            raise ValueError(
                "Could not detect sample columns. "
                "Ensure the file has per-sample columns like 'Intensity A1'."
            )
        samples, dropped_aggregates = _filter_aggregate_samples(raw_samples)
        if not samples:
            raise ValueError(
                "Detected only per-group aggregate columns, no per-sample columns. "
                "Make sure your file has per-sample quant columns (e.g. 'Intensity A1')."
            )

        quant_columns = _detect_quant_columns(header_set, samples)
        if not quant_columns:
            raise ValueError("No quantification data columns detected.")

        groups = _auto_groups(samples)

        # Discover the best identity & gene-name columns to use
        id_col = next((c for c in ID_COLUMNS if c in header_set), None)
        majority_col = "Majority protein IDs" if "Majority protein IDs" in header_set else id_col
        gene_col = next((c for c in GENE_NAME_COLUMNS if c in header_set), None)
        fasta_col = "Fasta headers" if "Fasta headers" in header_set else None

        # File-level metadata: which standard columns are present
        has_peptides_col = any(c in header_set for c in
                               ("Peptides", "Razor + unique peptides", "Unique peptides"))
        has_contam_col = "Potential contaminant" in header_set
        has_reverse_col = "Reverse" in header_set
        has_byside_col = "Only identified by site" in header_set

        # Parse all rows
        proteins = []
        quant_data = {qt: {s: [] for s in samples} for qt in quant_columns}
        raw_headers = list(headers)
        raw_rows = []

        contaminant_count = 0
        reverse_count = 0
        only_by_site_count = 0

        for row in reader:
            raw_rows.append([(row.get(h, "") or "") for h in raw_headers])

            is_contaminant = row.get("Potential contaminant", "") == "+"
            is_reverse = row.get("Reverse", "") == "+"
            is_only_by_site = row.get("Only identified by site", "") == "+"

            if is_contaminant:
                contaminant_count += 1
            if is_reverse:
                reverse_count += 1
            if is_only_by_site:
                only_by_site_count += 1

            # Identity — fall back to the first non-empty column we know about
            protein_id = row.get(id_col, "") if id_col else ""
            majority_id = row.get(majority_col, "") if majority_col else protein_id
            if not majority_id:
                majority_id = protein_id
            fasta_header = row.get(fasta_col, "") if fasta_col else ""

            # Gene name: from dedicated column, or from fasta header
            if gene_col:
                gene_name = row.get(gene_col, "") or _extract_gene_name(fasta_header)
            else:
                gene_name = _extract_gene_name(fasta_header)

            # Peptide counts — read what's there; if NO peptide-count column
            # exists at all in the file, default to 1 so downstream filters
            # (e.g. peptides<1) don't drop every protein.
            if has_peptides_col:
                peptides = _int(row.get("Peptides", ""))
                unique_peptides = _int(row.get("Unique peptides", ""))
                razor = _int(row.get("Razor + unique peptides", ""))
            else:
                peptides = 1
                unique_peptides = 0
                razor = 0

            protein = {
                "id": protein_id,
                "majority_id": majority_id,
                "gene_name": gene_name,
                "fasta_header": fasta_header,
                "mol_weight": _float(row.get("Mol. weight [kDa]", "")),
                "sequence_length": _int(row.get("Sequence length", "")),
                "peptides": peptides,
                "unique_peptides": unique_peptides,
                "razor_unique_peptides": razor,
                "sequence_coverage": _float(row.get("Sequence coverage [%]", "")),
                "score": _float(row.get("Score", "")),
                "only_identified_by_site": is_only_by_site,
                "reverse": is_reverse,
                "potential_contaminant": is_contaminant,
                "peptide_sequences": row.get("Peptide sequences", ""),
                # Tag every protein with its source file for multi-file workflows.
                # main.py overwrites this with the user-facing filename.
                "source_file": str(filepath),
            }
            proteins.append(protein)

            # Collect quantification values; missing cols (sample present in
            # `samples` but missing for this quant type) are padded with 0.
            for qt, sample_cols in quant_columns.items():
                for sample in samples:
                    col_name = sample_cols.get(sample)
                    val = _float(row.get(col_name, "0")) if col_name else 0.0
                    quant_data[qt][sample].append(val)

        # If the file had NO id column at all, synthesize one from the row index
        # so the UI has something to display.
        if not id_col:
            for idx, p in enumerate(proteins):
                p["id"] = f"row_{idx + 1}"
                p["majority_id"] = p["majority_id"] or f"row_{idx + 1}"

    return {
        "filename": str(filepath),
        "proteins": proteins,
        "samples": samples,
        "quant_types": list(quant_columns.keys()),
        "quant_data": quant_data,
        "suggested_groups": groups,
        "total_proteins": len(proteins),
        "contaminants": contaminant_count,
        "reverse_hits": reverse_count,
        "only_by_site": only_by_site_count,
        # Provenance / format flags so the frontend can adapt UI/filters
        "format_info": {
            "id_column": id_col,
            "gene_column": gene_col,
            "fasta_column": fasta_col,
            "has_peptide_counts": has_peptides_col,
            "has_contaminant_column": has_contam_col,
            "has_reverse_column": has_reverse_col,
            "has_only_by_site_column": has_byside_col,
            "dropped_aggregate_columns": dropped_aggregates,
        },
        # Original-file preservation for downstream Excel/CSV export
        "raw_headers": raw_headers,
        "raw_rows": raw_rows,
    }
