# Pro-ker Proteomics Analysis

An interactive, browser-based tool for exploring and visualizing label-free proteomics data from MaxQuant `proteinGroups.txt` files. Designed for working biologists: drag-and-drop a file, assign samples to groups, and build publication-ready volcano plots, PCA plots, and other comparative visualizations without writing code.

Pro-ker runs entirely on your machine — no cloud uploads, no accounts. The frontend is a single HTML page served by a local Python web server; everything you do stays local.

---

## Installation

### Recommended (PyPI)

```bash
pip install proker
```

Requires Python 3.10 or newer and a modern browser (Chrome, Firefox, Safari, or Edge).

### Bundled installers (from the source distribution)

If you cloned the repository or downloaded a release archive:

- **Windows** — Double-click `Install_Windows.bat`
- **macOS** — Double-click `Install_macOS.command` (or run `bash Install_macOS.command`)

Both scripts call `pip install -e .` against the bundled source and then launch the viewer.

### From source

```bash
git clone https://github.com/billy-ngo/proteomics-viewer
cd proteomics-viewer
pip install -e .
```

---

## Quick start

```bash
proker                      # launch the viewer on port 8050; opens your browser
proker data.txt             # launch and auto-load a proteinGroups.txt file
proker --port 9000          # use a custom port
proker --no-browser         # don't open the browser (e.g. running on a remote host)
proker --install            # create a desktop shortcut
proker --update             # check PyPI for an update and install if available
proker --version            # print version and exit
```

The viewer single-instances itself: if you re-run `proker` while it's already running, the existing tab is brought to the front instead of starting a duplicate. Closing all browser tabs that point at the viewer triggers an automatic shutdown after 30 seconds.

---

## How it works

The intended workflow:

1. **Upload** — Drag a `proteinGroups.txt` file (or several) onto the page, or click to browse. The parser detects per-sample columns automatically and shows a yellow note if it had to make any adaptations.
2. **Group** — Drag sample chips into named groups (or accept the auto-detected grouping based on shared name prefixes). At least two non-empty groups are required to enable analysis.
3. **Process** — Choose a quantification type (Intensity, LFQ, iBAQ, etc.), optionally normalize across samples or within an organism, prune by peptide threshold, and decide what to do with missing values.
4. **Analyse** — Define pairwise comparisons (Group X vs Group Y) or build derived groups by combining existing groups arithmetically. Optionally add Groups of Interest (highlighted protein ranges) or Species Highlights.
5. **Visualize** — Drag plot tiles from the palette onto the canvas. Each plot inherits the current processing settings; freeze a plot to lock its data while you keep changing things upstream.
6. **Export** — Save individual plots or the whole canvas as SVG (vector) or PNG (raster), export per-plot data as Prism-ready CSV, or export the full analysis as XLSX.

A guided tour (Help button, top-right) walks through this flow on first launch.

---

## Visualizations

| Plot | What it shows | Typical use |
|---|---|---|
| **Volcano** | log2 fold-change (X) vs −log10 FDR-adjusted p-value (Y) for two groups | Differential abundance — top corners are your hits |
| **Ranked enrichment** | Every protein plotted by log2 fold-change, sorted ascending | Quick scan of strongest up/down candidates |
| **Unique proteins** | Proteins detected in one group but absent in another | IP / co-IP enrichment, presence-only hits |
| **Dot plot** | Mean abundance in group X vs group Y, log-scaled | Visual sanity check; off-diagonal = differential |
| **PCA** | Each point is a sample, projected onto the two largest variance axes | Batch effects, outlier detection, group separation |
| **Protein abundance** | All proteins in a group or sample, ranked from most to least abundant | Dynamic-range overview, error bars (SD/SEM/range) |
| **Peptide coverage map** | Identified peptides aligned to a FASTA sequence, residue-by-residue | Coverage QC, mapping PTM sites |

All plots respect the global processing pipeline, so a change to normalization or pruning instantly re-renders every plot on the canvas (unless frozen).

---

## Statistical methods

### Statistical test (volcano plot)

The volcano plot's **Statistical test** dropdown offers three peer-reviewed methods. All three accept the optional S0 fudge factor and feed into the same Benjamini–Hochberg FDR correction.

