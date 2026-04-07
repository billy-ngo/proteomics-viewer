"""
Pro-ker plot generation via Bokeh.

Each function returns a Bokeh figure as json_item() dict, ready for
embedding in the browser with Bokeh.embed.embed_item().
"""

from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource, HoverTool, TapTool, LabelSet,
    Range1d, LinearAxis, Title, CustomJS,
    WheelZoomTool, PanTool, BoxSelectTool, ResetTool, SaveTool,
)
from bokeh.embed import json_item
from bokeh.palettes import RdBu11
import math


# ── Theme ────────────────────────────────────────────────────────
DARK_THEME = dict(
    bg='#0d1117', plot='#161b22', grid='#21262d', line='#30363d',
    text='#e6edf3', text_sec='#8b949e', accent='#58a6ff',
    dot='#e6edf3', danger='#f85149', success='#3fb950',
)


def _apply_theme(fig, theme=None):
    """Apply dark theme styling to a Bokeh figure."""
    t = theme or DARK_THEME
    fig.background_fill_color = t['plot']
    fig.border_fill_color = t['bg']
    fig.outline_line_color = t['line']
    fig.xaxis.axis_line_color = t['line']
    fig.yaxis.axis_line_color = t['line']
    fig.xaxis.major_tick_line_color = t['line']
    fig.yaxis.major_tick_line_color = t['line']
    fig.xaxis.minor_tick_line_color = None
    fig.yaxis.minor_tick_line_color = None
    fig.xaxis.major_label_text_color = t['text_sec']
    fig.yaxis.major_label_text_color = t['text_sec']
    fig.xaxis.axis_label_text_color = t['text']
    fig.yaxis.axis_label_text_color = t['text']
    fig.xaxis.axis_label_text_font_style = 'bold'
    fig.yaxis.axis_label_text_font_style = 'bold'
    fig.xaxis.axis_label_text_font_size = '12px'
    fig.yaxis.axis_label_text_font_size = '12px'
    fig.xaxis.major_label_text_font_size = '10px'
    fig.yaxis.major_label_text_font_size = '10px'
    fig.xgrid.grid_line_color = t['grid']
    fig.ygrid.grid_line_color = t['grid']
    fig.xgrid.grid_line_alpha = 0.4
    fig.ygrid.grid_line_alpha = 0.4
    fig.title.text_color = t['text']
    fig.title.text_font_size = '13px'
    fig.min_border_left = 60
    fig.min_border_bottom = 55


def _base_tools():
    """Standard tool set — no scroll zoom, no pan, just hover + tap + save."""
    return 'hover,tap,save,reset'


# ── Enrichment Plot ──────────────────────────────────────────────
def make_enrichment(data, x_label='Rank', y_label='Enrichment', title=''):
    """
    data: list of dicts with keys: rank, value, label, full_label, hover
    """
    source = ColumnDataSource(data={
        'x': [d['rank'] for d in data],
        'y': [d['value'] for d in data],
        'label': [d['label'] for d in data],
        'full_label': [d.get('full_label', '') for d in data],
        'hover': [d.get('hover', '') for d in data],
    })

    fig = figure(
        width=700, height=420,
        x_axis_label=x_label, y_axis_label=y_label,
        tools=_base_tools(), active_drag=None,
        sizing_mode='stretch_both',
    )

    fig.circle('x', 'y', source=source, size=5, color=DARK_THEME['dot'],
               alpha=0.8, selection_color=DARK_THEME['accent'],
               nonselection_alpha=0.4)

    fig.hover.tooltips = [("", "@hover{safe}")]
    fig.hover.mode = 'mouse'

    _apply_theme(fig)
    return json_item(fig)


# ── Unique Proteins Plot ─────────────────────────────────────────
def make_unique(data, color='#58a6ff', y_label='Abundance', title=''):
    """
    data: list of dicts with keys: x (jittered), y (abundance), label, full_label
    """
    source = ColumnDataSource(data={
        'x': [d['x'] for d in data],
        'y': [d['y'] for d in data],
        'label': [d['label'] for d in data],
        'full_label': [d.get('full_label', '') for d in data],
    })

    fig = figure(
        width=320, height=420,
        y_axis_label=y_label,
        tools=_base_tools(), active_drag=None,
        sizing_mode='stretch_height',
    )

    fig.circle('x', 'y', source=source, size=7, color=color,
               alpha=0.8, selection_color=DARK_THEME['accent'],
               line_color='rgba(255,255,255,0.2)', line_width=0.5)

    fig.xaxis.visible = False
    fig.xgrid.visible = False
    fig.x_range = Range1d(-0.5, 0.5)

    fig.hover.tooltips = [("", "@label"), ("Abundance", "@y{0,0}")]
    fig.hover.mode = 'mouse'

    _apply_theme(fig)
    return json_item(fig)


