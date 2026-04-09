# Pro-ker Proteomics Analysis

An interactive browser-based tool for proteomics data visualization and statistical analysis. Upload MaxQuant proteinGroups.txt files and explore your data through configurable plots, group comparisons, and export-ready figures.

## Installation

```bash
pip install proker
```

### Quick Start

```bash
proker                      # launch the viewer on default port 8050
proker data.txt             # launch and auto-load a file
proker --port 9000          # use a custom port
proker --install            # create a desktop shortcut
proker --update             # check for updates
```

One-click installers are also provided for Windows (`Install_Windows.bat`) and macOS (`Install_macOS.command`).

## Features

- **Upload & Parse** — MaxQuant proteinGroups.txt (tab-separated)
- **Sample Grouping** — Assign samples to groups by shared prefix or manually
- **Processing** — Intensity/LFQ selection, normalization, pruning, missing-value filtering
- **Derived Groups** — Create ratio, difference, sum, or product groups from existing groups
- **Visualizations** — Volcano plots, dot plots, enrichment plots, unique protein plots, PCA
- **Graph Settings** — Per-plot marker styling, grid, background, font, threshold line toggles
- **Canvas** — Drag, resize, freeze, annotate, and right-click label multiple plots
- **Themes** — Built-in dark/light presets and custom color themes
- **Export** — SVG (vector), PNG (high-resolution raster), and CSV (full analysis data)
- **Sessions** — Save/load full analysis state as JSON; auto-save on every change

## Statistical Methods

### Volcano Plot — Differential Expression Analysis

Volcano plots visualize fold change vs. statistical significance for pairwise group comparisons. Each point represents a protein; its x-position is the log2 fold change and y-position is the -log10 FDR-adjusted p-value.

#### Welch's t-test

Group means are compared using Welch's t-test (two-sample, unequal variance). The test statistic is:

```
t = |mean_A - mean_B| / (SE + S0)
```

where SE = sqrt(var_A/n_A + var_B/n_B) is the pooled standard error and S0 is an optional fudge factor (see below). Degrees of freedom are estimated via the Welch-Satterthwaite approximation:

```
df = (var_A/n_A + var_B/n_B)^2 / ((var_A/n_A)^2/(n_A-1) + (var_B/n_B)^2/(n_B-1))
```

P-values are computed from the regularized incomplete beta function.

#### Benjamini-Hochberg FDR Correction

Raw p-values are adjusted for multiple testing using the Benjamini-Hochberg procedure to control the false discovery rate:

```
adjusted_p[i] = min(adjusted_p[i+1], raw_p[i] * n / rank[i])
```

where p-values are sorted in ascending order and adjusted from the largest rank downward. This controls the expected proportion of false positives among rejected hypotheses.

#### S0 Low-Abundance Correction

The S0 parameter (Tusher et al., 2001; used by Perseus/SAM) is a fudge factor added to the t-test denominator to penalize fold changes driven by low-abundance noise:

```
t_s0 = |mean_A - mean_B| / (SE + S0)
```

- At **S0 = 0** (default), this is a standard Welch's t-test
- At **S0 > 0**, proteins with small standard error (typically low-abundance) require larger absolute differences to reach significance
- **Typical values**: 0.1 to 2.0 (Perseus default: 0.1)

This prevents the common problem where low-abundance proteins show extreme fold changes purely due to measurement noise, flooding volcano plot extremes with unreliable hits.

#### Log2 Fold Change

Fold change is calculated as:

```
log2FC = log2(mean_GroupX / mean_GroupY)
```

- Positive values (right side of the plot) = higher abundance in Group X
- Negative values (left side of the plot) = higher abundance in Group Y

#### Missing Value Imputation

When enabled, zero/missing intensity values are replaced with half the minimum detected non-zero value for that protein across the relevant samples. This is a simple down-shift imputation approach that assumes missing values arise from proteins below the detection limit.

#### Significance Thresholds

Points are classified as significant when both conditions are met:
- FDR-adjusted p-value < FDR threshold (default: 0.05)
- |log2 FC| >= fold change threshold (default: 1.0)

Dotted reference lines on the plot mark these thresholds and can be toggled off via Graph Settings.

### PCA — Principal Component Analysis

PCA reduces high-dimensional proteomics data to two principal components for sample-level visualization, revealing batch effects, outliers, and group separation.

#### Algorithm

Pro-ker uses dual-space PCA (kernel method), optimized for proteomics datasets where the number of samples (n) is much smaller than the number of features/proteins (m):

1. **Mean centering** — Each protein's values are centered by subtracting the column mean across all samples
2. **Kernel matrix** — The n x n kernel matrix K = X * X^T is computed (instead of the m x m covariance matrix)
3. **Eigendecomposition** — Jacobi eigendecomposition extracts eigenvalues and eigenvectors from K
4. **Projection** — PC scores are computed as eigenvectors scaled by the square root of their eigenvalues

#### Output

- **PC1, PC2** — The first two principal components (axes of greatest variance)
- **Variance explained** — Percentage of total variance captured by each component, shown in axis labels
- Requires at least 3 samples

## Configuration Options

| Parameter | Plot | Default | Description |
|-----------|------|---------|-------------|
| FDR threshold | Volcano | 0.05 | Significance cutoff for adjusted p-values (0.05, 0.01, 0.001) |
| \|Log2 FC\| threshold | Volcano | 1.0 | Minimum absolute fold change for significance |
| S0 | Volcano | 0 | Low-abundance correction fudge factor (0 = off) |
| Impute missing | Volcano | On | Replace zeros with min(non-zero)/2 |
| Threshold lines | Volcano | On | Show/hide dotted threshold reference lines (Graph Settings) |

## Export

### CSV Export

The **Export Analysis as CSV** button (Analysis tab) produces a comprehensive file containing:

- **Metadata** — Software version, source file, protein counts
- **Processing settings** — Quantification type, normalization, pruning parameters
- **Sample groups** — Group assignments and derived groups
- **Raw data** — Pre-processing quantification values per sample
- **Processed data** — Post-filtering/normalization values with group means
- **Volcano plot statistics** — Per-protein fold change, p-value, FDR-adjusted p-value, and significance classification for each volcano plot on the canvas
- **PCA scores** — PC1/PC2 coordinates per sample with variance explained for each PCA plot on the canvas

### Canvas Export

Plots on the canvas can be exported as:
- **SVG** — Fully vectorized, editable in Illustrator/Inkscape/Figma
- **PNG** — High-resolution raster at 2x scale

## References

- Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *J. R. Stat. Soc. B*, 57(1), 289-300.
- Tusher, V.G., Tibshirani, R. & Chu, G. (2001). Significance analysis of microarrays applied to the ionizing radiation response. *PNAS*, 98(9), 5116-5121.
- Tyanova, S. et al. (2016). The Perseus computational platform for comprehensive analysis of (prote)omics data. *Nature Methods*, 13(9), 731-740.
- Cox, J. & Mann, M. (2008). MaxQuant enables high peptide identification rates. *Nature Biotechnology*, 26(12), 1367-1372.

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

**Current version: 3.6.0** (April 2026)

## Citation

```
Ngo, B.M. (2026). Pro-ker Proteomics Analysis [Software].
```

## License

Proprietary. See LICENSE for details.