#### Welch's t-test (default)

Two-sample, unequal-variance t-test comparing group means:

```
t  = (mean_X − mean_Y) / (SE + S0)
SE = sqrt(var_X / n_X + var_Y / n_Y)
df = (var_X/n_X + var_Y/n_Y)² / ((var_X/n_X)²/(n_X−1) + (var_Y/n_Y)²/(n_Y−1))
```

P-values are computed from the regularized incomplete beta function. The test runs only if both groups have ≥ 2 replicates; with only one replicate per group, the volcano plot still renders fold-change but reports p = 1 for every protein. This is the standard textbook choice and matches `scipy.stats.ttest_ind(equal_var=False)` and R's `t.test(var.equal=FALSE)`.

#### Moderated t-test (limma)

Empirical-Bayes shrinkage of per-protein variance toward a fitted prior (Smyth 2004). Each protein's posterior variance becomes:

```
s²_post = (d₀ · s²₀ + d_g · s²_g) / (d₀ + d_g)
t_mod   = (mean_X − mean_Y) / sqrt(s²_post · (1/n_X + 1/n_Y))
df_mod  = d_g + d₀
```

The hyperparameters d₀ (prior degrees of freedom) and s²₀ (prior variance) are estimated from the empirical distribution of per-protein log-variances using the digamma/trigamma method-of-moments identities:

```
trigamma(d₀/2) = empirical_var(log s²_g) − trigamma(d_g/2)
log(s²₀)       = empirical_mean(log s²_g) + digamma(d₀/2) − log(d₀/2)
```

The pure-JS implementation matches limma's `squeezeVar` to within 5% on standard test data (digamma/trigamma agree with R's `psigamma` to 1e-6, and a 1000-protein simulation with true d₀=4, s₀²=2 recovers d₀=3.95, s₀²=2.05). Recommended for studies with few replicates per group (≤5), which is most proteomics studies.

#### Peptide-count moderated (DEqMS)

DEqMS extends limma by replacing the single global prior with a per-protein prior that depends on peptide count (Zhu et al. 2020). Pro-ker's implementation:

1. Bins proteins by `floor(log₂(peptide_count))` — typically 4–6 bins for a normal MaxQuant file.
2. For each bin, computes the median log-variance → that bin's prior variance.
3. Empty bins inherit from the nearest non-empty neighbour; the global median is used as a final fallback.
4. Estimates a single shared d₀ from the residual log-variance after the binned smoother (so d₀ reflects within-bin scatter, not total scatter).
5. Each protein's moderated variance uses the prior corresponding to its own peptide count.

This explicitly captures the well-documented fact that proteins quantified from many peptides have inherently lower measurement variance than proteins quantified from one or two peptides. **Falls back to limma automatically if the file has no peptide-count column** (the dropdown option is also disabled in that case).

