# Changelog

All notable changes to Pro-ker Proteomics Analysis are documented here.
Versioning follows [SemVer](https://semver.org/) (MAJOR.MINOR.PATCH).

## [4.14.1] — 2026-05-02

### Removed — stale assets
- **`proker_logo.jpg`** (top-level, 30 KB): old "BN" branding from v2.0.0, never referenced by any code. The current logo design (two-of-diamonds cards) is fully owned by `proteomicsviewer/icon.ico` and the inline SVG in `index.html`.
- **`proteomicsviewer/server/templates/logo.svg`** (2 KB): also old "BN" SVG, also never referenced.

### Changed — repo hygiene
- **`.gitignore`** restructured (was 22 lines with three duplicate patterns; now 39 lines organised by category — Python build, virtual envs, test data, tooling caches, editor/IDE, OS junk, Claude workspace). Adds common patterns that were missing: `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`, `.idea/`, `.vscode/`, `*.swp`, `~$*`.
- **`MANIFEST.in`** rewritten with explicit includes/prunes. Now includes `LICENSE` and `CHANGELOG.md` in the sdist (was missing). Also includes the bundled installers for source-archive users. Prunes `.github/`, `.claude/`, `Test data/`, `dist/`, `build/`. `global-exclude` for `*.egg-info`, `__pycache__`, `*.py[cod]`, `.DS_Store`, `Thumbs.db`. Verified by building the sdist locally — clean 32-entry tarball with all expected files.

### Added — CI auto-creates GitHub Releases on tag push
- **`.github/workflows/publish.yml`** extended to (1) verify the package version matches the pushed tag, (2) extract the matching changelog section from `CHANGELOG.md`, (3) call `softprops/action-gh-release@v2` to create a GitHub Release entry with the changelog body and the built wheel + sdist as release assets. Requires `contents: write` permission (added). Going forward, every `v*` tag push produces both a PyPI release and a GitHub Release entry — no more manual `gh release create` needed.

## [4.14.0] — 2026-05-02

### Added — limma & DEqMS moderated t-tests
The volcano plot now offers three statistical tests, selectable from a new "Statistical test" dropdown:

- **Welch's t-test** (default, unchanged): standard two-sample unequal-variance t-test with Welch–Satterthwaite degrees of freedom.
- **Moderated t-test (limma)**: empirical-Bayes shrinkage of per-protein variance toward a fitted scaled-inverse-χ² prior. Posterior variance s²_post = (d₀·s²₀ + d_g·s²_g) / (d₀ + d_g); posterior df = d_g + d₀. Hyperparameters d₀ and s²₀ estimated from the empirical distribution of per-protein log-variances using digamma/trigamma method-of-moments identities (Smyth 2004). Recommended for studies with few replicates per group (≤5).
- **Peptide-count moderated (DEqMS)**: extends limma by binning proteins by `floor(log₂(peptide_count))` and using each bin's median log-variance as a per-bin prior. Captures that proteins quantified from many peptides have inherently lower measurement variance (Zhu et al. 2020). Falls back to limma automatically when the file has no `Peptides` column.

### Implementation
- New pure-JS special functions: `digamma(x)`, `trigamma(x)`, `inverseTrigamma(y)` — verified against R's `psigamma` to 1e-6.
- New `fitLimmaPrior(variances, df)` returns `{d0, s0Squared}` via method of moments. Verified on 1000-protein simulation: true d₀=4, s₀²=2 → recovered d₀=3.95, s₀²=2.05.
- New `fitDEqMSPriors(variances, peptideCounts, df)` returns `{priorByCount, d0}`. Verified: 200 proteins with 1 peptide each (high variance) and 200 with 10 peptides each (low variance) produced priors of 17.5 and 1.78 respectively.
- New `moderatedPValue()` — pooled-variance moderated t with optional S0.
- Volcano builder refactored into a clean two-pass structure.
- The volcano render attaches a `_modTest = {method, d0, nProteinsUsed}` to the chart instance for inspection.

### Cumulative front-end work from v4.11.0 onward
This commit also lands the front-end implementation of the v4.11.0–v4.13.0 release notes (which described the contracts; this commit ships the JavaScript that fulfils them):

- v4.11.0: Format-info banner for parser adaptations (dropped aggregate columns, missing peptide/contaminant column, etc.); disabled-with-explanation for column-dependent filters; plot palette + group/analysis tooltips; zero-protein upload guard.
- v4.12.0: Per-plot try/catch isolation in `refreshAllPlots`; step-isolated `renderAll`; chart-destroy guard; upload state-rollback (priorRAW); defended boot autoload; visible error toast for sync errors and async rejections; emergency `window.__reset()` recovery hatch.
- v4.12.1: README.md publication-quality rewrite; in-app Info-panel docs updated.
- v4.13.0: Three new imputation methods (Random Forest / MissForest, LLS, canonical per-sample MinProb); old "MinProb" renamed to QRILC; matrix-precomputation context for matrix-wide methods; UI dropdown expanded to 7 options; seed traceability across all stochastic methods.
- v4.14.0: Statistical-test dropdown; Volcano Settings XLSX sheet adds "Statistical Test" column; in-app Statistical Methods section documents all three tests + the digamma/trigamma derivations; References list adds Smyth (2004), Zhu et al. (2020), Wei et al. (2018), Kim et al. (2005), Stekhoven & Bühlmann (2012), Wang et al. (2020).

### Verification
Pure-JS unit tests (Node) confirm bit-identical reproducibility for stochastic imputation methods, recovery of known statistical-prior parameters, and dispatcher correctness across all 7 imputation methods. End-to-end `curl` against the live server confirms all 7 imputation options + 3 statistical-test options serialise and render correctly on a real 1492-protein × 10-sample MaxQuant file.

## [4.13.0] — 2026-05-02

### Added — three new imputation methods (front-end implementation lands in v4.14.0 cumulative commit)
The volcano-plot imputation menu now covers seven methods spanning the four families established in the proteomics literature (NAguideR, Wang et al. 2020), instead of four:

- **Random Forest (MissForest)** — pure-JS implementation of the iterative random-forest imputer (Stekhoven & Bühlmann 2012, *Bioinformatics* 28:112). For each sample column with missing values, trains a 50-tree forest of depth-6 regression trees with m_try = √p, then iterates until relative-change tolerance (0.01) or max 5 iterations. Top-ranked across multiple proteomics benchmarks.
- **LLS (Local Least Squares)** — pure-JS implementation of Kim et al. (2005, *Bioinformatics* 21:187). Per protein, finds k = 10 nearest neighbours, fits a regularised linear regression of the target on the neighbours, and predicts the missing values.
- **QRILC** — exposed as its own option (Wei et al. 2018). This is what Pro-ker's previous "MinProb" actually computed — a Gaussian centred at the 1st percentile of the comparison's global log2 distribution.

### Changed — MinProb is now the canonical per-sample form
The "MinProb" option now implements the canonical algorithm from Lazar et al. (2016, *J. Proteome Res.* 15:1116) and the `imputeLCMD` R package: per-sample MinDet computation, with each missing cell drawn from a Gaussian centred on its own sample's MinDet. Previously Pro-ker's "MinProb" computed a global 1st-percentile distribution (which is actually QRILC's algorithm) — now exposed as the separate "QRILC" option.

### Improved — seed traceability across all stochastic methods
All four stochastic methods (Perseus, MinProb, QRILC, MissForest) now consume the user-supplied **Random seed** and produce bit-identical output for the same seed + same data. Per-protein methods derive a per-protein seed; matrix-wide MissForest uses the global seed once for bootstrap and feature subsampling. Deterministic methods (kNN, LLS, Min/2) ignore the seed; the seed input is hidden in the UI when one of these is selected.

## [4.12.2] — 2026-05-02

### Fixed — desktop icon
- **Transparent background.** The previous `icon.ico` was rendered as 8-bpp BMP entries with a fully opaque white square filling the canvas (0 transparent pixels, ~82 % white). On macOS Dock and Windows desktop the icon visibly sat inside a white tile. The new icon has a properly transparent background (~51 % transparent, ~48 % opaque, ~1 % anti-aliased edges).
- **No more pixelation when scaled up.** The old ICO topped out at 48 × 48, so on modern displays (Retina, 4K) the desktop launcher was scaled up from 48 px and looked blocky. The new ICO ships seven sizes — 16, 24, 32, 48, 64, 128, 256 — encoded as PNG-in-ICO so each one renders crisp at its native resolution.
- **No more stretched/awkward proportions.** The icon is rendered into a true 1 : 1 square canvas with the cards centred and proportionally scaled.
- **Sized-down variants drop unreadable detail.** At 16, 24, and 32 px the corner "2" marks become unreadable specks; the small-size renders omit those and keep just the centre "2".
- **`icon.py` docstring** updated to reflect that PNG-in-ICO is now the primary case (BMP-conversion fallback retained).

## [4.12.1] — 2026-05-01

### Documentation
- **LICENSE** file created (referenced by `pyproject.toml` and the README but previously missing). Proprietary terms with explicit permission for academic / non-commercial research use.
- **README.md** rewrite — covers the imputation methods, multi-file workflows, deterministic seeds, XLSX/per-plot-CSV exports, robustness guarantees, and troubleshooting. *(Lands cumulatively in the v4.14.0 commit.)*
- **CHANGELOG.md** consolidated and consistent style throughout.
- **In-app Info panel** updated: version display, version history, References list expanded to include Lazar et al. 2016 and Troyanskaya et al. 2001. *(Lands cumulatively in the v4.14.0 commit.)*

## [4.12.0] — 2026-05-01

### Fixed — JS robustness, no single error can lock the program
*(Front-end implementation lands in the v4.14.0 cumulative front-end commit; the contract documented here is what shipped from this release onward.)*

- **Per-plot error isolation in `refreshAllPlots`.** Each plot renders inside its own `try/catch`; on failure, the plot's div shows a clear in-place "Plot render error" placeholder and the rest of the canvas keeps rendering.
- **Step-isolated `renderAll`.** Per-step loop with `try/catch` around each call (renderUnassigned → renderBins → … → autoSaveSession). A failure in one step no longer prevents the others — most importantly autosave still runs.
- **Chart `destroy()` guard in `renderPlot`.** A throwing destroy no longer blocks creating the new chart; the old `CHARTS` entry is always cleared.
- **Upload state-rollback.** If `initGrouping()` throws after the response is parsed, `RAW` is restored to its prior value so the user can re-upload cleanly.
- **Boot-autoload defended.** The startup `/api/data` fetch wraps both the network call and `initGrouping()` separately.

### Added — visible error feedback
- **Global error toast.** `window.onerror` and a new `unhandledrejection` listener surface errors as a dismissable red toast in the bottom-right (auto-dismisses after 12 s). The toast is itself fully `try/caught`.
- **Async error containment.** `unhandledrejection` listener catches promise rejections that previously vanished into devtools-only output.
- **Emergency reset hatch.** `window.__reset()` exposed on the global so a user can recover from an unrecoverable state via the browser console.

## [4.11.0] — 2026-05-01

### Fixed — parser robustness
- **NaN / Infinity in quant cells no longer breaks uploads.** `_float()` now collapses non-finite values to `0.0`. Previously a file with `"NaN"` or `"Inf"` in any intensity column parsed but Starlette refused to JSON-serialize the response, returning an opaque 500 error.
- **Inf in integer fields no longer crashes the parser.** `_int()` also catches `OverflowError` from cells like `"Inf"` or `"1.5e500"` in `Peptides` / `Sequence length`.
- **UTF-16 (LE/BE) and UTF-8 BOM auto-detected.** Excel's "Save As Tab-delimited Text" emits UTF-16 LE with BOM, which previously failed to parse. Files are now opened with the correct encoding based on the BOM bytes.

## [4.1.0] - 2026-04-09

### Added
- **Shape annotations** — New `+Shape` button in canvas toolbar. Add rectangles, circles, ellipses, diamonds, or triangles to the canvas. Shapes are resizable, draggable, with customizable border color (via swatch palette), border width, and optional fill.
- **Canvas panning** — Click and drag on empty canvas space to pan/scroll the viewport.
- **Separate volcano threshold controls** — Graph settings for volcano plots now show individual FC and FDR threshold line toggles alongside the main threshold checkbox.

### Changed
- **Toolbar layout** — Top row is fixed-height with `+Text`, `+Line`, `+Shape` buttons. Editing controls (text formatting, line style, shape properties, point color) appear in a second row that expands downward only when an element is selected.

## [4.0.0] - 2026-04-09

### Added
- **Published imputation methods** — Four scientifically established methods for missing value imputation in volcano plots: Perseus-style Gaussian (Tyanova et al. 2016, default), MinProb left-censored (Lazar et al. 2016), kNN k-nearest neighbors (Troyanskaya et al. 2001), and the original Min/2 baseline. Selectable via dropdown in volcano config.
- **Robust session save/load** — Sessions now persist graph positions, sizes, frozen state, point color overrides, pinned annotations, canvas text boxes and lines, canvas zoom level, Groups of Interest, and species highlights. Session format upgraded to version 2.
- **Searchable protein dropdown** — Peptide coverage map now has a type-to-search dropdown showing both locus tag and annotation name for each protein.
- **FASTA drag-and-drop** — Drag a .fasta file directly onto the coverage textarea to load it.
- **Amino acid level coverage display** — Coverage map now shows individual residues with green for detected peptides, gray for uncovered, and `|` boundary markers between adjacent peptides. Increased limit to 2000 aa.
- **UI tooltips** — Added hover tooltips to all processing tab options, graph settings controls, and tab buttons.

### Changed
- **Context menu color picker** — Right-click selection "Color selected" now uses the unified 120-color swatch palette instead of the native browser color picker.
- **Upload performance** — Removed duplicate `buildProcessedData()` call during initial data load. Fixed O(n²) protein dropdown population with single DOM write.

## [3.9.0] - 2026-04-09

### Added
- **Protein Abundance plot** — New visualization type in the palette: ranked protein abundance in a single group (mean) or individual sample. Supports optional error bars with three types: standard deviation (SD), standard error of the mean (SEM), or range (min–max). Hover shows full statistics including SD, SEM, range, and per-sample breakdown.
- **Error bar rendering in ProkerChart** — SVG charting engine now supports `trace.error` with symmetric (`y`) or asymmetric (`ymin`/`ymax`) error bars. Rendered as vertical lines with caps underneath data markers, respecting per-point colors and plot clipping.
- **Volcano plot tooltip guidance** — Log2 FC threshold and S0 inputs now show detailed hover tooltips with typical values and interpretations (e.g., "1.0 = 2-fold change", "0.1 = Perseus default"). Helper text below each input provides quick reference.

## [3.8.0] - 2026-04-09

### Changed
- **Unified color swatch palette** — All color pickers (bin groups, species highlight, Groups of Interest) now use the BiNgo-style 120-color swatch popup with click for palette and double-click for native picker, replacing native `<input type="color">` elements.
- **Toolbar swatch fix** — Clicking inside the swatch popup no longer dismisses the toolbar (added `.swatch-popup` class guard).
- **Dynamic macOS plist version** — `CFBundleVersion` in generated `.app` bundle uses `__version__` dynamically.

## [3.7.0] - 2026-04-09

### Fixed
- **Canvas line annotations** — Rewrote `addCanvasLine()` to use a single state object and single set of document-level listeners, preventing listener accumulation on each re-render.
- **Canvas text annotations** — Fixed text box selection and toolbar interaction glitch.
- **Auto-shutdown lock path** — Server lock file now uses `~/.proker/` consistently (was `~/.proteomicsviewer/`).
- **macOS shortcut version** — `CFBundleVersion` in generated `.app` plist now uses the dynamic package version instead of a hardcoded string.

### Changed
- Merged all pending features from parallel development (v3.4.0–v3.6.1).

## [3.6.1] - 2026-04-09

### Changed
- All graph types now default to the same marker format: size 5, circle symbol. Previously volcano NS was 4, up/down was 6, unique was 7, PCA was 10, dot plot edges were 4. Now consistent across enrichment, volcano, dot plot, unique, and PCA.

## [3.6.0] - 2026-04-09

### Added
- **Groups of Interest** — New section in the Analysis tab to select proteins by locus tag numeric range and assign custom color, shape (circle/square/diamond/triangle/star/cross), and size. Overrides propagate to all protein-level plots (volcano, enrichment, dot, unique), taking priority over species highlights and default styles.
- **Species Highlight** — Color proteins from a species/organism on all graphs by locus tag prefix with checkbox and color swatch per species.
- **2-of-diamonds logo** — New SVG logo matching the provided card design: thick dark borders, red "2" with diamond suit symbols. Applied to favicon, header, info panel, and desktop icon.
- **Hover tooltips show protein ID** — Hovering a point now shows both the gene name and the full protein ID / locus tag on separate lines.
- **Minimum click target** — Invisible 8px hit area behind small dots so tiny points (2-4px) remain easy to click and hover.
- **Canvas toolbar enhancements** — Text: underline toggle, text alignment, Helvetica font, sizes up to 48px. Lines: arrowhead toggle, dash-dot style. Text boxes and lines show toolbar on single click.
- **Color swatch on hover** — All color selector boxes now show the swatch popup on mouseenter in addition to click.

### Changed
- ProkerChart SVG engine extended to support per-point size and symbol arrays (in addition to existing per-point color arrays).
- Unified `applyMarkerOverrides()` helper used by all plot builders for consistent GOI + species highlight + default fallback styling.

### Fixed
- **`wDrag is not defined` crash** when using +Line feature — removed dangling reference, rewrote line drag handling.
- Desktop icon simplified to two offset cards with centered red "2" (no overlapping BN text).
- CLI startup message after shortcut prompt to prevent apparent hang.

### Removed
- Dead Bokeh dependency: deleted `plots.py` and `/api/plot` endpoint (unused since v3.0.0).

## [3.5.0] - 2026-04-08

### Added
- **Peptide coverage map** — New section in the Analysis tab where users can select a protein, paste a FASTA sequence, and visualize which peptides were identified by mass spectrometry. Shows a color-coded coverage bar, residue-level highlighted sequence, and a sortable peptide position table. Reads peptide sequences from the MaxQuant "Peptide sequences" column in proteinGroups.txt.

### Fixed
- **Desktop icon** — Rewritten to match the browser favicon: dark rounded-rect background, correct back-card opacity color, card border strokes, and matching card proportions/positions

## [3.4.0] - 2026-04-08

### Added
- **Volcano plot threshold lines** — Dotted reference lines at the FC and FDR significance thresholds, toggleable via "Threshold lines" checkbox in Graph Settings
- **S0 low-abundance correction** — Perseus/SAM-style fudge factor (S0) added to the t-test denominator to penalize noisy fold changes from low-abundance proteins; configurable during volcano plot setup (default: 0 = off)
- **Volcano plot group labels** — X-axis now shows directional labels indicating which side corresponds to which sample group (e.g. "← GroupY | Log2 Fold Change | GroupX →")
- **Volcano and PCA data in CSV export** — Export Analysis now includes per-protein volcano statistics (fold change, p-value, FDR, significance) and PCA scores (PC1/PC2, variance explained) for all plots on the canvas
- **Statistical methods documentation** — New "Statistical Methods" section in the Info panel documenting Welch's t-test, BH-FDR, S0 correction, imputation, and PCA algorithm
- **Dynamic methods reference in Analysis panel** — "Statistical Methods Used" section appears automatically when volcano or PCA plots are on the canvas
- **README.md** — Comprehensive project README with installation, features, statistical methods, configuration options, export details, and academic references
- **CHANGELOG.md** — Version history for all releases

### Changed
- Volcano plot non-significant point color changed from `#30363d` to `#6e7681` for better visibility against dark plot background
- Non-significant point opacity increased from 0.3 to 0.5 in Bokeh backend
- Reference lines system added to ProkerChart engine (`_refLines` with `relayout({showRefLines})` toggle)

### Fixed
- Install scripts cleaned up; removed unused Bokeh dependency

## [3.3.0] - 2026-04-04

### Added
- BiNgo-style unified 120-color swatch palette across all color pickers
- Undo/redo system for canvas operations
- Graph settings: hollow marker shapes, font size control, separate plot/paper background toggles
- Draggable and resizable floating panels (BiNgo style)

### Changed
- Tight dot plot axes with axis break marks for discontinuous regions
- Per-group colors preserved when restyling (PCA, volcano)

### Fixed
- Volcano plot: exclude single-group proteins, correct log2FC calculation
- More visible volcano plot dots
- Selection tool no longer colors all points

## [3.2.0] - 2026-03-28

### Added
- Intra-group sample comparison for dot plots
- Dot plot axis breaks for single-group proteins
- Toolbar: annotations, point color swatch, title formatting

### Changed
- Graphs appear centered in visible viewport area
- Clean dot plot rendering: axis-floor placement, diagonal reference line

### Fixed
- PCA computation and variance explained
- Right-click selection box position
- Graph drag snapping

## [3.1.0] - 2026-03-22

### Added
- Number inputs for graph settings (size, opacity, font size)
- Scroll zoom for canvas

### Changed
- Plots centered on creation
- Fixed zoom controls

## [3.0.0] - 2026-03-18

### Added
- Custom ProkerChart SVG rendering engine (replaces Plotly)
- Context toolbar for selected elements
- Canvas zoom controls for multiple graphs

### Changed
- Improved beeswarm layout for unique protein plots
- Show rank #/total in enrichment hover tooltips

### Fixed
- Selection precision in SVG engine

## [2.9.0] - 2026-03-12

### Added
- Beeswarm layout for unique protein plots
- Radio button aggregation mode toggle
- Freeze/unfreeze individual graphs

### Changed
- Auto-scale complementary axis when one axis is manually changed

## [2.8.0] - 2026-03-08

### Added
- Dynamic version display fetched from backend `/health` endpoint
- Rebuilt guided tutorial with 8 interactive steps
- Transparent background option for graphs

### Fixed
- Glitchy text box and line dragging
- Label dragging after background removal

## [2.7.0] - 2026-03-04

### Fixed
- Color selection in graph settings
- Clean label rendering
- Draggable plot positions

## [2.6.0] - 2026-02-28

### Added
- Comprehensive CSV export with raw data, processed data, groups, and settings
- Removed duplicate export buttons

## [2.5.0] - 2026-02-24

### Added
- Export Canvas as SVG and PNG
- Text box and line annotation tools
- Grid visibility toggle

## [2.4.0] - 2026-02-20

### Changed
- Arial font family for all text
- Non-bold text styling
- More distinguishable dot markers

### Fixed
- Log2 enrichment calculation
- Moveable axis titles
- Polished range editor

## [2.3.0] - 2026-02-16

### Fixed
- Axis and title editing by disabling Plotly drag capture layer

## [2.2.0] - 2026-02-12

### Added
- Editable chart titles and axis labels
- Right-click multi-point selection

### Fixed
- Unique protein plot rendering
- Windows event loop policy (`__main__.py`)
- Redesigned shortcut icon to match in-app logo

## [2.1.0] - 2026-02-08

### Added
- Graph settings panel (marker size, shape, color, opacity)
- Click-to-label system for data points
- Intensity/spectral count toggle
- Axis range editing
- Canvas guided tour
- Export panel

## [2.0.0] - 2026-02-04

### Added
- BiNgo-style header with tab navigation
- Info panel with version, citation, and references
- Theme system with dark/light presets and custom colors
- Session save/load as JSON with auto-save
- Auto-update from PyPI with version checking
- Desktop shortcut installer (Windows/macOS)
- GitHub Actions PyPI publish workflow
