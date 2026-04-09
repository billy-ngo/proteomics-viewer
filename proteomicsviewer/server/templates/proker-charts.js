/**
 * ProkerChart — Custom SVG charting engine for Pro-ker Proteomics Analysis.
 *
 * Uses D3.js only for scale/axis math. All SVG rendering and event handling
 * is custom, giving full control over interactions.
 *
 * Handles hundreds to thousands of data points efficiently.
 */

class ProkerChart {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.getElementById(container) : container;
        this.opts = {
            margin: { top: 30, right: 40, bottom: 55, left: 65 },
            theme: {
                bg: '#0d1117', plot: '#161b22', grid: '#21262d', line: '#30363d',
                text: '#e6edf3', textSec: '#8b949e', accent: '#58a6ff',
                danger: '#f85149', success: '#3fb950',
            },
            ...options
        };
        this.traces = [];
        this.xTitle = '';
        this.yTitle = '';
        this.xRange = null; // null = auto
        this.yRange = null;
        this.annotations = []; // [{x, y, text, key, ax, ay}]
        this.callbacks = {};
        this.svg = null;
        this.tooltip = null;
        this._selBox = null;
        this._selState = { active: false, startX: 0, startY: 0, x0: 0, y0: 0, x1: 0, y1: 0, hasSelection: false };
        this._selPx = null;
        this._zoomed = false;
        this._origXRange = null;
        this._origYRange = null;
        this._refLines = []; // [{axis:'x'|'y', value, color, dash, width, opacity}]