**Choosing a test.** Welch is the appropriate default for any dataset with adequate replication. limma is the recommended improvement when N ≤ 5 per group ([Smyth 2004](https://www.statsci.org/smyth/pubs/ebayes.pdf), [Goeminne et al. 2018, *Brief. Bioinform.*](https://academic.oup.com/bib/article/19/5/971/3079005)) and is what most modern proteomics analysis pipelines (DEP, prolfqua, MSstats) default to. DEqMS is recommended when peptide counts vary substantially across proteins — common in label-free DDA datasets ([Zhu et al. 2020 *MCP*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7261819/)).

### Benjamini–Hochberg FDR correction

Raw p-values from the volcano test are adjusted for multiple testing using the Benjamini–Hochberg procedure to control the false discovery rate. P-values are sorted in ascending order, scaled by `n / rank`, and capped from largest rank downward to enforce monotonicity. A protein is called significant only if its FDR-adjusted p-value falls below the user-set FDR threshold (default 0.05) **and** its |log2 FC| meets the fold-change threshold (default 1.0).

### S0 low-abundance correction

The optional S0 parameter (Tusher et al., 2001; used by Perseus/SAM) is a small constant added to the t-test denominator to penalize fold changes driven by low-abundance noise:

```
t_S0 = |mean_X − mean_Y| / (SE + S0)
```

- At **S0 = 0** (default), this reduces to a standard Welch's t-test.
- At **S0 > 0**, low-abundance proteins (with small SE) require larger absolute differences to reach significance. Typical values: 0.1 (Perseus default) to 2.0.

### Missing-value imputation (volcano plot)

Seven published methods are available, covering the four families established in the [NAguideR proteomics benchmark](https://academic.oup.com/nar/article/48/14/e83/5856122) (MNAR-aware single-distribution, MCAR-aware local-similarity, tree-based ensemble, and constant-value baseline). Each is selectable from a dropdown in the volcano configuration:

| Method | Family | Approach | Reference |
|---|---|---|---|
| **Perseus** (default) | MNAR | Draws each missing value from a down-shifted Gaussian in log2 space (shift = 1.8 SD, width = 0.3 SD), using the comparison's non-zero values to estimate µ/σ. | [Tyanova et al. (2016) *Nat. Protoc.* 11:2301](https://www.nature.com/articles/nprot.2016.136) |
| **MinProb** | MNAR | Per-sample MinDet: computes the smallest observed log2 value in each sample, then draws from N(MinDet_sample, σ_sample). Sample-specific. | [Lazar et al. (2016) *J. Proteome Res.* 15:1116](https://pubs.acs.org/doi/10.1021/acs.jproteome.5b00981) |
| **QRILC** | MNAR | Draws from a Gaussian centred at the 1st percentile of the comparison's global log2 distribution. Single global tail. | [Wei et al. (2018) *Sci. Rep.* 8:663](https://www.nature.com/articles/s41598-017-19120-0) |
| **kNN** | MCAR | Inverse-distance-weighted mean of the k = 10 nearest-neighbour proteins (Euclidean distance on shared observed positions). | [Troyanskaya et al. (2001) *Bioinformatics* 17:520](https://academic.oup.com/bioinformatics/article/17/6/520/272365) |
| **LLS** | MCAR | Linear regression of the target on its k = 10 most similar proteins (with small ridge for stability), in log2 space. Often outperforms kNN at high dimensionality. | [Kim et al. (2005) *Bioinformatics* 21:187](https://academic.oup.com/bioinformatics/article/21/2/187/204994) |
| **Random Forest** (MissForest) | Ensemble | Iterative non-linear regression. For each sample column with missing values, trains a random forest on the other samples (50 trees, depth 6, m_try = √p); iterates until relative-change tolerance (0.01) or max 5 iterations. Top-ranked across multiple proteomics benchmarks. | [Stekhoven & Bühlmann (2012) *Bioinformatics* 28:112](https://academic.oup.com/bioinformatics/article/28/1/112/219101) |
| **Min/2** | Baseline | Replaces missing values with half the per-protein minimum non-zero value. Simple deterministic baseline; produces "bifurcate" volcano patterns at high missingness. Included only as a sanity check. | — |

**Choosing a method.** Modern proteomics benchmarks ([NAguideR 2020](https://academic.oup.com/nar/article/48/14/e83/5856122), [Jin et al. *Sci. Rep.* 2021](https://www.nature.com/articles/s41598-021-81279-4), [2024 IJMS comprehensive evaluation](https://www.mdpi.com/1422-0067/25/24/13491)) consistently identify Random Forest, LLS, and BPCA as top performers when missingness is mostly MCAR; Perseus and MinProb are appropriate when missingness is mostly MNAR (i.e. driven by detection-limit dropout). [Lazar et al. 2016](https://pubs.acs.org/doi/10.1021/acs.jproteome.5b00981) explicitly recommends classifying each protein's missingness pattern and applying a method tuned to it. Pro-ker exposes both families so you can test sensitivity to this choice.

**Reproducibility.** All four stochastic methods (Perseus, MinProb, QRILC, MissForest) consume a seed and produce bit-identical output for the same seed + same data:

- *Per-protein methods* (Perseus, MinProb, QRILC) derive a per-protein PRNG seed from the user-supplied **Random seed** (default 42) and the protein's filtered index: `(seed · 1000003 + 2·fi + {1,2}) mod 2³²`.
- *Matrix-wide MissForest* uses the global seed once for bootstrap and feature subsampling across the entire forest construction (a single forest is built per sample column, reused for every protein in the column).
- *Deterministic methods* (kNN, LLS, Min/2) ignore the seed.

Change the seed to verify a conclusion is robust to the specific draws — a result that depends on a single seed is not robust. The seed is recorded on the *Volcano Settings* sheet of the XLSX export so any analysis is fully reproducible from the saved file alone.

**Presence-only proteins (when imputation is OFF).** Proteins detected in only one of the two groups would have ±∞ fold-change. Rather than discard them, the volcano plot adds two narrow side bands (one on each side of the main cloud, separated by an axis break) to display these presence-only proteins. Their hover tooltip clearly labels them as one-sided detections.

### Principal Component Analysis

Pro-ker uses dual-space PCA (the "kernel trick"), which is well-suited to proteomics datasets where the number of samples (n) is much smaller than the number of proteins (m):

1. **Mean-center** each protein's intensity vector across samples.
2. **Compute the n × n kernel matrix** K = X · X^T (instead of the much larger m × m covariance matrix).
3. **Jacobi eigendecomposition** of K extracts eigenvalues and eigenvectors.
4. **Project**: PC scores = eigenvectors scaled by √eigenvalue.

Variance explained is reported as a percentage of total variance for each component, shown in the axis labels. Configurable options include data source (raw vs processed), transform (none, log2, log10, or arcsinh), scaling (mean-centering, unit variance, Pareto), missing-value handling, and which two PCs to display.

Confidence ellipses can be overlaid on PCA plots; they use the chi² critical value at the user's confidence level (default 95 %) and have `pointer-events: none` so they don't block tooltips for points inside them.

---

## Configuration reference

| Parameter | Plot | Default | Description |
|---|---|---|---|
| Statistical test | Volcano | Welch | Welch / limma (moderated) / DEqMS (peptide-count moderated) |
| FDR threshold | Volcano | 0.05 | Significance cutoff for BH-adjusted p-values |
| \|log2 FC\| threshold | Volcano | 1.0 | Minimum absolute fold change for significance |
| S0 | Volcano | 0 | Low-abundance correction (0 = no dampening) — layered on top of any test |
| Imputation method | Volcano | Perseus | Perseus / MinProb / QRILC / kNN / LLS / Random Forest / Min/2 |
| Random seed | Volcano | 42 | Seed for stochastic imputation; reported in exports |
| Threshold lines | Volcano | On | Toggle dotted FC and FDR reference lines (Graph Settings) |
| PCs to display | PCA | 1 vs 2 | Any two principal components |
| Transform | PCA | log2(x+1) | none / log2 / log10 / arcsinh |
| Scaling | PCA | center | center / unit / Pareto |
| Confidence ellipse | PCA | 95 % | Overlay per-group ellipse at chi² critical level |
| Error bars | Abundance | none | none / SD / SEM / range |

---

## Multi-file workflows

Pro-ker supports loading multiple `proteinGroups.txt` files in a single session — useful when you want to compare results from independent experiments side-by-side.

- **Append** (recommended for cross-experiment comparison) — Adds the new file's proteins and samples to the current dataset. Existing samples are zero-padded for new proteins; new samples are zero-padded for existing proteins. Each protein is tagged with its source file.
- **Replace** — Discards the current dataset entirely.

Cross-file analyses are guarded: a volcano (or any other comparison) between two groups whose samples come from different files is rejected with a clear error, because the proteins in one file may not be present in the other (and the zero-padding would corrupt the comparison). Plots can optionally be restricted to a single source file via their config.

If a file appears to overlap completely with already-loaded data (every sample name already exists), the merge is refused with a clear "looks like a re-upload" message rather than silently corrupting the dataset.

---

## Sessions

Use the **Save Session** button (top-right) to download a JSON file containing your full analysis state: data, groups, processing settings, analyses, derived groups, Groups of Interest, species highlights, every plot on the canvas with its position / size / freeze state / color overrides / pinned annotations, and any text boxes, lines, or shapes you've added.

Saved sessions are **fully self-contained** — the parsed data is embedded — so they reload without needing the original `proteinGroups.txt` file. Loading a session into a clean instance of Pro-ker reproduces the exact same view.

A lightweight version is also auto-saved to your browser's `localStorage` after every edit, and offered as **Restore last session** on next launch. The auto-save excludes the bulky raw-row copies (which can exceed `localStorage`'s 5 MB quota); the file-based save is what you should rely on for reproducibility.

---

## Export

### Per-plot

Right-click any plot on the canvas → **Export data**. Produces a CSV with one row per data point, ready to paste into GraphPad Prism (XY or Column tables) or any other graphing software. The export re-runs the same computation the plot uses, so what you see is what you get.

### Whole-analysis (XLSX)

The **Export Analysis as XLSX** button (Analysis tab) produces a multi-sheet workbook containing:

- **Metadata** — software version, source files, protein counts
- **Processing settings** — quant type, normalization, pruning parameters
- **Sample groups** — group assignments and derived-group definitions
- **Raw data** — pre-processing quant values per sample
- **Processed data** — post-filtering / normalization values, with group means
- **Volcano statistics** — per-protein log2FC, raw p, FDR-adjusted p, significance call, and the imputation seed for every volcano plot on the canvas
- **PCA scores** — PC1/PC2 coordinates per sample with variance explained, for every PCA plot on the canvas

Cell values longer than the 32 767-character XLSX limit are clipped and flagged with a `…[clipped]` suffix so the file always opens cleanly.

### Canvas (figures)

Use the **Export** button (top-right) to render the full canvas:

- **SVG** — Fully vectorized, every text element preserved as text, editable in Illustrator / Inkscape / Figma. Best for figures.
- **PNG** — Raster at 2× scale. Best for slides, posters, and quick previews.

You can choose to export each plot separately (stacked vertically) or the canvas exactly as displayed (preserving plot positions, text boxes, lines, and shapes).

---

## Robustness

A few things designed to keep you out of trouble:

- **Per-plot error isolation.** If a single plot fails to render (bad config, edge data), the others still render and the broken plot shows an in-place error message you can read. The whole canvas never goes dark from one bad plot.
- **Visible error toast.** Uncaught JS errors and async rejections surface as a dismissable red toast in the bottom-right with the actual error message, instead of failing silently.
- **Upload state-rollback.** A failed file load can never leave Pro-ker with a half-loaded dataset; the previous state is restored.
- **Format-info banner.** When the parser had to make adaptations (e.g. dropped per-group aggregate columns, no peptide-count column, no contaminant column), a yellow banner at the top of the grouping section explains what happened so you're never surprised by missing functionality.
- **Emergency reset.** If anything ever does become unrecoverable, type `window.__reset()` in your browser's developer console (F12). It clears state, drops the auto-save, and reloads.

---

## Troubleshooting

**The browser doesn't open** — Pro-ker waits for the `/health` endpoint to be ready (up to 10 s). If the browser still doesn't open, navigate to `http://localhost:8050` (or your `--port`) manually.

**"Address already in use"** — Pro-ker single-instances itself, but if it crashed leaving a stale lock file, delete `~/.proker/server.lock` and try again. Or just use a different `--port`.

**A plot shows "Plot render error"** — One plot's data or config is incompatible. The other plots are fine. Click the × on the broken plot, or open its settings (double-click) and adjust.

**"This file appears to overlap entirely…"** — You're trying to append a file whose every sample name already exists in the current dataset. Pro-ker refuses because appending it would corrupt the row alignment. If you meant to replace, use the file-conflict modal's **Replace** button instead.

**The contaminant filter is greyed out** — Your file doesn't have a `Potential contaminant` column. Pro-ker disables filters that depend on absent columns rather than letting them silently no-op.

**An error toast keeps appearing** — Something is going wrong on every render. Open the console (F12), copy the error, and report it. As a recovery: `window.__reset()`.

---

## File format support

Pro-ker is built around MaxQuant `proteinGroups.txt` (tab-separated) but tolerates many real-world variations:

- Standard MaxQuant output (any version)
- Files with custom identity columns (`Combined_locus_tag` etc.) instead of `Protein IDs`
- Files missing peptide-count, contaminant, reverse, or by-site columns (filters that depend on those columns are disabled with an explanation)
- Files with per-group aggregate columns alongside per-sample columns (aggregates are detected and dropped)
- UTF-8, UTF-8 + BOM, UTF-16 LE/BE + BOM, and Latin-1 encodings
- CRLF, LF, or CR-only line endings
- Cell values containing `NaN`, `Inf`, or `-Inf` (collapsed to 0)

Empty files, files with no per-sample quant columns, and files with only one sample are rejected with informative error messages.

---

## References

### Statistical methods
- Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *J. R. Stat. Soc. B*, 57(1), 289–300.
- Tusher, V.G., Tibshirani, R. & Chu, G. (2001). Significance analysis of microarrays applied to the ionizing radiation response. *PNAS*, 98(9), 5116–5121.
- Smyth, G.K. (2004). Linear models and empirical Bayes methods for assessing differential expression in microarray experiments. *Statistical Applications in Genetics and Molecular Biology*, 3(1), Article 3. *(limma's moderated t-test)*
- Zhu, Y., Orre, L.M., Zhou Tran, Y., Mermelekas, G., Johansson, H.J., Malyutina, A., Anders, S. & Lehtiö, J. (2020). DEqMS: A Method for Accurate Variance Estimation in Differential Protein Expression Analysis. *Molecular & Cellular Proteomics*, 19(6), 1047–1057.

### Imputation methods
- Tyanova, S., Temu, T., Sinitcyn, P., Carlson, A., Hein, M.Y., Geiger, T., Mann, M. & Cox, J. (2016). The Perseus computational platform for comprehensive analysis of (prote)omics data. *Nature Methods*, 13(9), 731–740.
- Lazar, C., Gatto, L., Ferro, M., Bruley, C. & Burger, T. (2016). Accounting for the multiple natures of missing values in label-free quantitative proteomics data sets to compare imputation strategies. *J. Proteome Res.*, 15(4), 1116–1125.
- Wei, R., Wang, J., Su, M., Jia, E., Chen, S., Chen, T. & Ni, Y. (2018). Missing Value Imputation Approach for Mass Spectrometry-based Metabolomics Data. *Scientific Reports*, 8, 663. *(QRILC)*
- Troyanskaya, O., Cantor, M., Sherlock, G., Brown, P., Hastie, T., Tibshirani, R., Botstein, D. & Altman, R.B. (2001). Missing value estimation methods for DNA microarrays. *Bioinformatics*, 17(6), 520–525.
- Kim, H., Golub, G.H. & Park, H. (2005). Missing value estimation for DNA microarray gene expression data: local least squares imputation. *Bioinformatics*, 21(2), 187–198.
- Stekhoven, D.J. & Bühlmann, P. (2012). MissForest — non-parametric missing value imputation for mixed-type data. *Bioinformatics*, 28(1), 112–118.
- Wang, S., Li, W., Hu, L., Cheng, J., Yang, H. & Liu, Y. (2020). NAguideR: performing and prioritizing missing value imputations for consistent bottom-up proteomic analyses. *Nucleic Acids Research*, 48(14), e83. *(benchmark of 23 methods)*

### Data & tools
- Cox, J. & Mann, M. (2008). MaxQuant enables high peptide identification rates, individualized p.p.b.-range mass accuracies and proteome-wide protein quantification. *Nature Biotechnology*, 26(12), 1367–1372.

---

## Citation

If Pro-ker contributes to a publication, please cite it as:

```
Ngo, B.M. (2026). Pro-ker Proteomics Analysis [Software].
Available at https://github.com/billy-ngo/proteomics-viewer
```

---

## Version history

See [CHANGELOG.md](CHANGELOG.md) for the full per-version history. Current release is shown in the in-app **Info** panel and via `proker --version`.

---

## License

Proprietary. See [LICENSE](LICENSE) for terms.

---

## Author

Billy M Ngo · billy.ngo0108@gmail.com · [github.com/billy-ngo](https://github.com/billy-ngo)
