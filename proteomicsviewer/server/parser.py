"""Parse MaxQuant proteinGroups.txt into structured data for the frontend."""

import csv
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


def _float(val):
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


def _int(val):
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError):
        return 0


def _extract_gene_name(fasta_header):
    """Extract a short display name from the fasta header."""
    if not fasta_header:
        return ""
    # Handle multiple entries separated by ;
    first = fasta_header.split(";")[0].strip()
    # Try to extract after the first space (protein_id description)
    parts = first.split(None, 1)
    if len(parts) > 1:
        return parts[1]
    return first


def _detect_samples(headers):
    """Detect sample names from column headers using Intensity columns."""
    samples = set()
    for header in headers:
        # Try standard quant prefixes
        for prefix in QUANT_PREFIXES:
            if header.startswith(prefix + " "):
                sample = header[len(prefix) + 1:]
                # Skip global columns that aren't per-sample
                if sample and not sample.startswith("[") and not sample.startswith("("):
                    samples.add(sample)
    return sorted(samples)


def _detect_quant_columns(headers, samples):
    """Map quantification types to their per-sample columns."""
    quant_columns = {}

    for prefix in QUANT_PREFIXES:
        cols = {}
        for sample in samples:
            col_name = f"{prefix} {sample}"
            if col_name in headers:
                cols[sample] = col_name
        if cols and len(cols) == len(samples):
            quant_columns[prefix] = cols

    # Also check percentage-based columns
    for prefix in PCT_PREFIXES:
        cols = {}
        for sample in samples:
            for pattern in [f"{prefix} {sample} [%]", f"{prefix} {sample}"]:
                if pattern in headers:
                    cols[sample] = pattern
                    break
        if cols and len(cols) == len(samples):
            quant_columns[f"{prefix} [%]"] = cols

    return quant_columns


def _auto_groups(samples):
    """Auto-detect sample groups from name prefixes."""
    groups = defaultdict(list)
    for sample in samples:
        match = re.match(r"([A-Za-z]+)", sample)
        if match:
            groups[match.group(1)].append(sample)
        else:
            groups["Ungrouped"].append(sample)
    return dict(groups)


def parse_protein_groups(filepath):
    """Parse a MaxQuant proteinGroups.txt file and return structured data."""
    csv.field_size_limit(10_000_000)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        if not headers:
            raise ValueError("Empty file or unrecognized format")

        header_set = set(headers)
        samples = _detect_samples(headers)
        if not samples:
            raise ValueError(
                "Could not detect sample columns. "
                "Ensure the file has per-sample columns like 'Intensity A1'."
            )

        quant_columns = _detect_quant_columns(header_set, samples)
        if not quant_columns:
            raise ValueError("No quantification data columns detected.")

        groups = _auto_groups(samples)

        # Parse all rows
        proteins = []
        quant_data = {qt: {s: [] for s in samples} for qt in quant_columns}

        contaminant_count = 0
        reverse_count = 0
        only_by_site_count = 0

        for row in reader:
            is_contaminant = row.get("Potential contaminant", "") == "+"
            is_reverse = row.get("Reverse", "") == "+"
            is_only_by_site = row.get("Only identified by site", "") == "+"

            if is_contaminant:
                contaminant_count += 1
            if is_reverse:
                reverse_count += 1
            if is_only_by_site:
                only_by_site_count += 1

            protein_id = row.get("Protein IDs", row.get("Majority protein IDs", ""))
            majority_id = row.get("Majority protein IDs", protein_id)
            fasta_header = row.get("Fasta headers", "")

            protein = {
                "id": protein_id,
                "majority_id": majority_id,
                "gene_name": _extract_gene_name(fasta_header),
                "fasta_header": fasta_header,
                "mol_weight": _float(row.get("Mol. weight [kDa]", "")),
                "sequence_length": _int(row.get("Sequence length", "")),
                "peptides": _int(row.get("Peptides", "")),
                "unique_peptides": _int(row.get("Unique peptides", "")),
                "razor_unique_peptides": _int(row.get("Razor + unique peptides", "")),
                "sequence_coverage": _float(row.get("Sequence coverage [%]", "")),
                "score": _float(row.get("Score", "")),
                "only_identified_by_site": is_only_by_site,
                "reverse": is_reverse,
                "potential_contaminant": is_contaminant,
                "peptide_sequences": row.get("Peptide sequences", ""),
            }
            proteins.append(protein)

            # Collect quantification values
            for qt, sample_cols in quant_columns.items():
                for sample, col_name in sample_cols.items():
                    quant_data[qt][sample].append(_float(row.get(col_name, "0")))

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
    }