# ── Volcano Plot ─────────────────────────────────────────────────
def make_volcano(ns_data, up_data, down_data, up_color, down_color,
                 fc_thresh=1.0, fdr_thresh=0.05,
                 x_label='Log2 Fold Change', y_label='-Log10(FDR adj. P-value)'):
    """
    Each *_data is a list of dicts: {x, y, label, full_label, hover}
    """
    fig = figure(
        width=700, height=420,
        x_axis_label=x_label, y_axis_label=y_label,
        tools=_base_tools(), active_drag=None,
        sizing_mode='stretch_both',
    )

    # NS points
    if ns_data:
        ns_src = ColumnDataSource(data={
            'x': [d['x'] for d in ns_data], 'y': [d['y'] for d in ns_data],
            'label': [d['label'] for d in ns_data], 'hover': [d.get('hover', '') for d in ns_data],
            'full_label': [d.get('full_label', '') for d in ns_data],
        })
        fig.circle('x', 'y', source=ns_src, size=3, color='#30363d', alpha=0.3)

    # Up points
    if up_data:
        up_src = ColumnDataSource(data={
            'x': [d['x'] for d in up_data], 'y': [d['y'] for d in up_data],
            'label': [d['label'] for d in up_data], 'hover': [d.get('hover', '') for d in up_data],
            'full_label': [d.get('full_label', '') for d in up_data],
        })
        fig.circle('x', 'y', source=up_src, size=5, color=up_color, alpha=0.8,
                   selection_color=DARK_THEME['accent'])

    # Down points
    if down_data:
        dn_src = ColumnDataSource(data={
            'x': [d['x'] for d in down_data], 'y': [d['y'] for d in down_data],
            'label': [d['label'] for d in down_data], 'hover': [d.get('hover', '') for d in down_data],
            'full_label': [d.get('full_label', '') for d in down_data],
        })
        fig.circle('x', 'y', source=dn_src, size=5, color=down_color, alpha=0.8,
                   selection_color=DARK_THEME['accent'])

    # Threshold lines
    from bokeh.models import Span
    fig.add_layout(Span(location=fc_thresh, dimension='height', line_color='#30363d', line_dash='dashed', line_width=1))
    fig.add_layout(Span(location=-fc_thresh, dimension='height', line_color='#30363d', line_dash='dashed', line_width=1))
    fig.add_layout(Span(location=-math.log10(fdr_thresh), dimension='width', line_color='#30363d', line_dash='dashed', line_width=1))

    fig.hover.tooltips = [("", "@hover{safe}")]
    fig.hover.mode = 'mouse'

    _apply_theme(fig)
    return json_item(fig)


# ── Dot Plot (Scatter) ───────────────────────────────────────────
def make_dotplot(traces, x_label='', y_label=''):
    """
    traces: list of dicts, each with:
      x, y, label, full_label, hover, color (single or list), symbol, size, alpha, name
    """
    fig = figure(
        width=700, height=420,
        x_axis_label=x_label, y_axis_label=y_label,
        tools=_base_tools(), active_drag=None,
        sizing_mode='stretch_both',
    )

    for trace in traces:
        source = ColumnDataSource(data={
            'x': trace['x'], 'y': trace['y'],
            'label': trace.get('label', ['']*len(trace['x'])),
            'full_label': trace.get('full_label', ['']*len(trace['x'])),
            'hover': trace.get('hover', ['']*len(trace['x'])),
        })
        color = trace.get('color', DARK_THEME['dot'])
        symbol = trace.get('symbol', 'circle')
        size = trace.get('size', 5)
        alpha = trace.get('alpha', 0.7)

        if symbol == 'circle':
            fig.circle('x', 'y', source=source, size=size, color=color,
                       alpha=alpha, selection_color=DARK_THEME['accent'],
                       legend_label=trace.get('name', ''))
        elif symbol == 'triangle':
            fig.triangle('x', 'y', source=source, size=size, color=color,
                         alpha=alpha, legend_label=trace.get('name', ''))
        elif symbol == 'square':
            fig.square('x', 'y', source=source, size=size, color=color,
                       alpha=alpha, legend_label=trace.get('name', ''))

    # Diagonal line
    if traces and len(traces) > 0:
        all_vals = []
        for t in traces:
            all_vals.extend(t['x'])
            all_vals.extend(t['y'])
        all_vals = [v for v in all_vals if v and abs(v) < 1e10]
        if all_vals:
            mn, mx = min(all_vals), max(all_vals)
            fig.line([mn, mx], [mn, mx], line_color='#30363d', line_dash='dashed', line_width=1)

    fig.hover.tooltips = [("", "@hover{safe}")]
    fig.hover.mode = 'mouse'
    fig.legend.visible = any(t.get('name') for t in traces)
    fig.legend.label_text_color = DARK_THEME['text_sec']
    fig.legend.background_fill_color = DARK_THEME['bg']
    fig.legend.border_line_color = DARK_THEME['line']
    fig.legend.label_text_font_size = '10px'

    _apply_theme(fig)
    return json_item(fig)


# ── PCA Plot ─────────────────────────────────────────────────────
def make_pca(groups_data, x_label='PC1', y_label='PC2'):
    """
    groups_data: list of dicts, each with:
      x, y, names, color, group_name
    """
    fig = figure(
        width=700, height=420,
        x_axis_label=x_label, y_axis_label=y_label,
        tools=_base_tools(), active_drag=None,
        sizing_mode='stretch_both',
    )

    for gd in groups_data:
        source = ColumnDataSource(data={
            'x': gd['x'], 'y': gd['y'],
            'name': gd['names'],
            'group': [gd['group_name']] * len(gd['x']),
        })
        fig.circle('x', 'y', source=source, size=10, color=gd['color'],
                   alpha=0.8, legend_label=gd['group_name'],
                   selection_color=DARK_THEME['accent'])

    fig.hover.tooltips = [("Sample", "@name"), ("Group", "@group"),
                          ("PC1", "@x{0.00}"), ("PC2", "@y{0.00}")]
    fig.hover.mode = 'mouse'
    fig.legend.label_text_color = DARK_THEME['text_sec']
    fig.legend.background_fill_color = DARK_THEME['bg']
    fig.legend.border_line_color = DARK_THEME['line']
    fig.legend.label_text_font_size = '10px'

    _apply_theme(fig)
    return json_item(fig)
