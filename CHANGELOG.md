# Changelog

All notable changes to Pro-ker Proteomics Analysis are documented here.

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
