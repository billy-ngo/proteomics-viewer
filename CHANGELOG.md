# Changelog

All notable changes to Pro-ker Proteomics Analysis are documented here.
Versioning follows [SemVer](https://semver.org/) (MAJOR.MINOR.PATCH).

## [4.15.14] — 2026-05-06

### Fixed — X-axis range survives every re-render path
v4.15.13 made axis ranges round-trip through session save/load, but they were still wiped any time `renderPlot()` ran — which is many code paths: PCA Graph Settings change, filter change → `renderAll`, freeze toggle, reset colours, session restore. `renderPlot` destroys the old chart and constructs a fresh `ProkerChart`, so the in-memory `xRange` / `yRange` / `_xManual` / `_yManual` were silently lost between destroy and re-render.

The fix promotes axis ranges (and title drag positions) to a first-class persisted field on `p.config._chartState`, mirroring the existing `_gsMarker` / `_gsLayout` pattern that already survives every re-render:

1. `renderPlot` now snapshots the OLD chart's `xRange/yRange/xManual/yManual/zoomed/titlePos/xTitlePos/yTitlePos` into `p.config._chartState` BEFORE calling `destroy()`. The snapshot reads the live chart, so it always reflects the user's most recent zoom or title drag.
2. After `build*Config` and the `_gsLayout` / `_gsMarker` reapply, `renderPlot` restores from `p.config._chartState` and triggers one render, committing the user's range and title positions on the fresh chart.
3. `buildSessionObject` writes the same snapshot into `p.config._chartState` at save time, then lets `cp.config` (which includes `_chartState`) flow through the session JSON naturally — no separate `chartState` field needed.
4. `loadSession` migrates v4.15.13 saves (which used a sibling `cp.chartState` field) into `cfg._chartState` so older sessions still restore the user's zoom.

The restore is conservative: only manual ranges (`xManual` / `yManual === true`) are reapplied. A plot saved at the auto range stays auto.

### Fixed — graphs are draggable again when paper background is hidden
Drag-to-move attached its `mousedown` listener to `svg.querySelector('rect')` — the FIRST `<rect>` element in the SVG. With paper background visible this picked the full-size paper-bg rect, so dragging worked anywhere on the chart. With paper background hidden the first rect became the smaller plot-bg (so drag only worked over the plot area itself, not the title / axis / margin regions). With both backgrounds hidden the first rect was the `clipPath` rect inside `<defs>` — not visible, no clicks captured — and drag was completely broken.

Two changes:

1. **Drag listener moved to SVG level.** Now any `mousedown` inside the SVG bubbles up and starts a drag, with bail-outs for clicks on data points, titles, tick labels, annotations, and the selection rectangle so existing interactions keep working.
2. **Defensive drag-surface rect added.** A full-SVG transparent `<rect class="drag-surface" pointer-events="all">` is rendered first inside the SVG so the chart always has something to capture pointer events even when both backgrounds are hidden. Without it, browsers don't reliably hit-test fully empty SVG regions.

Tested combinations: paper bg on / plot bg on; paper bg off / plot bg on; paper bg on / plot bg off; both off; transparent bg toggle. All four reliably drag now.

## [4.15.13] — 2026-05-06

### Fixed — chart axis range and title positions now survive session save/load
Two related session-persistence bugs were silently dropping user-set state on reload.

**Axis ranges (the bug the user hit):** When the user zoomed the X-axis to a specific range — either via right-click drag-zoom or the right-click "Edit X range" menu — `chart.xRange` / `chart.yRange` and the `_xManual` / `_yManual` flags were updated on the chart instance but never serialized into the session JSON. On reload, `renderPlot` constructed a fresh `ProkerChart` and let `build*Config` compute auto ranges from the data, so the user's saved zoom was wiped to "show full range".

**Title drag positions:** Same root cause for `_titlePos`, `_xTitlePos`, `_yTitlePos`. When the user dragged a chart title or axis title to a custom location, that position lived on the chart instance only — it never made it into the session payload, so reloading snapped every title back to its build-time default position.

`buildSessionObject` now writes a per-plot `chartState` block alongside the existing `position` / `colorOverrides` / `annotations` / `goiLegend` fields:

```json
{
    "xRange":   [-1.5, 2.0],     "yRange":   [0, 5],
    "xManual":  true,            "yManual":  true,
    "zoomed":   true,
    "titlePos":  {"x": 350, "y": 18},
    "xTitlePos": null,
    "yTitlePos": null
}
```

`loadSession` restores this in the same setTimeout that runs `renderPlot`, AFTER `renderPlot` has run (so `build*Config` doesn't overwrite the restored values), and triggers one extra `chart.render()` to commit the visual update. The restore is conservative: only manual ranges (`xManual === true`) are reapplied — sessions saved while a plot was at its auto range stay at auto range.

### Fixed — partial card position no longer leaves plots at 0×0
The session-restore for plot card position only applied `width` / `height` if the saved value was truthy. A schema gap (e.g. an older session saved before width/height were captured, or a corrupted entry) could leave `pw.style.height` or `pw.style.width` unset, collapsing the card to its CSS-default near-zero size.

The restore now always sets explicit width and height, falling back to the create-time defaults (`700px` × `420px`) when the saved value is empty.

### Hardened — saved card size falls back to actual rendered size
`buildSessionObject` now reads `card.offsetWidth` / `offsetHeight` as a fallback when `card.style.width` / `style.height` are empty. The inline-style values are normally set by `setupPlotResize` and `addCanvasPlot`, but a defensive fallback covers any path that mutates the rendered size without writing back to inline style.

## [4.15.12] — 2026-05-01

### Reverted — title auto-shrink (v4.15.11)
v4.15.11 introduced dynamic font scaling + ellipsis truncation for chart and axis titles when the plot card was small enough to clip them. Per user feedback this was the wrong approach: titles should be allowed to be **larger than their graphs** rather than be silently shrunk or truncated.

The auto-shrink path is removed:
- `_textWidth()` and `_fitTitle()` helpers deleted from `proker-charts.js`.
- All three titles (chart, X-axis, Y-axis) render at their original fixed font sizes (`fs+1` for chart title, `fs` for axes).
- The SVG element gains `style="overflow:visible"` so glyphs that extend past the SVG's `width`/`height` bounds still paint into the parent `.canvas-plot` wrapper instead of being clipped at the SVG edge.
- `<svg:title>` hover-tooltip elements removed (no longer needed — full text is always rendered).

Net effect: a long Y-axis title on a narrow plot now renders at full size and naturally extends into the canvas margin around the chart card. PNG and SVG exports inherit the same overflow-visible behaviour, so titles export at their full rendered width.

### Added — marker outline as a Graph Settings option (off by default)
Until this release every filled marker drew with a hard-coded `stroke="${T.plot}"` 1 px outline — visible as a faint ring around every dot, matching the plot background colour. This was a debug-era styling artefact that survived too many revisions.

Outlines are now **off by default** and **opt-in via Graph Settings**:

1. The default fill-only render path emits no `stroke` attribute, so dots are pure fills with the chosen colour and opacity.
2. A new **Outline** checkbox appears in the Graph Settings panel, immediately below the Hollow checkbox, alongside an **Outline color** swatch.
3. The colour swatch uses the same UI affordance as the marker / plot-bg / paper-bg / grid swatches: click for the in-app palette, hover to peek, double-click for the OS native colour picker.
4. Outline default colour is `#000000`; users can pick any colour and it's persisted on the plot's `_gsMarker` override so it survives re-renders, plot duplication, and session save/load.

Wiring:
- `proker-charts.js`: marker render at line ~324 now branches on `marker._outline === true` to add `stroke="${marker._outlineColor}" stroke-width="${marker._outlineWidth || 1}"`. The default branch emits no stroke.
- `proker-charts.js` `restyle()`: accepts `outline`, `outlineColor`, and `outlineWidth` props and stores them as `marker._outline / _outlineColor / _outlineWidth` on the trace.
- `index.html` `applyGraphSettings()`: reads `gs-outline` checkbox and `gs-outline-color` input, includes both in the `markerOverride` object so they round-trip through `cp.config._gsMarker` on every future render.
- `index.html` `openGraphSettingsForPlot()`: populates the new inputs from the persisted override first, falling back to the chart's first trace's marker `_outline / _outlineColor` properties.
- The `gsUpdateSwatches()` helper and the input listener registration both include `gs-outline-color`, so the swatch colour stays in sync with the picker value.

The Hollow render path (which uses the marker's own colour as a stroke) is unaffected — Outline only applies to the filled-marker branch. Hollow + Outline cannot conflict because they're mutually exclusive render paths.

## [4.15.11] — 2026-05-06

### Fixed — chart and axis titles no longer clipped when the plot is shrunk
Long titles (chart title, X-axis title, Y-axis title) used to render at their fixed font size and silently overflow the SVG bounds when the plot card was made smaller. The result was titles cut off mid-word at the chart's left/right edge — visible in earlier screenshots where the volcano plot's Y-axis title "RpoC swarmer log2(RpoC swarmer / WT swarmer) enriched in WT swarmer" was clipped at the top edge.

All three title types now **auto-shrink to fit** the available space:

1. Measure the title's rendered width via a hidden `<canvas>` 2D context (`measureText`), accurate to the actual font and string.
2. If the title fits at the base font size (`fs+1` for chart title, `fs` for axis titles), render as-is.
3. Otherwise progressively shrink the font in 0.5 px steps down to a 8 px minimum until it fits.
4. If the title still doesn't fit at minimum size, **truncate with "…"** via binary-search for the longest fitting prefix.

Each title also carries an `<svg:title>` child element with the full untruncated text — modern browsers show this as a hover tooltip, so the user can still read the original title even when it's been shrunk or truncated.

Available width per title:
- Chart title (top, centred): plot width `pw`.
- X-axis title (bottom, centred): plot width `pw`.
- Y-axis title (rotated −90°, left): plot height `ph` (after rotation, the text extends along the chart's vertical axis).

A 3 px safety pad on each side prevents anti-aliasing/kerning from pushing rendered glyphs over the edge.

The `<svg:title>` tooltip carries the full text into PNG/SVG exports too — when you hover a clipped axis title in an exported SVG opened in a browser, the original full label is still revealed.

## [4.15.10] — 2026-05-06

### Fixed — +Text now actually does something visible
The `+Text` button in the canvas toolbar previously placed the text box at fixed coordinates `(50, 50)` from the top-left of the canvas. If the user had scrolled, zoomed, or just had a busy canvas, the text box landed off-screen and the button appeared to do nothing. Same applied when the user wanted the text in a specific location — they had to drag it from the corner every time.

`addCanvasTextBox()` now enters **placement mode**:

1. Cursor switches to crosshair on the canvas + viewport.
2. A small accent-coloured banner appears at the top of the screen: *"Click on the canvas to drop a text box… (Esc to cancel)"*.
3. The user clicks anywhere on empty canvas space → a text box drops at exactly those coordinates.
4. The text box is **auto-focused with its placeholder text "Text" pre-selected**, so the user can immediately type to replace it. No extra double-click needed.
5. Pressing <kbd>Escape</kbd> at any point during placement cancels and restores the cursor.

Click-target detection: placement-mode clicks on plots, annotations, GOI legends, zoom controls, or other text boxes are ignored (those keep their own behaviour). Click coordinates are converted from screen space to canvas space accounting for `canvasScale` (zoom level) so the box lands exactly under the cursor regardless of zoom.

The text box's drag-to-reposition behaviour was also made canvas-zoom-aware (the previous implementation moved the box at scaled pixels, so dragging a zoomed-out canvas was sluggish).

A reusable `_enterCanvasPlacement(msg, onPlace)` helper handles the cursor/banner/click-listener/Esc-to-cancel boilerplate, so the same pattern can later be applied to `+Line` and `+Shape` buttons too.

## [4.15.9] — 2026-05-06

### Changed — empty-canvas hint text
The empty-canvas drop hint now reads "Add a graph from the Visualization tab" instead of "Drop a graph type here or click one from the palette". Drag-and-drop still works; the message just points users to the canonical entry point. Replaced in all four spots that recreate the empty-canvas state (initial render, `resetState()`, `removePlot()` when last plot leaves, and `clearCanvas()`).

## [4.15.8] — 2026-05-06

### Fixed — marker color change no longer wipes Groups-of-Interest highlights
The v4.15.7 fix went too far: by applying `trace.marker.color = props.color` unconditionally, it overwrote the per-point colour arrays that `applyMarkerOverrides()` set for Groups-of-Interest and species highlights — so picking a marker colour in Graph Settings made every GOI lose its distinctive colour, shape, and size.

Fix in `proker-charts.js`'s `restyle()`: when the trace has a `marker.priority` array (the flag that `applyMarkerOverrides` writes for highlighted points), only replace `color[i]`, `size[i]`, `symbol[i]` where `priority[i] === 0` (ordinary point). Priority `1` (species highlight) and `2` (GOI) are preserved verbatim. Per-point `_colorOverrides` set via right-click → "Color selected" continue to take precedence over both in the render loop.

### Fixed — changing marker colour no longer drags a stale dark-theme background onto the plot
On non-dark themes (light, soft, custom), picking a marker colour also unexpectedly switched the plot's background to dark surface (`#161b22`) and the paper background to dark page (`#0d1117`).

Root cause: `openGraphSettingsForPlot()` was reading from `el.data` and `el.layout` to populate the panel inputs — but those are old Plotly properties that don't exist on ProkerChart. The reads silently no-op'd, so the inputs stayed at whatever was last there. Initial state for those inputs was the hardcoded dark-theme defaults from the static HTML (`<input type="color" value="#161b22">` etc). When the user then changed a marker colour, `applyGraphSettings()` read **all** form inputs — including the stale dark-theme bg/grid — and wrote them back to the chart, forcing the dark surface onto the plot.

Fix: `openGraphSettingsForPlot()` now reads from the correct sources, in this precedence order:

1. **`cp.config._gsMarker` / `cp.config._gsLayout`** — the user's persisted Graph Settings overrides for this plot (added in v4.15.7). If present, these win.
2. **The ProkerChart instance's actual current state** — `chart.opts.theme.{plot,bg,grid}`, `chart._fontSize`, `chart._showGrid`, `chart._hidePlotBg`, `chart._hidePaperBg`, and `chart.traces[0].marker.{size,color,symbol,opacity,_hollow}`. Reflects whatever the active theme produced if no user override exists.
3. **Hard-coded fallbacks** if no chart yet exists.

For per-point arrays (size/color/symbol when GOI is active), a small `pickScalar(value, priority)` helper picks the value at the first index where `priority[i] === 0` (an ordinary point), so the panel doesn't show a GOI's colour as the "marker colour" default.

### Effect
- Picking a new marker colour now changes ONLY the ordinary points' colour. GOI dots keep their custom colour, shape, and size.
- Picking a marker colour on a light-theme plot leaves the bg/paper/grid colours alone — the panel reads the live theme-derived values, and writing them back is now a no-op rather than a regression.
- Same for any other Graph Settings combination: opening the panel always shows the plot's current state, so changing one option doesn't disturb the others.

## [4.15.7] — 2026-05-06

### Fixed — Graph Settings marker colour now actually applies
The colour picker in Graph Settings was silently ignored on essentially every plot type. The bug was an over-restrictive condition in `proker-charts.js`'s `restyle()`:

```js
// BEFORE — colour only applied when ALL of:
//   props.color is truthy
//   AND there's exactly ONE trace
//   AND traces[0].marker.color is NOT an array
const applyColor = props.color && this.traces.length === 1 &&
                   !Array.isArray(this.traces[0]?.marker?.color);
```

This skipped colour changes for:
- **Volcano plots** — 3 traces (`ns`, `up`, `down`) → `traces.length === 1` is false → skip
- **Dot plots** — per-point colour arrays → `Array.isArray(...)` is true → skip
- **PCA** — per-group traces → multiple traces → skip
- **Enrichment / unique / abundance** — per-point colour arrays → skip

I.e. **almost every plot type silently ignored the user's colour pick**. Fix: apply `trace.marker.color = props.color` to every trace unconditionally. Per-point overrides set via right-click → "Color selected" still take precedence in the render loop, so individual highlights are preserved.

### Fixed — Graph Settings now persist across re-renders, session reload, plot duplication, and export
Every Graph Settings option (marker size / shape / colour / opacity / hollow, plot background, paper background, grid colour, grid visibility, font size, threshold-line visibility per axis) was being silently wiped on every re-render. Root cause: `chart.restyle()` and `chart.relayout()` mutate the live chart instance, but on the next call to `renderPlot()` (triggered by filter changes, freeze toggles, session reload, plot duplication, or any data refresh), `build*Config` rebuilds `this.traces` and resets layout flags (`_fontSize`, `_showGrid`, `_hidePlotBg`, etc.) from scratch — discarding the user's tweaks.

Fix mirrors the title-edit persistence from v4.15.4:
- `applyGraphSettings()` now stores the chosen values on the plot's config:
  - `cp.config._gsMarker = {size, symbol, color, opacity, hollow}`
  - `cp.config._gsLayout = {plotBg, paperBg, gridColor, showGrid, showRefLines, transparentBg, fontSize}`
- `renderPlot()` re-applies these via `chart.relayout()` + `chart.restyle()` immediately after `build*Config` runs.
- Per-axis FC / FDR threshold-line visibility (which was already persisted as `cp.config.showFClines` / `showFDRline`) is now also re-applied to `chart._refLines` after every render.
- `applyGraphSettings()` triggers an autosave so the change is captured immediately.

Because `_gsMarker` and `_gsLayout` live on `cp.config` (which the session save serialises whole), all Graph Settings round-trip through reload and plot duplication automatically — no extra plumbing.

### Side effect — exports now reflect the user's Graph Settings
Both export paths (canvas-as-is and graphs-separately, SVG and PNG) take the chart's currently-rendered SVG verbatim. With Graph Settings now persisting through the chart's render output, the exported figure shows the user's chosen colours, sizes, shapes, opacity, hollow markers, font size, plot/paper backgrounds, grid colour, grid visibility, and threshold-line visibility — exactly as displayed on screen.

### Audit summary
| Option | Applies live | Persists on re-render | In export | Verdict |
|---|---|---|---|---|
| Marker color | ✅ (was ❌) | ✅ (was ❌) | ✅ (was ❌) | Fixed |
| Marker size | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Marker shape | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Marker opacity | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Hollow markers | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Plot background | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Paper background | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Grid colour | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Grid visibility | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Font size | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Threshold lines (master) | ✅ | ✅ (already worked) | ✅ | Already correct |
| Threshold lines (per-axis FC/FDR) | ✅ | ✅ (was ❌) | ✅ | Fixed |
| Confidence ellipses (PCA) | ✅ | ✅ (already worked) | ✅ | Already correct |

## [4.15.6] — 2026-05-05

### Fixed — colored marker dots now appear in exported legend
The v4.15.5 export rendered the legend's title and labels correctly but the colored marker dots all stacked at the legend's top-left corner (visually missing — hidden behind the title row).

Root cause: SVG elements (the `<svg>` inside each `.gl-marker` span) **don't have `offsetLeft` / `offsetTop` / `offsetParent`** — those are HTML-element-only properties. The export's `_layoutOffsetWithin()` walked up the offsetParent chain starting from the SVG marker, hit `undefined` immediately, and returned `(0, 0)` for every marker. Each dot got positioned at the legend's origin, hidden behind the title.

Fix: read the offset from the wrapping `<span class="gl-marker">` (an HTML element with valid offsets) instead of the SVG marker itself. The marker's inner shape is then translated to the span's layout position. In-app rendering was unaffected because the span's CSS positions the SVG via flexbox layout, not absolute coordinates.

### Added — editable / removable legend title
The "Groups of interest" header is now an editable `contenteditable` element, matching the row labels:

- Click the title to edit; type a custom heading like "Pathway hits" or your project name. Press <kbd>Enter</kbd> to commit, <kbd>Escape</kbd> to revert.
- Clear the text (type and delete it all, then blur) to **hide the title row entirely** — useful when the legend is purely a colour key for a figure caption that already says what it is.
- Or click the small × button next to the title to hide it instantly. Restore the title later by typing into the (still draggable) legend body — the title row reappears on the next render.
- The custom title persists in `state.title` on the legend and round-trips through session save/load and plot duplication. An empty string means "hidden"; `undefined` means "use the default 'Groups of interest'".

CSS now mirrors the `.gl-label` editing affordances: dashed-border on hover, accent-coloured focus highlight via `color-mix(in srgb, var(--accent) 14%, transparent)`. Drag-to-move now skips when the user is actively editing any contenteditable region in the legend (catches both the title and row labels via `e.target.isContentEditable`), so editing doesn't accidentally trigger a drag.

### Export honours the title state
The PNG/SVG legend export skips the title row entirely if `state.title === ''` or the title element's text is empty — no leftover blank rectangle in the figure.

## [4.15.5] — 2026-05-05

### Fixed — GOI legend renders correctly in PNG export, on top of the chart
The v4.15.4 export integration shipped, but had three bugs that made the legend look wrong (or missing) in the PNG export specifically:

1. **CSS `color-mix()` background colours didn't survive the data-URI round-trip.** PNG export serialises the composite SVG to a `data:image/svg+xml,...` URI and renders it via `Image → drawImage`. The image renderer in some environments doesn't accept the modern color-syntax that `getComputedStyle()` returned for our `color-mix(in srgb, var(--surface) 92%, transparent)` background — so the legend rect ended up with no fill, making the legend look blank or transparent. Fixed with a new `_normalizeCssColor()` helper that runs every legend colour through a 1×1 throwaway canvas, which always produces `#rrggbb` or `rgba(r,g,b,a)` — universally supported.

2. **Position math used CSS-transform-scaled values.** Both export paths computed legend position via `legend.getBoundingClientRect()`. When the canvas is zoomed (anything ≠ 100 %), this returns *visual* coordinates (scaled), but the export SVG uses *layout* coordinates (unscaled). Result: legend appeared at the wrong position relative to its chart, or even off the visible export bounds. Fixed with a new `_layoutOffsetWithin(el, ancestor)` helper that walks the offsetParent chain and returns true layout offsets, plus switched to `offsetWidth`/`offsetHeight` for size.

3. **`maxW` was only expanded when the legend extended *below* the chart.** A logic bug — should always expand when the legend extends past the chart's right edge. Result: a wide legend placed in the right portion of a narrow chart was silently clipped from the export. Fixed: `maxW` and per-card height are now both updated unconditionally based on the legend's bounds.

Verified that the legend SVG group is appended **after** the chart's inner SVG content in both export paths, so SVG painter's-algorithm draws it on top of the chart (later siblings = on top).

The transparent-toggle state, custom row labels, hidden rows, marker colours/shapes, and editable title all carry through correctly now.

## [4.15.4] — 2026-05-05

### Fixed — GOI legend now exports correctly
Both export paths previously dropped the `.canvas-goi-legend` overlay entirely:

- **Canvas-as-is export** (`exportCanvasAsSVG` / `exportCanvasAsPNG`) iterated `.canvas-plot` for chart SVG and `.canvas-anno-wrap` for text/line/shape annotations, but never visited the legend div that lives as a sibling inside the plot card.
- **Per-plot export** (`exportAllSVG` / `exportAllPNG`, the default "Export graphs separately" option) iterated `.proker-svg` directly, which is the chart SVG only — it didn't even look at plot cards.

Both are fixed. New `_legendToSVG(legendEl, ox, oy)` helper walks the legend's DOM (background, title, marker SVGs, label text) and emits an equivalent SVG `<g>` block. The buttons (close, bg-toggle, hide) are deliberately skipped because they're UI controls, not figure content.

- Canvas-as-is now collects each plot card's legend (if present) and embeds it in the composite at the right canvas-relative position via the new `type: 'legend'` item in the items list.
- Per-plot export was refactored to iterate `.canvas-plot` cards (via the new `_buildSeparatePlotsSVG()` helper) instead of bare `.proker-svg` elements, so each plot's legend is included immediately below/over its chart, in the same per-card group transform.

The legend's transparent-toggle state, custom row labels, hidden rows, marker colours/shapes, and editable title all carry through to the export verbatim.

### Fixed — inline-edited titles now persist across re-renders and session save/load
Until this release, when a user double-clicked a chart title (or X/Y axis title) and typed a new label, the change was stored only on the live chart instance (`chart._chartTitle`, `chart.xTitle`, `chart.yTitle`). On the next re-render — triggered by anything from a filter change to a freeze/unfreeze toggle to a session reload — `buildEnrichmentConfig` / `buildVolcanoConfig` / etc. would call `setChartTitle(...)` / `setXTitle(...)` / `setYTitle(...)` with their auto-computed defaults and silently wipe the user's edit.

Two coordinated fixes:

1. **Chart engine** (`proker-charts.js`): `_editChartTitle` and `_editAxisTitle` now emit a `titleedit` event with `{kind: 'chart' | 'xaxis' | 'yaxis', value}` after the user commits the edit.
2. **Host page** (`index.html`): the `titleedit` listener writes the new value to `p.config._titleOverrides[kind]` on the plot entry and triggers an autosave. After every `buildXxxConfig` call, `renderPlot` re-applies these overrides via `setChartTitle/setXTitle/setYTitle` and re-renders.

Because `_titleOverrides` lives on `p.config` (which is already serialised whole in the session save), edits round-trip through reload automatically with no extra plumbing. Plot duplication (which deep-clones the config) also carries the overrides to the new copy.

### Already correct (verified)
- **Pinned point labels**: the floating leader-line labels created by clicking a data point have always been saved as `chart.annotations` and round-trip cleanly through session save/load (`canvasPlots[i].annotations`).
- **GOI legend custom labels** (per-row text edits inside a legend) and **GOI custom names** (the sidebar text input, v4.15.1): both already persist via `goiLegend.labels[id]` and `groupsOfInterest[].name` respectively.

## [4.15.3] — 2026-05-05

### Added — canvas-level right-click menu with "Clear canvas"
Right-clicking on **empty canvas space** (i.e. not on a plot, annotation, GOI legend, or zoom control) now opens a small context menu. Items:

- **📝 Add text box** — same as the toolbar `+ Text` button, but discoverable from the canvas itself.
- **➡️ Add line** — same as the toolbar `+ Line` button.
- **🗑️ Clear canvas** *(only shown when there's something to clear)* — wipes everything off the canvas in one action: all plots (with their charts, color overrides, pinned labels, and GOI legends), all text-box / line / shape annotations. The menu item shows a live count of what's about to be removed (e.g. "Clear canvas (3 plots + 2 annotations)").

### Safety — explicit warning modal before clearing
Clear canvas does **not** wipe immediately. It opens a styled modal that:

- Has a red ⚠️ "Clear canvas?" header
- Lists exactly what will be removed, broken down by category (plots, text boxes, line annotations, shape annotations, GOI legends) — so the user knows precisely what they'd lose
- Reminds them: "This cannot be undone. If you want to keep this layout, save the session first (top-right → Save Session) before continuing."
- Has explicit **Cancel** (focused by default — Enter doesn't wipe) and **Clear canvas** (red danger-styled) buttons

Right-clicking on empty canvas with nothing there shows "Canvas is empty" in the menu — the Clear option is omitted entirely. The modal also gracefully falls back to the native `confirm()` dialog if its DOM element is somehow missing.

### Implementation
- `_canvasContents()` inventories the canvas, counting plots and breaking down annotations by type.
- `clearCanvas()` opens the modal with a per-category breakdown.
- `_confirmClearCanvas()` / `_cancelClearCanvas()` handle the modal buttons.
- `_doClearCanvas()` performs the actual wipe: destroys every chart instance, clears `CHARTS` and `CANVAS_PLOTS`, resets `canvas.style.minHeight/minWidth` (the auto-grown values from drag/resize/addPlot), resets viewport scroll, restores the empty-canvas drop hint, refreshes the stats-methods sidebar, and triggers an autosave.
- Context menu attaches via `vp.addEventListener('contextmenu', ...)`. Skips when right-click target is inside `.canvas-plot`, `.canvas-anno-wrap`, `.canvas-zoom-controls`, `.canvas-textbox`, or `.canvas-goi-legend` so each of those keeps their own menu/behavior.
- Reuses the existing `.modal-overlay` / `.modal-box` / `.m-cancel` / `.m-danger` CSS so the styled warning matches the file-conflict modal exactly.

## [4.15.2] — 2026-05-04

### Fixed — GOI legend background now follows the active theme
The GOI legend introduced in v4.15.0 hardcoded its background as `rgba(13,17,23,0.92)` — the dark theme's `--bg` colour with alpha. On any other theme (light, soft, high-contrast, or a custom theme) this rendered as a black-on-light box that looked obviously broken. Same problem with the `:focus` highlight on editable labels (`rgba(0,0,0,0.25)`) and the drop-shadow.

All three are now derived from the active theme's CSS custom properties via `color-mix()`:

- **Background**: `color-mix(in srgb, var(--surface) 92%, transparent)` — matches whichever surface colour the active theme uses (preset or custom). Stays opaque-ish so the legend reads clearly even when overlaid on a busy plot.
- **Editable-label focus highlight**: `color-mix(in srgb, var(--accent) 14%, transparent)` — a subtle tint of the theme's accent colour, so it pops in any colour scheme.
- **Drop shadow**: `color-mix(in srgb, var(--text) 30%, transparent)` — soft on dark themes (text colour is light → faint shadow), more visible on light themes (text colour is dark → solid grey shadow).

The legend now also explicitly inherits `var(--text)` for the editable label text (was inheriting from the parent, which worked but was implicit).

Reactivity: when the user changes theme via the Theme panel, `applyThemeVars` rewrites the CSS variables on `documentElement` and the legend's `color-mix()` declarations recompute automatically — no JS code path touches the legend, no re-render needed. The transparent toggle (◯) still works exactly as before.

Browser support note: `color-mix()` is supported in Chrome 111+, Firefox 113+, Safari 16.2+ (all March 2023 or earlier). Pro-ker doesn't target older browsers, so no fallback is provided.

## [4.15.1] — 2026-05-04

### Added — Groups-of-Interest custom labels (sidebar)
Each GOI in the Analysis-tab sidebar now has an editable **Custom label** text input. Whatever you type there propagates to every legend on the canvas as the row's default label. Leave it blank to fall back to the auto-generated locus tag (`CT_456`, `CT_120–CT_135`, etc.).

This means you can edit a GOI's display name in two complementary places:

- **In the sidebar** (this release): the canonical custom name. Affects every legend everywhere.
- **In any individual legend** (since v4.15.0): a per-legend override that takes precedence over the sidebar name. Useful when you want a different label in one figure than another.

The new `goiName(id, name)` function persists the name in the session save so it round-trips through reload.

### Fixed — session save now tracks plot positions accurately

Three sources of position drift on save/load are addressed:

1. **Plot drag now triggers an autosave.** The chart's drag-to-move handler in `proker-charts.js` previously only updated `wrap.style.left/top` and pushed an undo entry — it never called `autoSaveSession()`. Combined with the user-facing autosave only running from `renderAll()` (which group/processing changes trigger but plot-drag doesn't), this meant a user who dragged a plot then refreshed would see the plot snap back to where it was the last time settings changed. Drag-end now calls `autoSaveSession()`.

2. **Plot resize now triggers an autosave.** Same root cause — `setupPlotResize`'s `mouseup` only resized the chart; no session write. Same fix: `mouseup` now persists.

3. **Canvas-level layout state is now saved and restored.** Sessions previously didn't capture:
   - `canvas.style.minHeight` / `minWidth` — set inline by `addPlotToCanvas`/drag/resize when plots extend past the natural canvas bounds. Without these, a reloaded session would have a small canvas, and plots positioned at e.g. `top: 1500px` would land outside the scrollable area.
   - `canvas-viewport.scrollLeft` / `scrollTop` — the viewer's current scroll position.
   
   Both are now in the new `canvasLayout` block of the session JSON. On restore, `minHeight`/`minWidth` are applied **before** plots are positioned (so they have room to land), and `scrollLeft`/`scrollTop` are applied **after** plots paint (delayed by `200 + N×50 ms`, matching the staggered render timeline).

Drag and resize handlers also auto-grow the canvas's `min-height`/`min-width` if the user drags or resizes a plot past the current bounds — keeping the plot inside the scrollable region for next time.

## [4.15.0] — 2026-05-04

### Added — Groups-of-Interest legend (right-click → "Add GOI legend")
Right-clicking a chart on the canvas now offers an **Add GOI legend** option that drops an editable, draggable legend onto the plot. The legend renders one row per Group of Interest with:

- **A real marker swatch** that matches the GOI's actual rendering on the plot — same colour, same shape (`circle` / `square` / `diamond` / `triangle-up` / `star` / `cross`), and same size as the markers in the chart. SVG, so it stays crisp at any zoom level and exports cleanly with the figure.
- **An inline-editable label.** The default text is the GOI's identifier (e.g. `CT_456` or `CT_120–CT_135`); click the text and type to override. Press <kbd>Enter</kbd> to commit, <kbd>Escape</kbd> to revert. Custom labels persist with the session.
- **A per-row hide button (×).** Hides that single row from this legend without touching the underlying GOI definition. Useful when you want a focused legend that mentions only some of the highlighted groups.
- **A background-toggle (◉ / ◯)** in the top-left corner — switches between an opaque dark panel (default, good for screen) and a transparent overlay (good for figure overlays where you want the plot to show through).
- **A close button (×)** in the top-right corner removes the legend from the plot.

The legend is **fully draggable** anywhere within the plot card. It lives inside the `.canvas-plot` element so it travels with the plot when the plot is duplicated, exported, or restored from a saved session. Position, custom labels, hidden rows, and background-toggle state all round-trip through session save/load.

The legend stays **reactive** to the GOI sidebar: adding, removing, recolouring, resizing, or changing the symbol of a GOI immediately updates every legend on the canvas — both the marker and the default label.

### Implementation
- `proker-charts.js`: new `Add GOI legend` context-menu item that emits a `goilegend` event.
- `index.html`:
  - `_goiMarkerSVG(color, symbol, size)` — pure-JS SVG generator matching every shape the plot engine renders.
  - `addGOILegend(plotId)` — initialises per-plot legend state (`p.goiLegend = {x, y, transparent, hidden, labels}`) and renders.
  - `renderGOILegend(plotId)` — idempotent DOM rendering with mouse-drag, blur-to-save inline editing, per-row hide, and per-legend close.
  - `refreshGOILegends()` — called from `addGroupOfInterest`, `removeGOI`, `goiColor`, `goiSymbol`, `goiSize`.
  - `renderPlot` calls `renderGOILegend(plotId)` at the end so session-restored and duplicated plots show their legends without extra wiring.
  - Session save/load and duplicate-plot both deep-clone `goiLegend`.
- CSS: new `.canvas-goi-legend` block with hover-revealed buttons.

## [4.14.4] — 2026-05-04

### Fixed — canvas zoom controls now stay glued to the bottom-right corner
Before this release, the zoom controls (`−` `100%` `+` `Fit` `1:1`) lived inside `#canvas-viewport`, which is a `position: relative; overflow: auto` container. With `position: absolute; bottom: 12px; right: 12px`, that anchored them to the **content box** of the scrollable canvas, not the visible viewport. As soon as the canvas grew beyond the viewport (i.e. after zooming in or adding a few plots), the controls drifted to the bottom-right of the entire scrollable region — so panning could move them anywhere on screen, including the middle.

Fix: moved the `.canvas-zoom-controls` element out of `#canvas-viewport` and into `#canvas-wrap`, then added `position: relative` to `#canvas-wrap`. The wrap has `overflow: hidden` and is the same fixed size as the visible viewport area, so the absolutely-positioned controls now anchor to its bottom-right corner permanently — independent of zoom level, scroll position, or canvas size.

## [4.14.3] — 2026-05-04

### Added — duplicate plot (right-click → "Duplicate plot (with labels)")
Right-clicking a chart on the canvas now offers a **Duplicate plot (with labels)** option that creates an independent copy of the plot in place. The new copy preserves:

- The plot type and full configuration (group selections, thresholds, imputation method, statistical test, axis ranges, etc. — everything stored in `config`).
- All pinned point labels with their text, anchor positions, and leader-line offsets.
- All per-point color overrides (custom colors set via right-click → "Color selected" or the toolbar swatch).
- The frozen state (a duplicate of a frozen plot is also frozen, with the same data snapshot).
- The card's width and height; positioned 30 px down/right of the original so it's immediately visible without overlapping completely.

The duplicate is fully independent — modifying one (e.g. adding more labels, changing settings) does not affect the other. Useful for trying out alternative settings without losing the original, or producing two side-by-side variants of the same data for figure layouts.

Implementation: `chart.on('duplicate')` event from the context menu invokes `duplicatePlot(plotId)`, which deep-clones the plot's `config`, allocates a fresh `plotId`, builds an offset card, calls `renderPlot()`, then transfers `annotations` and `_colorOverrides` from the source chart instance to the new one and re-renders. Force-update is set so a frozen duplicate still populates initially.

## [4.14.2] — 2026-05-04

### Changed — pinned-label leader lines
- **Solid by default** instead of dashed (`stroke-dasharray="3,2"` removed). Cleaner look in figures and reduces visual noise when many labels are pinned.
- **Stops at the text bounding-box edge** instead of running into the centre of the label. The leader line now terminates at a 3 px gap before the text glyphs, computed via slab-method ray–AABB intersection on the text's bounding rectangle. No more lines visibly crossing into letters.
- Slight opacity (0.85) added so a long line behind a busy chart isn't visually overwhelming.

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