        // Symbol renderers
        this._symbols = {
            circle: (x, y, s) => `<circle cx="${x}" cy="${y}" r="${s}" `,
            square: (x, y, s) => `<rect x="${x-s}" y="${y-s}" width="${s*2}" height="${s*2}" `,
            diamond: (x, y, s) => `<polygon points="${x},${y-s*1.3} ${x+s},${y} ${x},${y+s*1.3} ${x-s},${y}" `,
            cross: (x, y, s) => `<path d="M${x-s},${y}L${x+s},${y}M${x},${y-s}L${x},${y+s}" stroke-width="${Math.max(1.5,s/3)}" fill="none" `,
            'triangle-up': (x, y, s) => `<polygon points="${x},${y-s*1.2} ${x+s},${y+s*.8} ${x-s},${y+s*.8}" `,
            'triangle-right': (x, y, s) => `<polygon points="${x+s*1.2},${y} ${x-s*.8},${y-s} ${x-s*.8},${y+s}" `,
            star: (x, y, s) => {
                let pts = '';
                for (let i = 0; i < 5; i++) {
                    const a1 = (i * 72 - 90) * Math.PI / 180;
                    const a2 = ((i * 72) + 36 - 90) * Math.PI / 180;
                    pts += `${x + s * 1.2 * Math.cos(a1)},${y + s * 1.2 * Math.sin(a1)} ${x + s * 0.5 * Math.cos(a2)},${y + s * 0.5 * Math.sin(a2)} `;
                }
                return `<polygon points="${pts.trim()}" `;
            },
        };
    }

    setData(traces) { this.traces = traces; return this; }
    setXTitle(t) { this.xTitle = t; return this; }
    setYTitle(t) { this.yTitle = t; return this; }
    setChartTitle(t) { this._chartTitle = t; return this; }
    setXRange(min, max) { this.xRange = (min != null && max != null) ? [min, max] : null; this._xManual = !!this.xRange; return this; }
    setYRange(min, max) { this.yRange = (min != null && max != null) ? [min, max] : null; this._yManual = !!this.yRange; return this; }
    setTheme(t) { Object.assign(this.opts.theme, t); return this; }

    on(event, cb) { if (!this.callbacks[event]) this.callbacks[event] = []; this.callbacks[event].push(cb); return this; }
    _emit(event, data) { (this.callbacks[event] || []).forEach(cb => cb(data)); }

    // ── Compute scales ──────────────────────────────────────────
    _computeScales(w, h) {
        const m = this.opts.margin;
        const pw = w - m.left - m.right;
        const ph = h - m.top - m.bottom;

        // Gather all x/y values
        let allX = [], allY = [];
        this.traces.forEach(t => {
            if (t.x) allX.push(...t.x.filter(v => isFinite(v)));
            if (t.y) allY.push(...t.y.filter(v => isFinite(v)));
        });

        let xMin, xMax, yMin, yMax;

        // First pass: determine fixed axis ranges
        if (this.xRange) { [xMin, xMax] = this.xRange; }
        else if (allX.length) { xMin = Math.min(...allX); xMax = Math.max(...allX); const pad = (xMax - xMin) * 0.02 || 0.5; xMin -= pad; xMax += pad; }
        else { xMin = 0; xMax = 1; }

        if (this.yRange) { [yMin, yMax] = this.yRange; }
        else if (allY.length) { yMin = Math.min(...allY); yMax = Math.max(...allY); const pad = (yMax - yMin) * 0.02 || 0.5; yMin -= pad; yMax += pad; }
        else { yMin = 0; yMax = 1; }

        // Auto-fit: if one axis is manual and the other is not, fit the auto axis
        // to the data visible within the manual axis range
        // Skip auto-fit if chart has axis breaks (dotplot) to preserve break structure
        if (this._xManual && !this._yManual && allX.length && !(this._axisBreaks && this._axisBreaks.length)) {
            const visibleY = [];
            this.traces.forEach(t => {
                if (!t.x || !t.y) return;
                for (let i = 0; i < t.x.length; i++) {
                    if (isFinite(t.x[i]) && isFinite(t.y[i]) && t.x[i] >= xMin && t.x[i] <= xMax) visibleY.push(t.y[i]);
                }
            });
            if (visibleY.length) { yMin = Math.min(...visibleY); yMax = Math.max(...visibleY); const pad = (yMax - yMin) * 0.05 || 0.5; yMin -= pad; yMax += pad; }
        }
        if (this._yManual && !this._xManual && allY.length && !(this._axisBreaks && this._axisBreaks.length)) {
            const visibleX = [];
            this.traces.forEach(t => {
                if (!t.x || !t.y) return;
                for (let i = 0; i < t.x.length; i++) {
                    if (isFinite(t.x[i]) && isFinite(t.y[i]) && t.y[i] >= yMin && t.y[i] <= yMax) visibleX.push(t.x[i]);
                }
            });
            if (visibleX.length) { xMin = Math.min(...visibleX); xMax = Math.max(...visibleX); const pad = (xMax - xMin) * 0.05 || 0.5; xMin -= pad; xMax += pad; }
        }

        // Use D3's nice() to get clean axis endpoints
        const xScale = d3.scaleLinear().domain([xMin, xMax]).nice().range([0, pw]);
        const yScale = d3.scaleLinear().domain([yMin, yMax]).nice().range([ph, 0]);

        return { xScale, yScale, pw, ph, m };
    }

    // ── Render ───────────────────────────────────────────────────
    render() {
        const el = this.container;
        if (!el) return this;
        const w = el.clientWidth || 600;
        const h = el.clientHeight || 400;
        const T = this.opts.theme;
        const fs = this._fontSize || 12;
        const tfs = Math.max(8, fs - 1); // tick font size slightly smaller
        const { xScale, yScale, pw, ph, m } = this._computeScales(w, h);

        // Store for interactions
        this._w = w; this._h = h;
        this._xScale = xScale; this._yScale = yScale;
        this._pw = pw; this._ph = ph; this._m = m;
        if (!this._origXRange) this._origXRange = xScale.domain().slice();
        if (!this._origYRange) this._origYRange = yScale.domain().slice();

        // Generate ticks — fewer, cleaner
        const xTicks = xScale.ticks(Math.min(8, Math.max(3, Math.floor(pw / 100))));
        const yTicks = yScale.ticks(Math.min(7, Math.max(3, Math.floor(ph / 60))));
        const xFmt = this._niceFormat(xScale.domain());
        const yFmt = this._niceFormat(yScale.domain());

        // Build SVG
        let svg = `<svg class="proker-svg" width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg" style="font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased">`;

        // Background
        if (!this._transparentBg && !this._hidePaperBg) {
            svg += `<rect width="${w}" height="${h}" fill="${T.bg}" rx="0"/>`;
        }
        if (!this._transparentBg && !this._hidePlotBg) {
            svg += `<rect x="${m.left}" y="${m.top}" width="${pw}" height="${ph}" fill="${T.plot}"/>`;
        }

        // Grid lines (subtle, dashed) — toggle via _showGrid
        if (this._showGrid !== false) {
            svg += `<g class="grid" shape-rendering="crispEdges">`;
            xTicks.forEach(v => { const x = Math.round(m.left + xScale(v)) + 0.5; svg += `<line x1="${x}" y1="${m.top}" x2="${x}" y2="${m.top + ph}" stroke="${T.grid}" stroke-width="0.5" stroke-dasharray="3,3" opacity="0.6"/>`; });
            yTicks.forEach(v => { const y = Math.round(m.top + yScale(v)) + 0.5; svg += `<line x1="${m.left}" y1="${y}" x2="${m.left + pw}" y2="${y}" stroke="${T.grid}" stroke-width="0.5" stroke-dasharray="3,3" opacity="0.6"/>`; });
            svg += `</g>`;
        }

        // Axes lines
        svg += `<g shape-rendering="crispEdges">`;
        svg += `<line x1="${m.left}" y1="${m.top + ph}" x2="${m.left + pw}" y2="${m.top + ph}" stroke="${T.line}" stroke-width="1"/>`;
        svg += `<line x1="${m.left}" y1="${m.top}" x2="${m.left}" y2="${m.top + ph}" stroke="${T.line}" stroke-width="1"/>`;
        svg += `</g>`;

        // X tick marks + labels
        svg += `<g class="x-ticks">`;
        xTicks.forEach(v => {
            const x = Math.round(m.left + xScale(v)) + 0.5;
            svg += `<line x1="${x}" y1="${m.top + ph}" x2="${x}" y2="${m.top + ph + 5}" stroke="${T.line}" stroke-width="1" shape-rendering="crispEdges"/>`;
            svg += `<text x="${x}" y="${m.top + ph + 18}" text-anchor="middle" fill="${T.textSec}" font-size="${tfs}" class="tick-label" data-axis="x" data-val="${v}" style="cursor:pointer">${xFmt(v)}</text>`;
        });
        svg += `</g>`;

        // Y tick marks + labels
        svg += `<g class="y-ticks">`;
        yTicks.forEach(v => {
            const y = Math.round(m.top + yScale(v)) + 0.5;
            svg += `<line x1="${m.left - 5}" y1="${y}" x2="${m.left}" y2="${y}" stroke="${T.line}" stroke-width="1" shape-rendering="crispEdges"/>`;
            svg += `<text x="${m.left - 8}" y="${y + 4}" text-anchor="end" fill="${T.textSec}" font-size="${tfs}" class="tick-label" data-axis="y" data-val="${v}" style="cursor:pointer">${yFmt(v)}</text>`;
        });
        svg += `</g>`;

        // Chart title (centered, draggable)
        if (this._chartTitle) {
            const tx = this._titlePos ? this._titlePos.x : m.left + pw / 2;
            const ty = this._titlePos ? this._titlePos.y : 18;
            svg += `<text x="${tx}" y="${ty}" text-anchor="middle" fill="${T.text}" font-size="${fs+1}" font-weight="400" class="chart-title draggable-text" style="cursor:move">${this._esc(this._chartTitle)}</text>`;
        }

        // X axis title (draggable)
        const xTitleX = this._xTitlePos ? this._xTitlePos.x : m.left + pw / 2;
        const xTitleY = this._xTitlePos ? this._xTitlePos.y : h - 6;
        svg += `<text x="${xTitleX}" y="${xTitleY}" text-anchor="middle" fill="${T.text}" font-size="${fs}" font-weight="400" class="axis-title draggable-text" data-axis="x" style="cursor:move">${this._esc(this.xTitle)}</text>`;

        // Y axis title (rotated, draggable)
        const yTitleX = this._yTitlePos ? this._yTitlePos.x : 15;
        const yTitleY = this._yTitlePos ? this._yTitlePos.y : m.top + ph / 2;
        svg += `<text x="${yTitleX}" y="${yTitleY}" text-anchor="middle" fill="${T.text}" font-size="${fs}" font-weight="400" class="axis-title draggable-text" data-axis="y" transform="rotate(-90,${yTitleX},${yTitleY})" style="cursor:move">${this._esc(this.yTitle)}</text>`;

        // Data points (clip to plot area)
        svg += `<defs><clipPath id="clip-${this._uid()}"><rect x="${m.left}" y="${m.top}" width="${pw}" height="${ph}"/></clipPath></defs>`;
        svg += `<g class="data-layer" clip-path="url(#clip-${this._lastUid})">`;

        this.traces.forEach((trace, ti) => {
            if (!trace.x || !trace.y) return;
            const n = Math.min(trace.x.length, trace.y.length);
            const marker = trace.marker || {};
            const baseSize = marker.size || 5;
            const baseSymbol = marker.symbol || 'circle';
            const opacity = marker.opacity != null ? marker.opacity : 0.8;
            const colors = Array.isArray(marker.color) ? marker.color : null;
            const singleColor = !colors ? (marker.color || T.text) : null;
            const sizes = Array.isArray(marker.size) ? marker.size : null;
            const symbols = Array.isArray(marker.symbol) ? marker.symbol : null;

            // For colorscale mapping
            let colorFn = null;
            if (colors && marker.colorscale) {
                const cmin = marker.cmin != null ? marker.cmin : Math.min(...colors);
                const cmax = marker.cmax != null ? marker.cmax : Math.max(...colors);
                colorFn = v => this._colorscale(v, cmin, cmax, marker.colorscale);
            }

            // Error bars (rendered before markers so they appear underneath)
            if (trace.error && trace.error.y) {
                const errWidth = trace.error.width || 1;
                const capW = trace.error.capWidth || 3;
                const errOp = trace.error.opacity != null ? trace.error.opacity : 0.5;
                const errHasColor = !!trace.error.color;
                const errStaticColor = trace.error.color || singleColor || T.text;
                for (let i = 0; i < n; i++) {
                    const vx = trace.x[i], vy = trace.y[i];
                    if (!isFinite(vx) || !isFinite(vy)) continue;
                    const epx = m.left + xScale(vx);
                    if (epx < m.left || epx > m.left + pw) continue;
                    const lo = trace.error.ymin ? trace.error.ymin[i] : vy - trace.error.y[i];
                    const hi = trace.error.ymax ? trace.error.ymax[i] : vy + trace.error.y[i];
                    if (!isFinite(lo) || !isFinite(hi)) continue;
                    const epy1 = m.top + yScale(lo);
                    const epy2 = m.top + yScale(hi);
                    const cy1 = Math.max(m.top, Math.min(m.top + ph, epy1));
                    const cy2 = Math.max(m.top, Math.min(m.top + ph, epy2));
                    // Per-point color fallback
                    const ec = errHasColor ? errStaticColor : (colors ? colors[i] : errStaticColor);
                    svg += `<line x1="${epx}" y1="${cy1}" x2="${epx}" y2="${cy2}" stroke="${ec}" stroke-width="${errWidth}" opacity="${errOp}"/>`;
                    if (epy2 >= m.top && epy2 <= m.top + ph)
                        svg += `<line x1="${epx-capW}" y1="${cy2}" x2="${epx+capW}" y2="${cy2}" stroke="${ec}" stroke-width="${errWidth}" opacity="${errOp}"/>`;
                    if (epy1 >= m.top && epy1 <= m.top + ph)
                        svg += `<line x1="${epx-capW}" y1="${cy1}" x2="${epx+capW}" y2="${cy1}" stroke="${ec}" stroke-width="${errWidth}" opacity="${errOp}"/>`;
                }
            }

            for (let i = 0; i < n; i++) {
                const vx = trace.x[i], vy = trace.y[i];
                if (!isFinite(vx) || !isFinite(vy)) continue;
                const px = m.left + xScale(vx);
                const py = m.top + yScale(vy);
                if (px < m.left || px > m.left + pw || py < m.top || py > m.top + ph) continue;

                let c = colorFn ? colorFn(colors[i]) : (colors ? colors[i] : singleColor);
                // Apply color overrides from selection coloring
                if (this._colorOverrides) {
                    const ovr = this._colorOverrides.find(o => o.ti === ti && o.i === i);
                    if (ovr) c = ovr.color;
                }
                const ptSize = sizes ? sizes[i] : baseSize;
                const ptSymbol = symbols ? symbols[i] : baseSymbol;
                const symFn = this._symbols[ptSymbol] || this._symbols.circle;
                const hoverText = trace.text ? trace.text[i] || '' : '';
                const customData = trace.customdata ? trace.customdata[i] || '' : '';

                const isHollow = marker._hollow;
                const attrs = `class="data-pt" data-ti="${ti}" data-i="${i}" data-x="${vx}" data-y="${vy}" data-hover="${this._esc(hoverText)}" data-custom="${this._esc(customData)}" style="cursor:pointer"`;
                // Invisible hit area for small points (min 8px radius)
                const minHit = 8;
                if (ptSize < minHit) {
                    svg += `<circle cx="${px}" cy="${py}" r="${minHit}" fill="transparent" stroke="none" ${attrs}/>`;
                }
                if (ptSymbol === 'cross') {
                    svg += symFn(px, py, ptSize) + `stroke="${c}" opacity="${opacity}" ${attrs}/>`;
                } else if (isHollow) {
                    svg += symFn(px, py, ptSize) + `fill="none" stroke="${c}" stroke-width="1.5" opacity="${opacity}" ${attrs}/>`;
                } else {
                    svg += symFn(px, py, ptSize) + `fill="${c}" fill-opacity="${opacity}" stroke="${T.plot}" stroke-width="1" ${attrs}/>`;
                }
            }
        });
        svg += `</g>`;

        // Diagonal y=x reference line (for dot plots)
        if (this._diagonalLine) {
            const domain = xScale.domain();
            const mn = Math.max(domain[0], yScale.domain()[0]);
            const mx = Math.min(domain[1], yScale.domain()[1]);
            if (mn < mx) {
                const x1 = m.left + xScale(mn), y1 = m.top + yScale(mn);
                const x2 = m.left + xScale(mx), y2 = m.top + yScale(mx);
                svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${T.text}" stroke-width="0.8" opacity="0.4" stroke-dasharray="none"/>`;
            }
        }

        // Reference lines (threshold lines, etc.) — hidden when _showRefLines === false
        if (this._refLines && this._refLines.length && this._showRefLines !== false) {
            this._refLines.forEach(rl => {
                if (rl._hidden) return;
                const c = rl.color || T.textSec;
                const dash = rl.dash || '5,4';
                const w = rl.width || 1;
                const op = rl.opacity != null ? rl.opacity : 0.7;
                if (rl.axis === 'x') {
                    const px = m.left + xScale(rl.value);
                    if (px >= m.left && px <= m.left + pw)
                        svg += `<line x1="${px}" y1="${m.top}" x2="${px}" y2="${m.top + ph}" stroke="${c}" stroke-width="${w}" stroke-dasharray="${dash}" opacity="${op}"/>`;
                } else {
                    const py = m.top + yScale(rl.value);
                    if (py >= m.top && py <= m.top + ph)
                        svg += `<line x1="${m.left}" y1="${py}" x2="${m.left + pw}" y2="${py}" stroke="${c}" stroke-width="${w}" stroke-dasharray="${dash}" opacity="${op}"/>`;
                }
            });
        }

        // Annotation layer (rendered after data so on top)
        svg += `<g class="annotation-layer">`;
        this.annotations.forEach((ann, ai) => {
            const px = m.left + xScale(ann.x);
            const py = m.top + yScale(ann.y);
            const ax = ann.ax || 30;
            const ay = ann.ay || -25;
            const lx = px + ax, ly = py + ay;
            // Truncate long labels
            const rawLines = String(ann.text).split('\n');
            const lines = rawLines.map(l => l.length > 30 ? l.slice(0, 28) + '...' : l);
            const lineH = 14;
            const textW = Math.max(...lines.map(l => l.length * 7)) + 16;
            const textH = lines.length * lineH + 10;

            svg += `<g class="ann" data-key="${this._esc(ann.key)}" data-ai="${ai}">`;
            svg += `<line x1="${px}" y1="${py}" x2="${lx}" y2="${ly}" stroke="${T.textSec}" stroke-width="0.8" stroke-dasharray="3,2"/>`;
            svg += `<circle cx="${px}" cy="${py}" r="2.5" fill="${T.accent}" opacity="0.7"/>`;
            lines.forEach((line, li) => {
                svg += `<text x="${lx}" y="${ly + li * lineH}" text-anchor="middle" fill="${T.text}" font-size="10.5" font-weight="400">${this._esc(line)}</text>`;
            });
            svg += `</g>`;
        });
        svg += `</g>`;

        // Axis break indicators (double slash marks on axis)
        if (this._axisBreaks && this._axisBreaks.length) {
            this._axisBreaks.forEach(brk => {
                if (brk.axis === 'y') {
                    const by = m.top + yScale(brk.pos);
                    // Double diagonal slash on the Y axis
                    const ax = m.left;
                    svg += `<rect x="${ax-1}" y="${by-4}" width="${pw+2}" height="8" fill="${T.bg || T.plot}"/>`;
                    svg += `<line x1="${ax-4}" y1="${by+3}" x2="${ax+4}" y2="${by-3}" stroke="${T.line}" stroke-width="1.5"/>`;
                    svg += `<line x1="${ax-1}" y1="${by+3}" x2="${ax+7}" y2="${by-3}" stroke="${T.line}" stroke-width="1.5"/>`;
                } else if (brk.axis === 'x') {
                    const bx = m.left + xScale(brk.pos);
                    const ay = m.top + ph;
                    svg += `<rect x="${bx-4}" y="${m.top-1}" width="8" height="${ph+2}" fill="${T.bg || T.plot}"/>`;
                    svg += `<line x1="${bx-3}" y1="${ay+4}" x2="${bx+3}" y2="${ay-4}" stroke="${T.line}" stroke-width="1.5"/>`;
                    svg += `<line x1="${bx-3}" y1="${ay+7}" x2="${bx+3}" y2="${ay-1}" stroke="${T.line}" stroke-width="1.5"/>`;
                }
            });
        }

        // Selection box placeholder
        svg += `<rect class="sel-box" x="0" y="0" width="0" height="0" fill="rgba(88,166,255,0.1)" stroke="${T.accent}" stroke-width="1.5" stroke-dasharray="4" display="none"/>`;

        svg += `</svg>`;

        el.innerHTML = svg;
        this.svg = el.querySelector('.proker-svg');
        this._attachEvents();
        return this;
    }

    // ── Events ───────────────────────────────────────────────────
    _attachEvents() {
        const svg = this.svg;
        if (!svg) return;

        // Tooltip
        this._ensureTooltip();

        // Data point hover + click
        svg.querySelectorAll('.data-pt').forEach(pt => {
            pt.style.cursor = 'pointer';
            pt.addEventListener('mouseenter', e => {
                const text = pt.dataset.hover || '';
                if (text) this._showTooltip(e, text.replace(/&lt;br&gt;/g, '<br>').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
            });
            pt.addEventListener('mouseleave', () => this._hideTooltip());
            pt.addEventListener('click', e => {
                e.stopPropagation();
                const x = parseFloat(pt.dataset.x), y = parseFloat(pt.dataset.y);
                const ti = parseInt(pt.dataset.ti), i = parseInt(pt.dataset.i);
                const custom = pt.dataset.custom || pt.dataset.hover || '';
                const label = custom.replace(/&lt;br&gt;/g, '\n').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
                // Highlight selected point
                svg.querySelectorAll('.data-pt-selected').forEach(s => s.classList.remove('data-pt-selected'));
                pt.classList.add('data-pt-selected');
                pt.setAttribute('stroke', this.opts.theme.accent);
                pt.setAttribute('stroke-width', '2.5');
                // Get current color
                const color = pt.getAttribute('fill') || '#e6edf3';
                this._emit('pointselect', { x, y, ti, i, color, text: label, element: pt, plotId: this.container?.id });
                this._toggleAnnotation(x, y, label);
            });
        });

        // Draggable text elements (titles) — drag to move, click to edit
        svg.querySelectorAll('.draggable-text').forEach(el => {
            let dragging = false, startMX, startMY, origX, origY, moved = false;
            el.addEventListener('mousedown', e => {
                e.stopPropagation();
                dragging = true; moved = false;
                startMX = e.clientX; startMY = e.clientY;
                origX = parseFloat(el.getAttribute('x'));
                origY = parseFloat(el.getAttribute('y'));
                document.body.style.cursor = 'move';
            });
            const onMove = e => {
                if (!dragging) return;
                moved = true;
                const dx = e.clientX - startMX, dy = e.clientY - startMY;
                const nx = origX + dx, ny = origY + dy;
                el.setAttribute('x', nx); el.setAttribute('y', ny);
                // Update transform for rotated Y title
                if (el.getAttribute('transform')) {
                    el.setAttribute('transform', `rotate(-90,${nx},${ny})`);
                }
            };
            const onUp = e => {
                if (!dragging) return;
                dragging = false;
                document.body.style.cursor = '';
                const nx = parseFloat(el.getAttribute('x'));
                const ny = parseFloat(el.getAttribute('y'));
                // Save position
                if (el.classList.contains('chart-title')) this._titlePos = {x:nx,y:ny};
                else if (el.dataset.axis === 'x') this._xTitlePos = {x:nx,y:ny};
                else if (el.dataset.axis === 'y') this._yTitlePos = {x:nx,y:ny};
                // If didn't move much, treat as click → edit and select
                if (!moved || (Math.abs(e.clientX-startMX)<3 && Math.abs(e.clientY-startMY)<3)) {
                    this._emit('titleselect', { element: el });
                    if (el.classList.contains('chart-title')) this._editChartTitle(el);
                    else this._editAxisTitle(el);
                }
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });

        // Tick label click → edit range
        svg.querySelectorAll('.tick-label').forEach(el => {
            el.style.cursor = 'pointer';
            el.addEventListener('click', e => {
                e.stopPropagation();
                this._editRange(el);
            });
        });

        // Annotation drag
        svg.querySelectorAll('.ann').forEach(g => {
            const texts = g.querySelectorAll('text');
            const line = g.querySelector('line');
            const circle = g.querySelector('circle');
            const key = g.dataset.key;
            let dragging = false, startMX, startMY, origAx, origAy;

            // All child elements are drag handles
            [...texts, circle].filter(Boolean).forEach(target => {
                target.style.cursor = 'grab';
                target.addEventListener('mousedown', e => {
                    e.stopPropagation();
                    e.preventDefault();
                    dragging = true;
                    startMX = e.clientX; startMY = e.clientY;
                    const ann = this.annotations.find(a => a.key === key);
                    origAx = ann ? (ann.ax || 30) : 30;
                    origAy = ann ? (ann.ay || -25) : -25;
                    document.body.style.cursor = 'grabbing';
                });
            });

            const onMove = e => {
                if (!dragging) return;
                const dx = e.clientX - startMX, dy = e.clientY - startMY;
                const newAx = origAx + dx, newAy = origAy + dy;
                const px = parseFloat(line.getAttribute('x1'));
                const py = parseFloat(line.getAttribute('y1'));
                const lx = px + newAx, ly = py + newAy;
                line.setAttribute('x2', lx);
                line.setAttribute('y2', ly);
                const tt = g.querySelectorAll('text');
                tt.forEach((t, i) => {
                    t.setAttribute('x', lx);
                    t.setAttribute('y', ly + i * 14);
                });
            };
            const onUp = () => {
                if (!dragging) return;
                dragging = false;
                document.body.style.cursor = '';
                // Persist new position
                const ann = this.annotations.find(a => a.key === key);
                if (ann) {
                    const px = parseFloat(line.getAttribute('x1'));
                    const py = parseFloat(line.getAttribute('y1'));
                    ann.ax = parseFloat(line.getAttribute('x2')) - px;
                    ann.ay = parseFloat(line.getAttribute('y2')) - py;
                }
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });

        // No scroll zoom — user explicitly requested no scroll wheel interaction

        // Right-click context menu (prevent default)
        svg.addEventListener('contextmenu', e => e.preventDefault());

        // Right-click drag selection — only within the plot area
        svg.addEventListener('mousedown', e => {
            if (e.button !== 2) return;
            e.preventDefault();
            this._clearSelection();
            this._closeContextMenu();
            const rect = svg.getBoundingClientRect();
            const scaleX = this._w / rect.width;
            const scaleY = this._h / rect.height;
            const svgX = (e.clientX - rect.left) * scaleX;
            const svgY = (e.clientY - rect.top) * scaleY;
            // Only start selection if cursor is inside the plot area (within margins)
            const m = this._m;
            if (svgX < m.left || svgX > m.left + this._pw || svgY < m.top || svgY > m.top + this._ph) {
                // Outside plot area — show context menu immediately on right-click release
                return;
            }
            this._selState.active = true;
            this._selState.startX = svgX;
            this._selState.startY = svgY;
            this._selScale = { x: scaleX, y: scaleY };
        });

        const onSelMove = e => {
            if (!this._selState.active) return;
            const rect = svg.getBoundingClientRect();
            const sx = this._selScale?.x || 1, sy = this._selScale?.y || 1;
            const cx = (e.clientX - rect.left) * sx, cy = (e.clientY - rect.top) * sy;
            const box = svg.querySelector('.sel-box');
            const x = Math.min(cx, this._selState.startX);
            const y = Math.min(cy, this._selState.startY);
            const w = Math.abs(cx - this._selState.startX);
            const h = Math.abs(cy - this._selState.startY);
            box.setAttribute('x', x); box.setAttribute('y', y);
            box.setAttribute('width', w); box.setAttribute('height', h);
            box.setAttribute('display', 'block');
        };
        document.addEventListener('mousemove', onSelMove);

        document.addEventListener('mouseup', e => {
            if (e.button !== 2 || !this._selState.active) return;
            this._selState.active = false;
            const rect = svg.getBoundingClientRect();
            const scX = this._selScale?.x || 1, scY = this._selScale?.y || 1;
            const cx = (e.clientX - rect.left) * scX, cy = (e.clientY - rect.top) * scY;
            const sx = Math.min(cx, this._selState.startX);
            const sy = Math.min(cy, this._selState.startY);
            const ex = Math.max(cx, this._selState.startX);
            const ey = Math.max(cy, this._selState.startY);

            // Store pixel bounds for accurate hit testing
            this._selPx = { x0: sx, y0: sy, x1: ex, y1: ey };
            // Convert to data coords (for zoom)
            const m = this._m;
            this._selState.x0 = this._xScale.invert(sx - m.left);
            this._selState.x1 = this._xScale.invert(ex - m.left);
            this._selState.y0 = this._yScale.invert(ey - m.top);
            this._selState.y1 = this._yScale.invert(sy - m.top);

            if (Math.abs(cx - this._selState.startX) > 5 || Math.abs(cy - this._selState.startY) > 5) {
                this._selState.hasSelection = true;
            } else {
                // Plain right-click — clear box, show menu
                svg.querySelector('.sel-box').setAttribute('display', 'none');
                this._selState.hasSelection = false;
            }
            this._showContextMenu(e.clientX, e.clientY);
        });

        // Left-click on bg dismisses selection and clears point highlight
        svg.addEventListener('click', () => {
            this._clearSelection();
            this._closeContextMenu();
            svg.querySelectorAll('.data-pt-selected').forEach(s => {
                s.classList.remove('data-pt-selected');
                s.setAttribute('stroke', this.opts.theme.plot);
                s.setAttribute('stroke-width', '1');
            });
            this._emit('pointdeselect', {});
        });

        // Left-click drag on plot background → move entire plot on canvas
        {
            let dragging = false, startMX, startMY, origL, origT;
            const plotBgRect = svg.querySelector('rect'); // first rect is the background
            if (plotBgRect) {
                plotBgRect.style.cursor = 'grab';
                plotBgRect.addEventListener('mousedown', e => {
                    if (e.button !== 0) return;
                    if (e.target.closest('.data-pt,.axis-title,.chart-title,.tick-label,.ann')) return;
                    const wrap = this.container.closest('.canvas-plot');
                    if (!wrap) return;
                    dragging = true;
                    startMX = e.clientX; startMY = e.clientY;
                    origL = parseFloat(wrap.style.left) || 0;
                    origT = parseFloat(wrap.style.top) || 0;
                    document.body.style.cursor = 'grabbing';
                    e.preventDefault();
                });
            }
            document.addEventListener('mousemove', e => {
                if (!dragging) return;
                const wrap = this.container.closest('.canvas-plot');
                if (!wrap) return;
                // Get canvas zoom scale to convert screen pixels to canvas coords
                const scale = typeof canvasScale !== 'undefined' ? canvasScale : 1;
                wrap.style.left = (origL + (e.clientX - startMX) / scale) + 'px';
                wrap.style.top = (origT + (e.clientY - startMY) / scale) + 'px';
            });
            document.addEventListener('mouseup', () => {
                if (dragging) {
                    dragging = false; document.body.style.cursor = '';
                    const wrap = this.container.closest('.canvas-plot');
                    if (wrap && typeof pushUndo === 'function') {
                        const newL = parseFloat(wrap.style.left)||0, newT = parseFloat(wrap.style.top)||0;
                        if (newL !== origL || newT !== origT) {
                            pushUndo('moveGraph', { plotId: this.container.id, oldL: origL, oldT: origT, newL, newT });
                        }
                    }
                }
            });
        }

        // Double-click → emit for graph settings
        svg.addEventListener('dblclick', e => {
            e.preventDefault();
            this._emit('dblclick', {});
        });
    }

    // ── Tooltip ──────────────────────────────────────────────────
    _ensureTooltip() {
        if (!this.tooltip) {
            this.tooltip = document.createElement('div');
            this.tooltip.style.cssText = 'position:fixed;z-index:500;background:var(--card,#21262d);border:1px solid var(--border,#30363d);color:var(--text,#e6edf3);padding:6px 10px;border-radius:4px;font-size:11px;line-height:1.5;pointer-events:none;display:none;max-width:300px;box-shadow:0 4px 12px rgba(0,0,0,0.4);font-family:Inter,system-ui,sans-serif';
            document.body.appendChild(this.tooltip);
        }
    }

    _showTooltip(e, html) {
        this.tooltip.innerHTML = html;
        this.tooltip.style.display = 'block';
        this.tooltip.style.left = (e.clientX + 12) + 'px';
        this.tooltip.style.top = (e.clientY - 10) + 'px';
    }

    _hideTooltip() {
        if (this.tooltip) this.tooltip.style.display = 'none';
    }

    // ── Annotation toggle ────────────────────────────────────────
    _toggleAnnotation(x, y, text) {
        const key = x + '_' + y;
        const plotId = this.container?.id;
        const idx = this.annotations.findIndex(a => a.key === key);
        if (idx >= 0) {
            const removed = this.annotations.splice(idx, 1)[0];
            if (typeof pushUndo === 'function') pushUndo('removeLabel', { plotId, ann: removed });
        } else {
            const i = this.annotations.length;
            const side = (i % 2 === 0) ? 1 : -1;
            const ax = 35 * side + Math.floor(i / 2) * 15 * side;
            const ay = -25 - (i % 3) * 16;
            const displayText = text.split('\n').filter(s => s.trim()).slice(0, 2).join('\n');
            const ann = { x, y, text: displayText, key, ax, ay };
            this.annotations.push(ann);
            if (typeof pushUndo === 'function') pushUndo('addLabel', { plotId, ann: {...ann} });
        }
        this.render();
    }

    addAnnotation(x, y, text, opts = {}) {
        const key = opts.key || (x + '_' + y);
        if (!this.annotations.some(a => a.key === key)) {
            this.annotations.push({ x, y, text, key, ax: opts.ax || 30, ay: opts.ay || -25 });
        }
        this.render();
        return this;
    }

    removeAnnotation(key) {
        this.annotations = this.annotations.filter(a => a.key !== key);
        this.render();
        return this;
    }

    getAnnotations() { return this.annotations.slice(); }

    clearAnnotations() { this.annotations = []; this.render(); return this; }

    // ── Axis title editing ───────────────────────────────────────
    _editChartTitle(el) {
        const current = this._chartTitle || '';
        const rect = el.getBoundingClientRect();
        this._showEditInput(rect, current, v => { this._chartTitle = v; this.render(); });
    }

    // Shared edit input helper
    _showEditInput(rect, current, onCommit) {
        document.querySelectorAll('.proker-edit-input').forEach(e => e.remove());
        const inp = document.createElement('input');
        inp.type = 'text'; inp.value = current;
        inp.className = 'proker-edit-input';
        inp.style.cssText = `position:fixed;z-index:300;font-size:13px;font-family:Inter,system-ui,sans-serif;padding:6px 10px;background:#1a1f29;color:#e6edf3;border:1px solid #58a6ff;border-radius:6px;outline:none;box-shadow:0 4px 16px rgba(0,0,0,0.5);width:${Math.max(160, rect.width + 30)}px;`;
        inp.style.left = (rect.left - 10) + 'px';
        inp.style.top = (rect.top - 8) + 'px';
        document.body.appendChild(inp);
        inp.focus(); inp.select();
        let done = false;
        const commit = () => { if (done) return; done = true; const v = inp.value.trim(); inp.remove(); if (v && v !== current) onCommit(v); };
        inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); commit(); } if (e.key === 'Escape') { done = true; inp.remove(); } });
        inp.addEventListener('blur', commit);
    }

    _editAxisTitle(el) {
        const axis = el.dataset.axis;
        const current = axis === 'x' ? this.xTitle : this.yTitle;
        const rect = el.getBoundingClientRect();
        this._showEditInput(rect, current, v => {
            if (axis === 'x') this.xTitle = v; else this.yTitle = v;
            this.render();
        });
    }

    // ── Range editing (polished popup) ───────────────────────────
    _editRange(el) {
        const axis = el.dataset.axis;
        const domain = axis === 'x' ? this._xScale.domain() : this._yScale.domain();
        const rect = el.getBoundingClientRect();

        document.querySelectorAll('.proker-edit-input').forEach(e => e.remove());
        const div = document.createElement('div');
        div.className = 'proker-edit-input';
        div.style.cssText = 'position:fixed;z-index:300;background:#1a1f29;border:1px solid rgba(88,166,255,0.4);border-radius:8px;padding:12px 14px;box-shadow:0 8px 24px rgba(0,0,0,0.5);font-family:Inter,system-ui,sans-serif';
        div.style.left = Math.max(8, rect.left - 30) + 'px';
        div.style.top = (rect.top - 50) + 'px';

        const fmtVal = v => {
            if (Number.isInteger(v)) return v.toString();
            if (Math.abs(v) >= 100) return v.toFixed(0);
            if (Math.abs(v) >= 1) return v.toFixed(1);
            return v.toPrecision(3);
        };

        div.innerHTML = `
            <div style="font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">${axis === 'x' ? 'X' : 'Y'}-Axis Range</div>
            <div style="display:flex;gap:8px;align-items:center">
                <div style="flex:1">
                    <div style="font-size:9px;color:#656d76;margin-bottom:2px">MIN</div>
                    <input type="number" step="any" value="${fmtVal(domain[0])}" style="width:100%;font-size:12px;font-family:monospace;padding:5px 8px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:4px;outline:none">
                </div>
                <div style="color:#30363d;font-size:16px;padding-top:12px">\u2014</div>
                <div style="flex:1">
                    <div style="font-size:9px;color:#656d76;margin-bottom:2px">MAX</div>
                    <input type="number" step="any" value="${fmtVal(domain[1])}" style="width:100%;font-size:12px;font-family:monospace;padding:5px 8px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:4px;outline:none">
                </div>
            </div>
            <div style="display:flex;gap:6px;margin-top:10px;justify-content:flex-end">
                <button class="range-cancel" style="font-size:11px;padding:4px 12px;background:transparent;color:#8b949e;border:1px solid #30363d;border-radius:4px;cursor:pointer;font-family:inherit">Cancel</button>
                <button class="range-apply" style="font-size:11px;padding:4px 14px;background:#58a6ff;color:#fff;border:none;border-radius:4px;cursor:pointer;font-family:inherit;font-weight:600">Apply</button>
            </div>`;
        document.body.appendChild(div);
        const inputs = div.querySelectorAll('input');
        inputs[0].focus(); inputs[0].select();
        let done = false;
        const commit = () => {
            if (done) return; done = true;
            const mn = parseFloat(inputs[0].value), mx = parseFloat(inputs[1].value);
            div.remove();
            if (isNaN(mn) || isNaN(mx) || mn >= mx) return;
            const oldX = this.xRange ? [...this.xRange] : null;
            const oldY = this.yRange ? [...this.yRange] : null;
            if (axis === 'x') this.setXRange(mn, mx); else this.setYRange(mn, mx);
            this._zoomed = true;
            if (typeof pushUndo === 'function') {
                pushUndo('axisRange', {
                    plotId: this.container?.id,
                    oldX, oldY,
                    newX: this.xRange ? [...this.xRange] : null,
                    newY: this.yRange ? [...this.yRange] : null
                });
            }
            this.render();
        };
        div.querySelector('.range-apply').onclick = commit;
        div.querySelector('.range-cancel').onclick = () => { done = true; div.remove(); };
        inputs.forEach(inp => inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); commit(); } if (e.key === 'Escape') { done = true; div.remove(); } }));
        div.addEventListener('click', e => e.stopPropagation());
    }

    // ── Context menu ─────────────────────────────────────────────
    _showContextMenu(mx, my) {
        this._closeContextMenu();
        const menu = document.createElement('div');
        menu.className = 'rc-context-menu'; menu.id = 'proker-ctx-menu';
        menu.style.left = mx + 'px'; menu.style.top = my + 'px';
        let items = '';

        if (this._selState.hasSelection) {
            items += `<div class="rc-item" data-action="zoom">&#128269; Zoom into selection</div>`;
            items += `<div class="rc-item" data-action="label">&#127991; Label selected points</div>`;
            items += `<div class="rc-item rc-color-row" data-action="color">&#127912; Color selected <span class="rc-color-swatch" style="width:20px;height:20px;border-radius:3px;background:#ff4444;display:inline-block;margin-left:auto;border:1px solid var(--border);cursor:pointer;vertical-align:middle"></span></div>`;
            items += `<div class="rc-sep"></div>`;
        }
        items += `<div class="rc-item" data-action="settings">&#9881; Graph settings</div>`;
        if (this._zoomed) {
            items += `<div class="rc-sep"></div>`;
            items += `<div class="rc-item" data-action="resetzoom">&#8634; Reset zoom</div>`;
        }
        if (this.annotations.length) {
            items += `<div class="rc-sep"></div>`;
            items += `<div class="rc-item" data-action="clearlabels">&#10005; Clear all labels</div>`;
        }
        items += `<div class="rc-item" data-action="resetcolors">&#8634; Reset colors</div>`;
        items += `<div class="rc-sep"></div>`;
        items += `<div class="rc-item" data-action="freeze">${this._frozen?'&#128275; Unfreeze data':'&#128274; Freeze data'}</div>`;
        if (this._frozen) {
            items += `<div class="rc-item" data-action="updatefrozen">&#8635; Update to current data</div>`;
        }
        menu.innerHTML = items;
        document.body.appendChild(menu);

        // Keep in viewport
        const r = menu.getBoundingClientRect();
        if (r.right > window.innerWidth) menu.style.left = (mx - r.width) + 'px';
        if (r.bottom > window.innerHeight) menu.style.top = (my - r.height) + 'px';

        // Action handlers
        menu.querySelectorAll('.rc-item').forEach(item => {
            const colorSwatch = item.querySelector('.rc-color-swatch');
            if (colorSwatch) {
                colorSwatch.addEventListener('click', e => {
                    e.stopPropagation();
                    if (typeof showColorSwatch === 'function') {
                        showColorSwatch(colorSwatch, '#ff4444', color => {
                            this._colorSelected(color);
                            this._closeContextMenu();
                            this._clearSelection();
                        });
                    }
                });
            }
            item.addEventListener('click', e => {
                if (e.target.tagName === 'INPUT' || e.target.classList.contains('rc-color-swatch')) return;
                const action = item.dataset.action;
                if (action === 'zoom') this._zoomToSelection();
                else if (action === 'label') this._labelSelected();
                else if (action === 'settings') this._emit('dblclick', {});
                else if (action === 'resetzoom') this._resetZoom();
                else if (action === 'clearlabels') this.clearAnnotations();
                else if (action === 'resetcolors') this._emit('resetcolors', {});
                else if (action === 'freeze') this._emit('freeze', {});
                else if (action === 'updatefrozen') this._emit('updatefrozen', {});
                this._closeContextMenu();
                if (action !== 'settings') this._clearSelection();
            });
        });

        setTimeout(() => document.addEventListener('click', () => {
            this._closeContextMenu();
        }, { once: true }), 10);
    }

    _closeContextMenu() { document.getElementById('proker-ctx-menu')?.remove(); }

    _clearSelection() {
        this._selState.hasSelection = false;
        this._selPx = null;
        const box = this.svg?.querySelector('.sel-box');
        if (box) box.setAttribute('display', 'none');
    }

    _zoomToSelection() {
        const s = this._selState;
        this.xRange = [s.x0, s.x1]; this._xManual = true;
        this.yRange = [s.y0, s.y1]; this._yManual = true;
        this._zoomed = true;
        this.render();
    }

    _resetZoom() {
        this.xRange = null;
        this.yRange = null;
        this._xManual = false;
        this._yManual = false;
        this._zoomed = false;
        this.render();
    }

    _labelSelected() {
        if (!this._selPx) return;
        const s = this._selState;
        const m = this._m;
        this.traces.forEach(trace => {
            if (!trace.x || !trace.y) return;
            for (let i = 0; i < trace.x.length; i++) {
                const x = trace.x[i], y = trace.y[i];
                if (!isFinite(x) || !isFinite(y)) continue;
                // Convert data point to pixel coords and check against pixel selection bounds
                const px = m.left + this._xScale(x);
                const py = m.top + this._yScale(y);
                if (px >= this._selPx.x0 && px <= this._selPx.x1 && py >= this._selPx.y0 && py <= this._selPx.y1) {
                    const text = trace.customdata?.[i] || trace.text?.[i] || '';
                    if (!text) continue;
                    const key = x + '_' + y;
                    if (!this.annotations.some(a => a.key === key)) {
                        const displayText = String(text).replace(/<[^>]*>/g, '\n').split('\n').filter(s => s.trim()).slice(0, 2).join('\n');
                        const idx = this.annotations.length;
                        this.annotations.push({ x, y, text: displayText, key, ax: 30 * ((idx % 2) ? -1 : 1), ay: -25 - (idx % 3) * 16 });
                    }
                }
            }
        });
        this.render();
    }

    _colorSelected(color) {
        if (!this._selPx) return;
        if (!this._colorOverrides) this._colorOverrides = [];
        const m = this._m;
        const newOverrides = [];
        this.traces.forEach((trace, ti) => {
            if (!trace.x || !trace.y) return;
            for (let i = 0; i < trace.x.length; i++) {
                const x = trace.x[i], y = trace.y[i];
                if (!isFinite(x) || !isFinite(y)) continue;
                const px = m.left + this._xScale(x);
                const py = m.top + this._yScale(y);
                if (px >= this._selPx.x0 && px <= this._selPx.x1 && py >= this._selPx.y0 && py <= this._selPx.y1) {
                    const ovr = { ti, i, color };
                    this._colorOverrides.push(ovr);
                    newOverrides.push(ovr);
                }
            }
        });
        if (newOverrides.length && typeof pushUndo === 'function') {
            pushUndo('colorPoints', { plotId: this.container?.id, overrides: newOverrides });
        }
        this.render();
    }

    // ── Export ────────────────────────────────────────────────────
    toSVG() {
        if (!this.svg) return '';
        return new XMLSerializer().serializeToString(this.svg);
    }

    toPNG(width, height, scale = 2) {
        return new Promise(resolve => {
            const svgStr = this.toSVG();
            const canvas = document.createElement('canvas');
            canvas.width = (width || this._w) * scale;
            canvas.height = (height || this._h) * scale;
            const ctx = canvas.getContext('2d');
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                canvas.toBlob(resolve, 'image/png');
            };
            img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);
        });
    }

    // ── Resize ───────────────────────────────────────────────────
    resize() { this.render(); return this; }

    destroy() {
        if (this.tooltip) { this.tooltip.remove(); this.tooltip = null; }
        if (this.container) this.container.innerHTML = '';
    }

    // ── Helpers ───────────────────────────────────────────────────
    _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

    _uid() { this._lastUid = 'pc' + (ProkerChart._uidCounter = (ProkerChart._uidCounter || 0) + 1); return this._lastUid; }

    _smartFormat(domain) {
        const range = Math.abs(domain[1] - domain[0]);
        if (range === 0) return '.1f';
        if (range > 10000) return '.2s';
        if (range > 100) return '.0f';
        if (range > 1) return '.1f';
        if (range > 0.01) return '.2f';
        return '.3f';
    }

    _niceFormat(domain) {
        const range = Math.abs(domain[1] - domain[0]);
        // Return a function, not a d3.format string
        return (v) => {
            if (v === 0) return '0';
            const abs = Math.abs(v);
            if (abs >= 10000) return d3.format('.2s')(v);
            if (Number.isInteger(v) || (range > 10 && abs >= 1)) return d3.format('.0f')(v);
            if (range > 1) return d3.format('.1f')(v);
            if (range > 0.1) return d3.format('.2f')(v);
            return d3.format('.3f')(v);
        };
    }

    _colorscale(val, cmin, cmax, scale) {
        const t = Math.max(0, Math.min(1, (val - cmin) / (cmax - cmin || 1)));
        // Default blue-gray-red scale
        if (!scale || scale === 'BlueRed') {
            const r = Math.round(t < 0.5 ? 88 + (139 - 88) * t * 2 : 139 + (248 - 139) * (t - 0.5) * 2);
            const g = Math.round(t < 0.5 ? 166 + (148 - 166) * t * 2 : 148 + (81 - 148) * (t - 0.5) * 2);
            const b = Math.round(t < 0.5 ? 255 + (158 - 255) * t * 2 : 158 + (73 - 158) * (t - 0.5) * 2);
            return `rgb(${r},${g},${b})`;
        }
        // Support Plotly-style colorscale arrays
        if (Array.isArray(scale)) {
            for (let i = 0; i < scale.length - 1; i++) {
                if (t >= scale[i][0] && t <= scale[i + 1][0]) {
                    const lt = (t - scale[i][0]) / (scale[i + 1][0] - scale[i][0]);
                    return this._lerpColor(scale[i][1], scale[i + 1][1], lt);
                }
            }
            return scale[scale.length - 1][1];
        }
        return '#8b949e';
    }

    _lerpColor(a, b, t) {
        const parse = c => { const m = c.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i); return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [128, 128, 128]; };
        const ca = parse(a), cb = parse(b);
        const r = Math.round(ca[0] + (cb[0] - ca[0]) * t);
        const g = Math.round(ca[1] + (cb[1] - ca[1]) * t);
        const bl = Math.round(ca[2] + (cb[2] - ca[2]) * t);
        return `rgb(${r},${g},${bl})`;
    }

    // ── Restyle (for graph settings) ─────────────────────────────
    restyle(props) {
        const applyColor = props.color && this.traces.length === 1 && !Array.isArray(this.traces[0]?.marker?.color);
        this.traces.forEach(trace => {
            if (!trace.marker) trace.marker = {};
            if (props.size != null) trace.marker.size = props.size;
            if (props.symbol) trace.marker.symbol = props.symbol;
            if (applyColor) trace.marker.color = props.color;
            if (props.opacity != null) trace.marker.opacity = props.opacity;
            if (props.hollow !== undefined) trace.marker._hollow = props.hollow;
        });
        this.render();
        return this;
    }

    relayout(props) {
        if (props.plotBg) this.opts.theme.plot = props.plotBg;
        else if (props.plotBg === null) this._hidePlotBg = true;
        if (props.plotBg) this._hidePlotBg = false;
        if (props.paperBg) this.opts.theme.bg = props.paperBg;
        else if (props.paperBg === null) this._hidePaperBg = true;
        if (props.paperBg) this._hidePaperBg = false;
        if (props.gridColor) this.opts.theme.grid = props.gridColor;
        if (props.showGrid !== undefined) this._showGrid = props.showGrid;
        if (props.transparentBg !== undefined) this._transparentBg = props.transparentBg;
        if (props.fontSize) this._fontSize = props.fontSize;
        if (props.showRefLines !== undefined) this._showRefLines = props.showRefLines;
        this.render();
        return this;
    }
}
