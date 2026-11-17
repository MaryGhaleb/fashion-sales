#!/usr/bin/env python3
"""
Fashion Sales Analysis
-----------------------
Reads fashion_sales.csv (READ-ONLY) and produces:
  - Summary CSV tables (category, channel, monthly trend, discount)
  - Vector SVG charts (bar, grouped bar, line, pie/donut)
  - A self-contained HTML report with plain-language findings

No third-party dependencies required (pure Python standard library).
The original CSV is never modified.
"""

import csv
import json
import os

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
SRC = "fashion_sales.csv"
OUTDIR = "analysis_output"

# Color palette
C_PRIMARY   = "#4C6EF5"   # blue
C_SECONDARY = "#F76707"   # orange
C_TERTIARY  = "#12B886"   # green
C_QUARTER   = "#E8590C"   # deep orange
C_GREY      = "#ADB5BD"
PALETTE = ["#4C6EF5", "#F76707", "#12B886", "#7048E8", "#F783AC",
           "#15AABF", "#E67700", "#5C7CFA"]

CAT_COLORS = {
    "Dresses":     "#4C6EF5",
    "Denim":       "#12B886",
    "Outerwear":   "#F76707",
    "Footwear":    "#7048E8",
    "Accessories": "#F783AC",
}
CHANNEL_COLORS = {"Online": "#4C6EF5", "Store": "#F76707"}

# ----------------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------------
def load_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

# ----------------------------------------------------------------------------
# Metric helpers
# ----------------------------------------------------------------------------
def fnum(rows, col):
    return [float(r[col]) for r in rows]

def total(rows, col):
    return sum(fnum(rows, col))

def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0

def median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

def pearson(xs, ys):
    n = len(xs)
    if n == 0:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else 0.0

def weighted_avg_price(rows):
    """Revenue / units  == unit-weighted average selling price."""
    u = total(rows, "units_sold")
    return total(rows, "revenue") / u if u else 0.0

def group_by(rows, key):
    g = {}
    for r in rows:
        g.setdefault(r[key], []).append(r)
    return g

# ----------------------------------------------------------------------------
# SVG chart primitives
# ----------------------------------------------------------------------------
def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def _fmt_money(v):
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"

def svg_header(w, h, title, subtitle=""):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{w/2}" y="34" text-anchor="middle" font-size="20" '
        f'font-weight="700" fill="#212529">{_esc(title)}</text>',
    ] + ([f'<text x="{w/2}" y="56" text-anchor="middle" font-size="13" '
          f'fill="#868e96">{_esc(subtitle)}</text>'] if subtitle else [])

def _lerp(c1, c2, t):
    """Linear interpolate between two #rrggbb colors."""
    t = max(0.0, min(1.0, t))
    a = tuple(int(c1[i:i+2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i+2], 16) for i in (1, 3, 5))
    r = tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
    return "#%02x%02x%02x" % r

def heatmap(path, title, row_labels, col_labels, matrix, value_fmt=_fmt_money,
            subtitle="", c_low="#e7f5ff", c_high="#1c4fd8"):
    """Matrix heatmap. matrix[row][col] = value."""
    nrows = len(row_labels)
    ncols = len(col_labels)
    cell_w, cell_h = 190, 64
    left, top = 190, 100
    gap = 6
    w = left + ncols * (cell_w + gap) + 30
    h = top + nrows * (cell_h + gap) + 70
    flat = [v for row in matrix for v in row]
    vmin, vmax = min(flat), max(flat)
    rng = (vmax - vmin) or 1
    out = svg_header(w, h, title, subtitle)
    # column headers
    for j, cl in enumerate(col_labels):
        cx = left + j * (cell_w + gap) + cell_w / 2
        out.append(f'<text x="{cx:.1f}" y="{top-14}" text-anchor="middle" '
                   f'font-size="15" font-weight="700" fill="#343a40">{_esc(cl)}</text>')
    # rows
    for i, rl in enumerate(row_labels):
        cy = top + i * (cell_h + gap)
        out.append(f'<text x="{left-16}" y="{cy+cell_h/2+5:.1f}" text-anchor="end" '
                   f'font-size="15" font-weight="600" fill="#343a40">{_esc(rl)}</text>')
        for j in range(ncols):
            v = matrix[i][j]
            t = (v - vmin) / rng
            col = _lerp(c_low, c_high, t)
            x = left + j * (cell_w + gap)
            out.append(f'<rect x="{x}" y="{cy}" width="{cell_w}" height="{cell_h}" '
                       f'rx="8" fill="{col}"/>')
            txt_col = "#ffffff" if t > 0.55 else "#1b2a4a"
            out.append(f'<text x="{x+cell_w/2:.1f}" y="{cy+cell_h/2+6:.1f}" '
                       f'text-anchor="middle" font-size="17" font-weight="700" '
                       f'fill="{txt_col}">{value_fmt(v)}</text>')
    # legend
    ly = top + nrows * (cell_h + gap) + 20
    out.append(f'<text x="{left}" y="{ly+4}" font-size="12" fill="#868e96">Low</text>')
    for k in range(120):
        out.append(f'<rect x="{left+40+k}" y="{ly-8}" width="1" height="16" '
                   f'fill="{_lerp(c_low, c_high, k/119)}"/>')
    out.append(f'<text x="{left+170}" y="{ly+4}" font-size="12" fill="#868e96">High</text>')
    out += svg_footer(w, h)
    with open(path, "w") as f:
        f.write("\n".join(out))

def svg_footer(w, h):
    return [f'<text x="{w-14}" y="{h-10}" text-anchor="end" font-size="11" '
            f'fill="#ced4da">fashion_sales.csv</text>', '</svg>']

def nice_ceil(v):
    """Round up to a pleasant axis maximum."""
    if v <= 0:
        return 1
    import math
    mag = 10 ** int(math.floor(math.log10(v)))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * mag >= v:
            return m * mag
    return 10 * mag

def bar_chart_h(path, title, labels, values, colors, value_fmt=_fmt_money,
                subtitle="", bar_value_fmt=None):
    """Horizontal bar chart. Great for category names."""
    w, h = 900, max(360, 70 * len(labels) + 140)
    left, right, top, bottom = 150, 130, 90, 50
    plot_w = w - left - right
    plot_h = h - top - bottom
    vmax = nice_ceil(max(values) if values else 1)
    n = len(values)
    slot = plot_h / n
    bar_h = min(46, slot * 0.62)
    out = svg_header(w, h, title, subtitle)
    # vertical gridlines + x labels
    import math
    ticks = 5
    for i in range(ticks + 1):
        x = left + plot_w * i / ticks
        val = vmax * i / ticks
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_h}" '
                   f'stroke="#f1f3f5" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{top+plot_h+22}" text-anchor="middle" '
                   f'font-size="11" fill="#868e96">{_fmt_money(val)}</text>')
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = top + i * slot + (slot - bar_h) / 2
        bw = plot_w * (val / vmax)
        col = colors[i] if isinstance(colors, list) else colors
        out.append(f'<rect x="{left}" y="{y:.1f}" width="{max(bw,1):.1f}" '
                   f'height="{bar_h:.1f}" rx="5" fill="{col}"/>')
        out.append(f'<text x="{left-12}" y="{y+bar_h/2+5:.1f}" text-anchor="end" '
                   f'font-size="13" fill="#495057">{_esc(lab)}</text>')
        vtxt = (bar_value_fmt or value_fmt)(val)
        out.append(f'<text x="{left+bw+8:.1f}" y="{y+bar_h/2+5:.1f}" '
                   f'font-size="12" font-weight="600" fill="#343a40">{vtxt}</text>')
    out += svg_footer(w, h)
    with open(path, "w") as f:
        f.write("\n".join(out))

def bar_chart_v(path, title, labels, values, colors, value_fmt=_fmt_money,
                subtitle="", bar_value_fmt=None):
    """Vertical bar chart."""
    w, h = 900, 480
    left, right, top, bottom = 80, 40, 90, 90
    plot_w = w - left - right
    plot_h = h - top - bottom
    vmax = nice_ceil(max(values) if values else 1)
    n = len(values)
    slot = plot_w / n
    bar_w = min(90, slot * 0.6)
    out = svg_header(w, h, title, subtitle)
    ticks = 5
    for i in range(ticks + 1):
        y = top + plot_h - plot_h * i / ticks
        val = vmax * i / ticks
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" '
                   f'stroke="#f1f3f5" stroke-width="1"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" '
                   f'font-size="11" fill="#868e96">{_fmt_money(val)}</text>')
    for i, (lab, val) in enumerate(zip(labels, values)):
        cx = left + i * slot + slot / 2
        bh = plot_h * (val / vmax)
        y = top + plot_h - bh
        col = colors[i] if isinstance(colors, list) else colors
        out.append(f'<rect x="{cx-bar_w/2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                   f'height="{bh:.1f}" rx="5" fill="{col}"/>')
        out.append(f'<text x="{cx:.1f}" y="{top+plot_h+22}" text-anchor="middle" '
                   f'font-size="12" fill="#495057">{_esc(lab)}</text>')
        vtxt = (bar_value_fmt or value_fmt)(val)
        out.append(f'<text x="{cx:.1f}" y="{y-8:.1f}" text-anchor="middle" '
                   f'font-size="12" font-weight="600" fill="#343a40">{vtxt}</text>')
    out += svg_footer(w, h)
    with open(path, "w") as f:
        f.write("\n".join(out))

def grouped_bar_v(path, title, labels, series, colors, value_fmt=_fmt_money,
                  subtitle="", legend=True):
    """Grouped vertical bars. series = {name: [values]} aligned to labels."""
    w, h = 940, 520
    left, right, top, bottom = 90, 40, 100, 95
    plot_w = w - left - right
    plot_h = h - top - bottom
    allvals = [v for vals in series.values() for v in vals]
    vmax = nice_ceil(max(allvals) if allvals else 1)
    n = len(labels)
    ns = len(series)
    slot = plot_w / n
    group_pad = slot * 0.18
    bar_w = (slot - 2 * group_pad) / ns
    out = svg_header(w, h, title, subtitle)
    ticks = 5
    for i in range(ticks + 1):
        y = top + plot_h - plot_h * i / ticks
        val = vmax * i / ticks
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" '
                   f'stroke="#f1f3f5" stroke-width="1"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" '
                   f'font-size="11" fill="#868e96">{_fmt_money(val)}</text>')
    names = list(series.keys())
    for i, lab in enumerate(labels):
        gx = left + i * slot + group_pad
        out.append(f'<text x="{gx+ (slot-2*group_pad)/2:.1f}" y="{top+plot_h+22}" '
                   f'text-anchor="middle" font-size="12" fill="#495057">{_esc(lab)}</text>')
        for j, name in enumerate(names):
            val = series[name][i]
            bh = plot_h * (val / vmax)
            x = gx + j * bar_w
            y = top + plot_h - bh
            col = colors[j] if isinstance(colors, list) else colors
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w-2:.1f}" '
                       f'height="{bh:.1f}" rx="3" fill="{col}"/>')
    # legend
    if legend:
        lx = w - right - ns * 150
        for j, name in enumerate(names):
            col = colors[j] if isinstance(colors, list) else colors
            x = lx + j * 150
            out.append(f'<rect x="{x}" y="70" width="14" height="14" rx="3" fill="{col}"/>')
            out.append(f'<text x="{x+20}" y="82" font-size="13" fill="#495057">{_esc(name)}</text>')
    out += svg_footer(w, h)
    with open(path, "w") as f:
        f.write("\n".join(out))

def line_chart(path, title, x_labels, series, colors, value_fmt=_fmt_money,
               subtitle="", legend=True):
    """Multi-series line chart. series = {name: [values]}."""
    w, h = 980, 520
    left, right, top, bottom = 90, 150, 100, 100
    plot_w = w - left - right
    plot_h = h - top - bottom
    allvals = [v for vals in series.values() for v in vals]
    vmax = nice_ceil(max(allvals) if allvals else 1)
    vmin = 0
    n = len(x_labels)
    out = svg_header(w, h, title, subtitle)
    # horizontal grid + y labels
    ticks = 5
    for i in range(ticks + 1):
        y = top + plot_h - plot_h * i / ticks
        val = vmax * i / ticks
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" '
                   f'stroke="#f1f3f5" stroke-width="1"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" '
                   f'font-size="11" fill="#868e96">{_fmt_money(val)}</text>')
    # x positions
    def xpos(i):
        return left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
    def ypos(v):
        return top + plot_h - plot_h * (v - vmin) / (vmax - vmin if vmax > vmin else 1)
    # x labels (thin out if many)
    step = 1 if n <= 14 else 2
    for i in range(n):
        if i % step == 0 or i == n - 1:
            out.append(f'<text x="{xpos(i):.1f}" y="{top+plot_h+22}" '
                       f'text-anchor="middle" font-size="10" fill="#868e96" '
                       f'transform="rotate(45 {xpos(i):.1f} {top+plot_h+22})">'
                       f'{_esc(x_labels[i])}</text>')
    names = list(series.keys())
    for j, name in enumerate(names):
        vals = series[name]
        pts = " ".join(f"{xpos(i):.1f},{ypos(v):.1f}" for i, v in enumerate(vals))
        col = colors[j] if isinstance(colors, list) else colors
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                   f'stroke-width="2.5" stroke-linejoin="round"/>')
        for i, v in enumerate(vals):
            out.append(f'<circle cx="{xpos(i):.1f}" cy="{ypos(v):.1f}" r="3" fill="{col}"/>')
    if legend:
        lx = w - right - 30
        for j, name in enumerate(names):
            col = colors[j] if isinstance(colors, list) else colors
            y = top + 6 + j * 22
            out.append(f'<line x1="{lx}" y1="{y}" x2="{lx+22}" y2="{y}" stroke="{col}" stroke-width="3"/>')
            out.append(f'<text x="{lx+30}" y="{y+4}" font-size="13" fill="#495057">{_esc(name)}</text>')
    out += svg_footer(w, h)
    with open(path, "w") as f:
        f.write("\n".join(out))

def pie_chart(path, title, labels, values, colors, value_fmt=_fmt_money,
              subtitle="", donut=True):
    """Pie / donut chart with legend."""
    import math
    w, h = 900, 460
    cx, cy = 260, 250
    r_out = 150
    r_in = 90 if donut else 0
    total_v = sum(values) or 1
    out = svg_header(w, h, title, subtitle)
    start = -math.pi / 2
    for lab, val, col in zip(labels, values, colors):
        frac = val / total_v
        ang = frac * 2 * math.pi
        end = start + ang
        large = 1 if ang > math.pi else 0
        x1, y1 = cx + r_out * math.cos(start), cy + r_out * math.sin(start)
        x2, y2 = cx + r_out * math.cos(end), cy + r_out * math.sin(end)
        if donut:
            xi1, yi1 = cx + r_in * math.cos(start), cy + r_in * math.sin(start)
            xi2, yi2 = cx + r_in * math.cos(end), cy + r_in * math.sin(end)
            d = (f"M {x1:.1f} {y1:.1f} A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} "
                 f"L {xi2:.1f} {yi2:.1f} A {r_in} {r_in} 0 {large} 0 {xi1:.1f} {yi1:.1f} Z")
        else:
            d = (f"M {cx} {cy} L {x1:.1f} {y1:.1f} "
                 f"A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} Z")
        out.append(f'<path d="{d}" fill="{col}" stroke="#ffffff" stroke-width="2"/>')
        # percentage label mid-angle
        mid = start + ang / 2
        lr = (r_out + r_in) / 2 if donut else r_out * 0.62
        lx, ly = cx + lr * math.cos(mid), cy + lr * math.sin(mid)
        out.append(f'<text x="{lx:.1f}" y="{ly+4:.1f}" text-anchor="middle" '
                   f'font-size="13" font-weight="700" fill="#ffffff">{frac*100:.0f}%</text>')
        start = end
    # center label (donut)
    if donut:
        out.append(f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="13" '
                   f'fill="#868e96">Total</text>')
        out.append(f'<text x="{cx}" y="{cy+18}" text-anchor="middle" font-size="17" '
                   f'font-weight="700" fill="#212529">{_fmt_money(total_v)}</text>')
    # legend
    lx = 480
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = 150 + i * 34
        out.append(f'<rect x="{lx}" y="{y}" width="16" height="16" rx="3" fill="{colors[i]}"/>')
        out.append(f'<text x="{lx+26}" y="{y+13}" font-size="14" fill="#343a40">{_esc(lab)}</text>')
        out.append(f'<text x="{lx+26}" y="{y+30}" font-size="12" fill="#868e96">'
                   f'{_fmt_money(val)} ({val/total_v*100:.0f}%)</text>')
    out += svg_footer(w, h)
    with open(path, "w") as f:
        f.write("\n".join(out))

# ----------------------------------------------------------------------------
# Analysis
# ----------------------------------------------------------------------------
def analyze(rows):
    result = {}

    # --- Totals ---
    tot_rev = total(rows, "revenue")
    tot_units = total(rows, "units_sold")
    result["totals"] = {
        "revenue": tot_rev,
        "units": tot_units,
        "avg_selling_price": tot_rev / tot_units if tot_units else 0,
        "avg_discount": mean(fnum(rows, "discount_pct")),
        "avg_rating": mean(fnum(rows, "avg_rating")),
        "avg_return_rate": mean(fnum(rows, "return_rate")),
        "n_rows": len(rows),
    }

    # --- By category ---
    cat = group_by(rows, "category")
    result["by_category"] = {}
    for c in cat:
        rs = cat[c]
        result["by_category"][c] = {
            "revenue": total(rs, "revenue"),
            "units": total(rs, "units_sold"),
            "avg_price": weighted_avg_price(rs),
            "avg_discount": mean(fnum(rs, "discount_pct")),
            "avg_rating": mean(fnum(rs, "avg_rating")),
            "avg_return_rate": mean(fnum(rs, "return_rate")),
            "ad_spend": total(rs, "ad_spend"),
        }

    # --- By channel ---
    ch = group_by(rows, "channel")
    result["by_channel"] = {}
    for c in ch:
        rs = ch[c]
        result["by_channel"][c] = {
            "revenue": total(rs, "revenue"),
            "units": total(rs, "units_sold"),
            "avg_price": weighted_avg_price(rs),
            "avg_discount": mean(fnum(rs, "discount_pct")),
            "avg_rating": mean(fnum(rs, "avg_rating")),
            "avg_return_rate": mean(fnum(rs, "return_rate")),
            "ad_spend": total(rs, "ad_spend"),
        }

    # --- Monthly trend ---
    months = sorted(set(r["month"] for r in rows))
    m = {mo: {"revenue": 0.0, "units": 0.0, "Online": 0.0, "Store": 0.0} for mo in months}
    for r in rows:
        mo = r["month"]
        m[mo]["revenue"] += float(r["revenue"])
        m[mo]["units"] += float(r["units_sold"])
        m[mo][r["channel"]] += float(r["revenue"])
    result["months"] = months
    result["monthly"] = m

    # --- Discount analysis (bands) ---
    def band(d):
        d = float(d)
        if d == 0:      return "0% (none)"
        if d <= 15:     return "1-15%"
        if d <= 25:     return "16-25%"
        if d <= 35:     return "26-35%"
        return "36-40%"
    bands = ["0% (none)", "1-15%", "16-25%", "26-35%", "36-40%"]
    binit = {b: {"revenue": 0.0, "units": 0.0, "n": 0} for b in bands}
    for r in rows:
        b = band(r["discount_pct"])
        binit[b]["revenue"] += float(r["revenue"])
        binit[b]["units"] += float(r["units_sold"])
        binit[b]["n"] += 1
    result["discount_bands"] = bands
    result["discount_analysis"] = binit

    # --- Correlations ---
    disc = fnum(rows, "discount_pct")
    units = fnum(rows, "units_sold")
    rev = fnum(rows, "revenue")
    rating = fnum(rows, "avg_rating")
    retr = fnum(rows, "return_rate")
    adsp = fnum(rows, "ad_spend")
    result["corr"] = {
        "discount_vs_units": pearson(disc, units),
        "discount_vs_revenue": pearson(disc, rev),
        "rating_vs_return": pearson(rating, retr),
        "rating_vs_units": pearson(rating, units),
        "adspend_vs_revenue": pearson(adsp, rev),
        "adspend_vs_units": pearson(adsp, units),
    }

    # --- Year-over-year growth (revenue by year & category) ---
    years = sorted(set(r["year"] for r in rows))
    ytot = {y: 0.0 for y in years}
    ycat = {y: {} for y in years}
    for r in rows:
        y = r["year"]; rv = float(r["revenue"])
        ytot[y] += rv
        ycat[y][r["category"]] = ycat[y].get(r["category"], 0.0) + rv
    result["years"] = years
    result["revenue_by_year"] = ytot
    result["revenue_by_year_category"] = ycat

    yoy = {}
    if len(years) >= 2:
        y0, y1 = years[0], years[1]
        yoy["from"], yoy["to"] = y0, y1
        yoy["total_growth_pct"] = ((ytot[y1] - ytot[y0]) / ytot[y0] * 100) if ytot[y0] else 0.0
        yoy["by_category"] = {}
        for c in sorted(set(list(ycat[y0].keys()) + list(ycat[y1].keys()))):
            a = ycat[y0].get(c, 0.0); b = ycat[y1].get(c, 0.0)
            g = ((b - a) / a * 100) if a else 0.0
            yoy["by_category"][c] = {"prev": a, "curr": b, "growth_pct": g}
    result["yoy"] = yoy

    # --- Category x Channel heatmap (revenue matrix) ---
    heat_cats = sorted(set(r["category"] for r in rows))
    heat_chans = ["Online", "Store"]
    matrix = []
    for c in heat_cats:
        rowv = []
        for ch in heat_chans:
            s = sum(float(r["revenue"]) for r in rows
                    if r["category"] == c and r["channel"] == ch)
            rowv.append(s)
        matrix.append(rowv)
    result["heatmap"] = {"row_labels": heat_cats, "col_labels": heat_chans, "matrix": matrix}

    # --- Ad-spend ROI by category ---
    roi = {}
    for c in cat:
        rs = cat[c]
        spend = total(rs, "ad_spend")
        rv = total(rs, "revenue")
        roi[c] = {
            "ad_spend": spend,
            "revenue": rv,
            "roas": (rv / spend) if spend else 0.0,      # return on ad spend (x)
            "profit_after_ads": rv - spend,               # revenue left after ad cost
        }
    result["ad_roi"] = roi
    return result

# ----------------------------------------------------------------------------
# Write summary CSVs
# ----------------------------------------------------------------------------
def write_csvs(path, res):
    with open(os.path.join(path, "summary_by_category.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "revenue", "units", "avg_selling_price",
                    "avg_discount_pct", "avg_rating", "avg_return_rate", "ad_spend"])
        for c, d in sorted(res["by_category"].items(), key=lambda x: -x[1]["revenue"]):
            w.writerow([c, round(d["revenue"], 2), d["units"], round(d["avg_price"], 2),
                        round(d["avg_discount"], 2), round(d["avg_rating"], 2),
                        round(d["avg_return_rate"], 4), round(d["ad_spend"], 2)])

    with open(os.path.join(path, "summary_by_channel.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["channel", "revenue", "units", "avg_selling_price",
                    "avg_discount_pct", "avg_rating", "avg_return_rate", "ad_spend"])
        for c, d in sorted(res["by_channel"].items(), key=lambda x: -x[1]["revenue"]):
            w.writerow([c, round(d["revenue"], 2), d["units"], round(d["avg_price"], 2),
                        round(d["avg_discount"], 2), round(d["avg_rating"], 2),
                        round(d["avg_return_rate"], 4), round(d["ad_spend"], 2)])

    with open(os.path.join(path, "monthly_trend.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "total_revenue", "total_units", "online_revenue", "store_revenue"])
        for mo in res["months"]:
            d = res["monthly"][mo]
            w.writerow([mo, round(d["revenue"], 2), d["units"],
                        round(d["Online"], 2), round(d["Store"], 2)])

    with open(os.path.join(path, "discount_analysis.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["discount_band", "transactions", "revenue", "units", "avg_revenue_per_row"])
        for b in res["discount_bands"]:
            d = res["discount_analysis"][b]
            avg_r = d["revenue"] / d["n"] if d["n"] else 0
            w.writerow([b, d["n"], round(d["revenue"], 2), d["units"], round(avg_r, 2)])

    with open(os.path.join(path, "key_metrics.json"), "w") as f:
        json.dump(res, f, indent=2)

    # YoY growth by category
    yoy = res["yoy"]
    with open(os.path.join(path, "yoy_growth_by_category.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", f"{yoy['from']}_revenue", f"{yoy['to']}_revenue", "growth_pct"])
        for c, d in sorted(yoy["by_category"].items(), key=lambda x: -x[1]["growth_pct"]):
            w.writerow([c, round(d["prev"], 2), round(d["curr"], 2), round(d["growth_pct"], 2)])

    # Yearly totals
    with open(os.path.join(path, "revenue_by_year.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "revenue"])
        for y in res["years"]:
            w.writerow([y, round(res["revenue_by_year"][y], 2)])

    # Category x Channel heatmap
    hm = res["heatmap"]
    with open(os.path.join(path, "heatmap_category_channel.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category"] + hm["col_labels"] + ["total"])
        for i, c in enumerate(hm["row_labels"]):
            rowv = hm["matrix"][i]
            w.writerow([c] + [round(v, 2) for v in rowv] + [round(sum(rowv), 2)])

    # Ad-spend ROI by category
    with open(os.path.join(path, "ad_spend_roi_by_category.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "ad_spend", "revenue", "roas_x", "profit_after_ads"])
        for c, d in sorted(res["ad_roi"].items(), key=lambda x: -x[1]["roas"]):
            w.writerow([c, round(d["ad_spend"], 2), round(d["revenue"], 2),
                        round(d["roas"], 2), round(d["profit_after_ads"], 2)])

# ----------------------------------------------------------------------------
# Build charts
# ----------------------------------------------------------------------------
def build_charts(path, res):
    charts = os.path.join(path, "charts")
    os.makedirs(charts, exist_ok=True)

    cats = sorted(res["by_category"].keys())
    cat_rev = [res["by_category"][c]["revenue"] for c in cats]
    cat_units = [res["by_category"][c]["units"] for c in cats]
    cat_price = [res["by_category"][c]["avg_price"] for c in cats]
    cat_disc = [res["by_category"][c]["avg_discount"] for c in cats]
    cat_colors = [CAT_COLORS.get(c, C_PRIMARY) for c in cats]

    # 1. Revenue by category (horizontal)
    order = sorted(range(len(cats)), key=lambda i: -cat_rev[i])
    bar_chart_h(
        os.path.join(charts, "01_revenue_by_category.svg"),
        "Total Revenue by Category",
        [cats[i] for i in order], [cat_rev[i] for i in order],
        [cat_colors[i] for i in order], value_fmt=_fmt_money,
        subtitle="Sum of revenue across 24 months (2024-2025)")

    # 2. Revenue share by category (donut)
    pie_chart(
        os.path.join(charts, "02_revenue_share_category.svg"),
        "Revenue Share by Category",
        cats, cat_rev, cat_colors,
        subtitle="How the total revenue pie is split")

    # 3. Units by category
    bar_chart_v(
        os.path.join(charts, "03_units_by_category.svg"),
        "Units Sold by Category",
        cats, cat_units, cat_colors,
        value_fmt=lambda v: f"{int(v):,}",
        subtitle="Total units sold across 24 months")

    # 4. Channel comparison: revenue & units grouped
    ch_names = ["Online", "Store"]
    ch_colors = [CHANNEL_COLORS["Online"], CHANNEL_COLORS["Store"]]
    ch_rev = [res["by_channel"][c]["revenue"] for c in ch_names]
    ch_units = [res["by_channel"][c]["units"] for c in ch_names]
    bar_chart_v(
        os.path.join(charts, "04_revenue_by_channel.svg"),
        "Total Revenue: Online vs Store",
        ch_names, ch_rev, ch_colors,
        subtitle="Sum of revenue across 24 months")
    bar_chart_v(
        os.path.join(charts, "05_units_by_channel.svg"),
        "Units Sold: Online vs Store",
        ch_names, ch_units, ch_colors,
        value_fmt=lambda v: f"{int(v):,}",
        subtitle="Total units sold across 24 months")

    # 5. Channel share donut
    pie_chart(
        os.path.join(charts, "06_channel_share.svg"),
        "Revenue Share: Online vs Store",
        ch_names, ch_rev, ch_colors,
        subtitle="Share of total revenue by sales channel")

    # 6. Monthly revenue trend (Online vs Store lines)
    months = res["months"]
    online = [res["monthly"][m]["Online"] for m in months]
    store = [res["monthly"][m]["Store"] for m in months]
    line_chart(
        os.path.join(charts, "07_monthly_revenue_trend.svg"),
        "Monthly Revenue Trend (Online vs Store)",
        months, {"Online": online, "Store": store},
        [CHANNEL_COLORS["Online"], CHANNEL_COLORS["Store"]],
        subtitle="Monthly revenue by channel, Jan 2024 - Dec 2025")

    # 7. Monthly total revenue + units (dual info: line for revenue)
    tot_month = [res["monthly"][m]["revenue"] for m in months]
    line_chart(
        os.path.join(charts, "08_monthly_total_revenue.svg"),
        "Monthly Total Revenue Trend",
        months, {"Revenue": tot_month}, [C_PRIMARY],
        subtitle="Total revenue per month across all categories and channels")

    # 8. Avg selling price by category
    bar_chart_h(
        os.path.join(charts, "09_avg_selling_price_by_category.svg"),
        "Average Selling Price by Category",
        cats, cat_price, cat_colors,
        value_fmt=lambda v: f"${v:.2f}",
        subtitle="Unit-weighted average selling price (revenue / units)")

    # 9. Discount analysis: revenue by band
    bands = res["discount_bands"]
    band_rev = [res["discount_analysis"][b]["revenue"] for b in bands]
    band_units = [res["discount_analysis"][b]["units"] for b in bands]
    band_n = [res["discount_analysis"][b]["n"] for b in bands]
    band_colors = ["#ADB5BD", "#74C0FC", "#4C6EF5", "#7048E8", "#F76707"]
    bar_chart_v(
        os.path.join(charts, "10_revenue_by_discount_band.svg"),
        "Revenue by Discount Band",
        bands, band_rev, band_colors,
        subtitle="How revenue distributes across discount levels")

    # 11. Units by discount band
    bar_chart_v(
        os.path.join(charts, "11_units_by_discount_band.svg"),
        "Units Sold by Discount Band",
        bands, band_units, band_colors,
        value_fmt=lambda v: f"{int(v):,}",
        subtitle="How unit sales distribute across discount levels")

    # 12. Avg discount by category
    bar_chart_h(
        os.path.join(charts, "12_avg_discount_by_category.svg"),
        "Average Discount by Category",
        cats, cat_disc, cat_colors,
        value_fmt=lambda v: f"{v:.1f}%",
        subtitle="Mean discount percentage per category")

    # 13. Units vs discount scatter-style (avg units per row per band) as bar
    band_avg_units = [res["discount_analysis"][b]["units"] /
                      res["discount_analysis"][b]["n"]
                      if res["discount_analysis"][b]["n"] else 0 for b in bands]
    bar_chart_v(
        os.path.join(charts, "13_avg_units_per_listing_by_discount.svg"),
        "Average Units per Listing by Discount Band",
        bands, band_avg_units, band_colors,
        value_fmt=lambda v: f"{v:.0f}",
        subtitle="Average units sold per category-month listing at each discount level")

    # 14. Year-over-year revenue by category (grouped bars)
    yoy = res["yoy"]
    y0, y1 = yoy["from"], yoy["to"]
    yoy_cats = sorted(yoy["by_category"].keys(),
                      key=lambda c: -yoy["by_category"][c]["curr"])
    prev_vals = [yoy["by_category"][c]["prev"] for c in yoy_cats]
    curr_vals = [yoy["by_category"][c]["curr"] for c in yoy_cats]
    grouped_bar_v(
        os.path.join(charts, "14_yoy_revenue_by_category.svg"),
        f"Year-over-Year Revenue by Category ({y0} vs {y1})",
        yoy_cats, {str(y0): prev_vals, str(y1): curr_vals},
        ["#ADB5BD", C_PRIMARY],
        subtitle=f"Revenue per category in {y0} vs {y1}")

    # 15. YoY growth % by category (horizontal, can be negative)
    growth_vals = [yoy["by_category"][c]["growth_pct"] for c in yoy_cats]
    gcolors = [C_TERTIARY if g >= 0 else "#E03131" for g in growth_vals]
    bar_chart_h(
        os.path.join(charts, "15_yoy_growth_pct_by_category.svg"),
        f"YoY Revenue Growth % by Category ({y0} \u2192 {y1})",
        yoy_cats, [abs(g) for g in growth_vals], gcolors,
        value_fmt=lambda v: f"{v:.1f}%",
        subtitle="Green = growth, Red = decline. Bar length shows magnitude.")

    # 16. Category x Channel heatmap
    hm = res["heatmap"]
    heatmap(
        os.path.join(charts, "16_heatmap_category_channel.svg"),
        "Revenue Heatmap: Category \u00d7 Channel",
        hm["row_labels"], hm["col_labels"], hm["matrix"],
        subtitle="Darker = more revenue. Each cell is total revenue.")

    # 17. Ad-spend ROI (ROAS) by category
    roi = res["ad_roi"]
    roi_cats = sorted(roi.keys(), key=lambda c: -roi[c]["roas"])
    roas_vals = [roi[c]["roas"] for c in roi_cats]
    roas_colors = [C_TERTIARY if v >= 5 else (C_SECONDARY if v >= 3 else "#E03131")
                   for v in roas_vals]
    bar_chart_h(
        os.path.join(charts, "17_ad_spend_roas_by_category.svg"),
        "Ad-Spend ROI (ROAS) by Category",
        roi_cats, roas_vals, roas_colors,
        value_fmt=lambda v: f"{v:.1f}x",
        subtitle="Revenue earned per $1 of ad spend. Higher is better.")

    # 18. Ad spend vs revenue by category (grouped)
    spend_vals = [roi[c]["ad_spend"] for c in roi_cats]
    rev_vals = [roi[c]["revenue"] for c in roi_cats]
    grouped_bar_v(
        os.path.join(charts, "18_adspend_vs_revenue_by_category.svg"),
        "Ad Spend vs Revenue by Category",
        roi_cats, {"Ad Spend": spend_vals, "Revenue": rev_vals},
        ["#ADB5BD", C_TERTIARY],
        subtitle="Compare marketing investment against the revenue it generates")

    return charts

# ----------------------------------------------------------------------------
# Build HTML report
# ----------------------------------------------------------------------------
def money(v): return f"${v:,.0f}"
def money2(v): return f"${v:,.2f}"
def pct(v, d=1): return f"{v:.{d}f}%"
def num(v): return f"{int(round(v)):,}"

def build_html(path, res):
    charts = "charts"
    t = res["totals"]
    bc = res["by_category"]
    bch = res["by_channel"]
    corr = res["corr"]

    # sort categories by revenue desc
    cat_sorted = sorted(bc.items(), key=lambda x: -x[1]["revenue"])
    top_cat = cat_sorted[0]
    low_cat = cat_sorted[-1]

    online_rev = bch["Online"]["revenue"]
    store_rev = bch["Store"]["revenue"]
    tot_rev = t["revenue"]
    online_share = online_rev / tot_rev * 100
    store_share = store_rev / tot_rev * 100
    lead_ch = "Online" if online_rev >= store_rev else "Store"

    # discount band insight: which band drives most revenue
    band_rev = {b: res["discount_analysis"][b]["revenue"] for b in res["discount_bands"]}
    top_band = max(band_rev, key=band_rev.get)

    # monthly: best/worst month
    mrev = {m: res["monthly"][m]["revenue"] for m in res["months"]}
    best_month = max(mrev, key=mrev.get)
    worst_month = min(mrev, key=mrev.get)

    def cat_table():
        rows_html = ""
        for c, d in cat_sorted:
            rows_html += (
                f"<tr><td><b>{c}</b></td><td>{money(d['revenue'])}</td>"
                f"<td>{num(d['units'])}</td><td>{money2(d['avg_price'])}</td>"
                f"<td>{pct(d['avg_discount'])}</td><td>{d['avg_rating']:.2f}</td>"
                f"<td>{pct(d['avg_return_rate']*100)}</td></tr>"
            )
        return rows_html

    def ch_table():
        rows_html = ""
        for c in ["Online", "Store"]:
            d = bch[c]
            rows_html += (
                f"<tr><td><b>{c}</b></td><td>{money(d['revenue'])}</td>"
                f"<td>{num(d['units'])}</td><td>{money2(d['avg_price'])}</td>"
                f"<td>{pct(d['avg_discount'])}</td><td>{d['avg_rating']:.2f}</td>"
                f"<td>{pct(d['avg_return_rate']*100)}</td></tr>"
            )
        return rows_html

    def discount_table():
        rows_html = ""
        for b in res["discount_bands"]:
            d = res["discount_analysis"][b]
            avg_r = d["revenue"] / d["n"] if d["n"] else 0
            rows_html += (
                f"<tr><td>{b}</td><td>{d['n']}</td><td>{money(d['revenue'])}</td>"
                f"<td>{num(d['units'])}</td><td>{money2(avg_r)}</td></tr>"
            )
        return rows_html

    # --- New-analysis derived values ---
    yoy = res["yoy"]
    y0, y1 = yoy["from"], yoy["to"]
    tot_growth = yoy.get("total_growth_pct", 0.0)
    yoy_cat_sorted = sorted(yoy["by_category"].items(),
                            key=lambda x: -x[1]["growth_pct"])
    best_growth_cat = yoy_cat_sorted[0]
    worst_growth_cat = yoy_cat_sorted[-1]

    roi = res["ad_roi"]
    roi_sorted = sorted(roi.items(), key=lambda x: -x[1]["roas"])
    best_roi_cat = roi_sorted[0]
    worst_roi_cat = roi_sorted[-1]
    tot_ad_spend = sum(d["ad_spend"] for d in roi.values())
    overall_roas = tot_rev / tot_ad_spend if tot_ad_spend else 0.0

    def yoy_table():
        rows_html = ""
        for c, d in yoy_cat_sorted:
            cls = "pos" if d["growth_pct"] >= 0 else "neg"
            rows_html += (
                f'<tr><td><b>{c}</b></td><td>{money(d["prev"])}</td>'
                f'<td>{money(d["curr"])}</td>'
                f'<td class="{cls}">{d["growth_pct"]:+.1f}%</td></tr>'
            )
        return rows_html

    def roi_table():
        rows_html = ""
        for c, d in roi_sorted:
            rows_html += (
                f"<tr><td><b>{c}</b></td><td>{money(d['ad_spend'])}</td>"
                f"<td>{money(d['revenue'])}</td><td><b>{d['roas']:.2f}x</b></td>"
                f"<td>{money(d['profit_after_ads'])}</td></tr>"
            )
        return rows_html

    def heatmap_table():
        hm = res["heatmap"]
        head = "".join(f"<th>{c}</th>" for c in hm["col_labels"])
        body = ""
        for i, c in enumerate(hm["row_labels"]):
            cells = ""
            row = hm["matrix"][i]
            rmax = max(row) if row else 1
            for v in row:
                # inline background intensity
                t = v / rmax if rmax else 0
                bg = _lerp("#e7f5ff", "#1c4fd8", t)
                txt = "#ffffff" if t > 0.55 else "#1b2a4a"
                cells += (f'<td style="background:{bg};color:{txt};'
                          f'font-weight:700">{money(v)}</td>')
            body += f"<tr><td><b>{c}</b></td>{cells}</tr>"
        return head, body

    # KPI cards
    kpis = [
        ("Total Revenue", money(tot_rev), C_PRIMARY),
        ("YoY Revenue Growth", f"{tot_growth:+.1f}%", C_TERTIARY if tot_growth >= 0 else "#E03131"),
        ("Total Units Sold", num(t["units"]), C_TERTIARY),
        ("Avg Selling Price", money2(t["avg_selling_price"]), C_SECONDARY),
        ("Avg Discount", pct(t["avg_discount"]), "#7048E8"),
        ("Overall ROAS", f"{overall_roas:.2f}x", "#0CA678"),
    ]
    kpi_html = "".join(
        f'<div class="kpi" style="border-top:4px solid {col}">'
        f'<div class="kpi-label">{lbl}</div>'
        f'<div class="kpi-value">{val}</div></div>'
        for lbl, val, col in kpis)

    def chart(name, cap):
        return (f'<figure><img src="{charts}/{name}" alt="{cap}"/>'
                f'<figcaption>{cap}</figcaption></figure>')

    # Sign helpers
    def corr_word(v):
        a = abs(v)
        if a < 0.1: strength = "almost no"
        elif a < 0.3: strength = "a weak"
        elif a < 0.5: strength = "a moderate"
        elif a < 0.7: strength = "a fairly strong"
        else: strength = "a strong"
        direction = "positive" if v >= 0 else "negative"
        return f"{strength} {direction}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Fashion Sales Analysis</title>
<style>
  :root {{ --bg:#f8f9fa; --card:#fff; --ink:#212529; --muted:#868e96; --line:#e9ecef; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:'Segoe UI',Helvetica,Arial,sans-serif;
         background:var(--bg); color:var(--ink); line-height:1.55; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:32px 22px 70px; }}
  header.hero {{ text-align:center; padding:26px 0 8px; }}
  header.hero h1 {{ margin:0; font-size:32px; letter-spacing:-0.5px; }}
  header.hero p {{ color:var(--muted); margin:8px 0 0; font-size:15px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:28px 0; }}
  .kpi {{ background:var(--card); border-radius:12px; padding:18px 20px;
          box-shadow:0 1px 3px rgba(0,0,0,.06); }}
  .kpi-label {{ font-size:13px; color:var(--muted); }}
  .kpi-value {{ font-size:24px; font-weight:700; margin-top:6px; }}
  section {{ background:var(--card); border-radius:14px; padding:26px 28px; margin:22px 0;
             box-shadow:0 1px 3px rgba(0,0,0,.06); }}
  section h2 {{ margin:0 0 4px; font-size:22px; }}
  section .lead {{ color:var(--muted); margin:0 0 18px; font-size:14px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:start; }}
  figure {{ margin:0; }}
  figure img {{ width:100%; height:auto; border:1px solid var(--line);
               border-radius:10px; background:#fff; }}
  figcaption {{ font-size:12px; color:var(--muted); text-align:center; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; margin-top:6px; }}
  th, td {{ padding:10px 12px; text-align:right; border-bottom:1px solid var(--line); }}
  th:first-child, td:first-child {{ text-align:left; }}
  thead th {{ background:#f1f3f5; font-weight:600; color:#495057; }}
  tbody tr:hover {{ background:#f8f9fa; }}
  td.pos {{ color:#2f9e44; font-weight:600; }}
  td.neg {{ color:#e03131; font-weight:600; }}
  .finding {{ background:#f1f3f5; border-left:4px solid var(--primary,#4C6EF5);
              border-radius:8px; padding:14px 18px; margin:12px 0; }}
  .finding b {{ color:var(--ink); }}
  ul.findings {{ margin:6px 0 0; padding-left:20px; }}
  ul.findings li {{ margin:8px 0; }}
  .tag {{ display:inline-block; background:#e7f5ff; color:#1971c2; border-radius:999px;
          padding:2px 10px; font-size:12px; font-weight:600; margin-right:6px; }}
  .note {{ font-size:13px; color:var(--muted); margin-top:18px; }}
  footer {{ text-align:center; color:var(--muted); font-size:13px; margin-top:30px; }}
  @media (max-width:820px) {{
    .kpis {{ grid-template-columns:repeat(2,1fr); }}
    .grid2 {{ grid-template-columns:1fr; }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <header class="hero">
    <h1>Fashion Sales Analysis</h1>
    <p>24 months of sales &middot; 5 categories &middot; Online vs Store &middot; Jan 2024 &ndash; Dec 2025</p>
  </header>

  <div class="kpis">{kpi_html}</div>

  <section>
    <h2>Executive Summary</h2>
    <p class="lead">The big picture in plain language.</p>
    <div class="finding">
      <b>{top_cat[0]}</b> is the top category with <b>{money(top_cat[1]['revenue'])}</b> in
      revenue ({top_cat[1]['revenue']/tot_rev*100:.0f}% of the total), while
      <b>{low_cat[0]}</b> is the smallest at {money(low_cat[1]['revenue'])}.
      Overall, <b>{lead_ch}</b> is the stronger channel at
      <b>{max(online_share, store_share):.0f}%</b> of revenue.
      The average selling price is <b>{money2(t['avg_selling_price'])}</b> with an
      average discount of <b>{pct(t['avg_discount'])}</b>.
    </div>
  </section>

  <section>
    <h2>Sales by Category</h2>
    <p class="lead">Which product categories bring in the most revenue and units.</p>
    <div class="grid2">
      {chart("01_revenue_by_category.svg", "Total revenue by category")}
      {chart("02_revenue_share_category.svg", "Share of total revenue by category")}
    </div>
    <div style="margin-top:22px">{chart("03_units_by_category.svg", "Units sold by category")}</div>
    <h3 style="margin:26px 0 6px">Category breakdown</h3>
    <table>
      <thead><tr><th>Category</th><th>Revenue</th><th>Units</th>
        <th>Avg Price</th><th>Avg Disc.</th><th>Rating</th><th>Return Rate</th></tr></thead>
      <tbody>{cat_table()}</tbody>
    </table>
    <div class="finding" style="margin-top:20px">
      <b>What this means:</b> {top_cat[0]} leads on revenue, but the ranking by
      <i>units</i> can differ from the ranking by <i>revenue</i> because higher-priced
      items earn more per unit. Use this table to see which categories are
      "high volume / low price" versus "low volume / high price".
    </div>
  </section>

  <section>
    <h2>Sales by Channel: Online vs Store</h2>
    <p class="lead">How the two sales channels compare.</p>
    <div class="grid2">
      {chart("04_revenue_by_channel.svg", "Revenue by channel")}
      {chart("06_channel_share.svg", "Revenue share by channel")}
    </div>
    <div class="grid2" style="margin-top:22px">
      {chart("05_units_by_channel.svg", "Units sold by channel")}
      <div>
        <table>
          <thead><tr><th>Channel</th><th>Revenue</th><th>Units</th>
            <th>Avg Price</th><th>Disc.</th><th>Ret. Rate</th></tr></thead>
          <tbody>{ch_table()}</tbody>
        </table>
      </div>
    </div>
    <div class="finding" style="margin-top:20px">
      <b>What this means:</b> <b>{lead_ch}</b> generates more revenue
      ({money(max(online_rev, store_rev))} vs {money(min(online_rev, store_rev))}).
      Compare the <i>average selling price</i> and <i>return rate</i> columns to see
      whether one channel sells pricier items or has more returns.
    </div>
  </section>

  <section>
    <h2>Monthly Sales Trends</h2>
    <p class="lead">How sales move month to month across the two years.</p>
    {chart("07_monthly_revenue_trend.svg", "Monthly revenue: Online vs Store")}
    <div style="margin-top:22px">{chart("08_monthly_total_revenue.svg", "Total monthly revenue")}</div>
    <div class="finding" style="margin-top:20px">
      <b>What this means:</b> The strongest month was <b>{best_month}</b>
      ({money(mrev[best_month])}) and the weakest was <b>{worst_month}</b>
      ({money(mrev[worst_month])}). Look for repeating up/down patterns &mdash;
      these are <b>seasonal effects</b> (e.g., colder months lifting Outerwear).
    </div>
  </section>

  <section>
    <h2>Average Selling Price</h2>
    <p class="lead">The typical price customers actually pay, by category.</p>
    {chart("09_avg_selling_price_by_category.svg", "Average selling price by category")}
    <div class="finding" style="margin-top:20px">
      <b>What this means:</b> Average selling price = total revenue &divide; total units.
      It already reflects discounts, so it is the real realized price &mdash; not the
      sticker (list) price. Categories with a high average price contribute more
      revenue per item sold.
    </div>
  </section>

  <section>
    <h2>Discount Analysis</h2>
    <p class="lead">Does discounting actually lift sales, and where does revenue come from?</p>
    <div class="grid2">
      {chart("10_revenue_by_discount_band.svg", "Revenue by discount band")}
      {chart("11_units_by_discount_band.svg", "Units by discount band")}
    </div>
    <div class="grid2" style="margin-top:22px">
      {chart("12_avg_discount_by_category.svg", "Average discount by category")}
      {chart("13_avg_units_per_listing_by_discount.svg", "Avg units per listing by discount band")}
    </div>
    <h3 style="margin:26px 0 6px">Discount band breakdown</h3>
    <table>
      <thead><tr><th>Discount Band</th><th>Listings</th><th>Revenue</th>
        <th>Units</th><th>Avg Rev / Listing</th></tr></thead>
      <tbody>{discount_table()}</tbody>
    </table>
    <div class="finding" style="margin-top:20px">
      <b>What this means:</b> The <b>{top_band}</b> band brings in the most revenue.
      The correlation between discount and units sold is
      <b>{corr['discount_vs_units']:+.2f}</b> ({corr_word(corr['discount_vs_units'])}).
      A value near 0 means bigger discounts are <i>not</i> strongly tied to selling more
      units in this dataset &mdash; a signal that discounting may be eroding margin
      without a clear volume payoff.
    </div>
  </section>

  <section>
    <h2>Year-over-Year Growth</h2>
    <p class="lead">How revenue changed from {y0} to {y1}, overall and by category.</p>
    <div class="finding">
      Total revenue {("grew" if tot_growth >= 0 else "fell")} by
      <b>{tot_growth:+.1f}%</b> from {y0} to {y1}. The fastest-growing category was
      <b>{best_growth_cat[0]}</b> ({best_growth_cat[1]['growth_pct']:+.1f}%), while
      <b>{worst_growth_cat[0]}</b> {("grew the least" if worst_growth_cat[1]['growth_pct'] >= 0 else "declined")}
      ({worst_growth_cat[1]['growth_pct']:+.1f}%).
    </div>
    <div class="grid2" style="margin-top:20px">
      {chart("14_yoy_revenue_by_category.svg", "Revenue by category: " + str(y0) + " vs " + str(y1))}
      {chart("15_yoy_growth_pct_by_category.svg", "YoY growth % by category")}
    </div>
    <h3 style="margin:26px 0 6px">Growth by category</h3>
    <table>
      <thead><tr><th>Category</th><th>{y0} Revenue</th><th>{y1} Revenue</th>
        <th>Growth %</th></tr></thead>
      <tbody>{yoy_table()}</tbody>
    </table>
  </section>

  <section>
    <h2>Category &times; Channel Heatmap</h2>
    <p class="lead">Where revenue concentrates &mdash; which categories sell best in each channel.</p>
    {chart("16_heatmap_category_channel.svg", "Revenue heatmap: category vs channel")}
    <h3 style="margin:26px 0 6px">Revenue matrix</h3>
    <table>
      <thead><tr><th>Category</th>{heatmap_table()[0]}</tr></thead>
      <tbody>{heatmap_table()[1]}</tbody>
    </table>
    <div class="finding" style="margin-top:20px">
      <b>What this means:</b> Each cell is the total revenue for that category in that
      channel. Darker cells = bigger sellers. This quickly reveals, for example, whether a
      category over-indexes Online vs Store.
    </div>
  </section>

  <section>
    <h2>Ad-Spend ROI by Category</h2>
    <p class="lead">Which categories turn marketing dollars into the most revenue?</p>
    <div class="finding">
      Overall, every <b>$1</b> of ad spend returns <b>{overall_roas:.2f}x</b> in revenue
      (ROAS). The most efficient category is <b>{best_roi_cat[0]}</b> at
      <b>{best_roi_cat[1]['roas']:.2f}x</b>; the least efficient is
      <b>{worst_roi_cat[0]}</b> at <b>{worst_roi_cat[1]['roas']:.2f}x</b>.
    </div>
    <div class="grid2" style="margin-top:20px">
      {chart("17_ad_spend_roas_by_category.svg", "ROAS by category")}
      {chart("18_adspend_vs_revenue_by_category.svg", "Ad spend vs revenue by category")}
    </div>
    <h3 style="margin:26px 0 6px">ROI breakdown</h3>
    <table>
      <thead><tr><th>Category</th><th>Ad Spend</th><th>Revenue</th>
        <th>ROAS</th><th>Revenue after Ads</th></tr></thead>
      <tbody>{roi_table()}</tbody>
    </table>
    <p class="note">ROAS (Return on Ad Spend) = revenue &divide; ad spend. An ROAS of 3x means
      each $1 of advertising produced $3 of revenue.</p>
  </section>

  <section>
    <h2>Other Useful Signals</h2>
    <p class="lead">Quick correlations that hint at what drives results.</p>
    <ul class="findings">
      <li><span class="tag">Ratings &rarr; Returns</span>
        Correlation <b>{corr['rating_vs_return']:+.2f}</b> ({corr_word(corr['rating_vs_return'])}).
        {("Higher-rated products tend to get returned less often." if corr['rating_vs_return'] < -0.1
          else "Ratings show little link to return rates here.")}</li>
      <li><span class="tag">Ad Spend &rarr; Revenue</span>
        Correlation <b>{corr['adspend_vs_revenue']:+.2f}</b> ({corr_word(corr['adspend_vs_revenue'])}).
        {("More ad spend is associated with higher revenue &mdash; marketing appears to pay off." if corr['adspend_vs_revenue'] > 0.1
          else "Ad spend is only weakly linked to revenue in this data.")}</li>
      <li><span class="tag">Ad Spend &rarr; Units</span>
        Correlation <b>{corr['adspend_vs_units']:+.2f}</b> ({corr_word(corr['adspend_vs_units'])}).</li>
      <li><span class="tag">Rating &rarr; Units</span>
        Correlation <b>{corr['rating_vs_units']:+.2f}</b> ({corr_word(corr['rating_vs_units'])}).</li>
    </ul>
  </section>

  <section>
    <h2>How to Read This Report</h2>
    <ul class="findings">
      <li><b>Revenue</b> = units sold &times; sale price, summed. It is the top-line sales figure.</li>
      <li><b>Units</b> = number of items sold (volume, ignoring price).</li>
      <li><b>Average Selling Price</b> = total revenue &divide; total units (the real price paid).</li>
      <li><b>Discount %</b> = percent off the list price.</li>
      <li><b>Return Rate</b> = share of items returned (quality / satisfaction signal).</li>
      <li><b>Correlation</b> ranges from &minus;1 to +1: near 0 = no link, near &plusmn;1 = strong link.</li>
    </ul>
    <p class="note">Source data: <code>fashion_sales.csv</code> (240 rows, unmodified).
      This report was generated by <code>sales_analysis.py</code>.
      Charts are available as both vector SVG (in <code>charts/</code>) and
      high-resolution PNG (in <code>charts_png/</code>).</p>
  </section>

  <footer>Generated automatically &middot; Fashion Sales Analysis</footer>
</div>
</body>
</html>"""

    with open(os.path.join(path, "report.html"), "w") as f:
        f.write(html)

# ----------------------------------------------------------------------------
# Plain-language findings summary (Markdown)
# ----------------------------------------------------------------------------
def write_summary(path, res):
    t = res["totals"]
    bc = res["by_category"]
    bch = res["by_channel"]
    corr = res["corr"]
    yoy = res["yoy"]
    roi = res["ad_roi"]
    tot_rev = t["revenue"]

    cat_sorted = sorted(bc.items(), key=lambda x: -x[1]["revenue"])
    top_cat = cat_sorted[0]
    low_cat = cat_sorted[-1]
    online_rev = bch["Online"]["revenue"]
    store_rev = bch["Store"]["revenue"]
    lead_ch = "Online" if online_rev >= store_rev else "Store"
    y0, y1 = yoy["from"], yoy["to"]
    tot_growth = yoy.get("total_growth_pct", 0.0)
    roi_sorted = sorted(roi.items(), key=lambda x: -x[1]["roas"])
    tot_ad = sum(d["ad_spend"] for d in roi.values())
    overall_roas = tot_rev / tot_ad if tot_ad else 0.0

    L = []
    L.append("# Fashion Sales Analysis \u2014 Key Findings\n")
    L.append(f"_Source: `fashion_sales.csv` (240 rows, unmodified). "
             f"Period: Jan {y0} \u2013 Dec {y1}._\n")
    L.append("## At a glance\n")
    L.append("| Metric | Value |")
    L.append("|---|---|")
    L.append(f"| Total revenue | ${tot_rev:,.0f} |")
    L.append(f"| YoY revenue growth | {tot_growth:+.1f}% |")
    L.append(f"| Total units sold | {int(t['units']):,} |")
    L.append(f"| Average selling price | ${t['avg_selling_price']:,.2f} |")
    L.append(f"| Average discount | {t['avg_discount']:.1f}% |")
    L.append(f"| Overall ROAS | {overall_roas:.2f}x |")
    L.append("")

    L.append("## The 6 most important findings\n")
    L.append(f"1. **Category leader \u2014 {top_cat[0]}.** It brings in "
             f"**${top_cat[1]['revenue']:,.0f}** ({top_cat[1]['revenue']/tot_rev*100:.0f}% of all "
             f"revenue). {low_cat[0]} is the smallest at ${low_cat[1]['revenue']:,.0f}.\n")
    L.append(f"2. **Channel split \u2014 {lead_ch} wins.** {lead_ch} drives "
             f"**${max(online_rev, store_rev):,.0f}** vs "
             f"${min(online_rev, store_rev):,.0f} for the other channel. "
             f"Store has a notably lower return rate "
             f"({bch['Store']['avg_return_rate']*100:.1f}% vs "
             f"{bch['Online']['avg_return_rate']*100:.1f}% Online).\n")
    L.append(f"3. **Year-over-year \u2014 {tot_growth:+.1f}%.** Revenue "
             f"{('grew' if tot_growth >= 0 else 'fell')} from {y0} to {y1}. "
             f"Biggest riser: {max(yoy['by_category'].items(), key=lambda x: x[1]['growth_pct'])[0]}; "
             f"biggest faller: {min(yoy['by_category'].items(), key=lambda x: x[1]['growth_pct'])[0]}.\n")
    L.append(f"4. **Discounting doesn't clearly lift volume.** Discount-to-units "
             f"correlation is **{corr['discount_vs_units']:+.2f}** (near zero) \u2014 bigger "
             f"markdowns are not reliably tied to more units, so they may erode margin.\n")
    L.append(f"5. **Ratings reduce returns.** Rating-to-return correlation is "
             f"**{corr['rating_vs_return']:+.2f}** \u2014 higher-rated products get returned less.\n")
    L.append(f"6. **Ad spend is most efficient in {roi_sorted[0][0]}.** ROAS there is "
             f"**{roi_sorted[0][1]['roas']:.2f}x** (vs {roi_sorted[-1][1]['roas']:.2f}x for "
             f"{roi_sorted[-1][0]}). Overall ROAS is {overall_roas:.2f}x.\n")

    L.append("## Category scorecard\n")
    L.append("| Category | Revenue | Share | Units | Avg Price | Avg Disc. | Return Rate | ROAS |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c, d in cat_sorted:
        L.append(f"| {c} | ${d['revenue']:,.0f} | {d['revenue']/tot_rev*100:.0f}% | "
                 f"{int(d['units']):,} | ${d['avg_price']:,.2f} | {d['avg_discount']:.1f}% | "
                 f"{d['avg_return_rate']*100:.1f}% | {roi[c]['roas']:.2f}x |")
    L.append("")

    L.append("## Channel scorecard\n")
    L.append("| Channel | Revenue | Units | Avg Price | Avg Disc. | Return Rate | ROAS |")
    L.append("|---|---|---|---|---|---|---|")
    for c in ["Online", "Store"]:
        d = bch[c]
        L.append(f"| {c} | ${d['revenue']:,.0f} | {int(d['units']):,} | "
                 f"${d['avg_price']:,.2f} | {d['avg_discount']:.1f}% | "
                 f"{d['avg_return_rate']*100:.1f}% | "
                 f"{roi[c]['roas'] if c in roi else 0:.2f}x |")
    L.append("")

    L.append("## What to do next (suggested actions)\n")
    L.append("- **Double down on high-ROAS categories** to scale efficiently.")
    L.append("- **Review blanket discounting** \u2014 it isn't driving volume, so target it.")
    L.append("- **Investigate Online returns** (higher than Store) to protect margin.")
    L.append("- **Plan inventory around seasonal peaks** visible in the monthly trend.")
    L.append("")

    with open(os.path.join(path, "KEY_FINDINGS.md"), "w") as f:
        f.write("\n".join(L))

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    rows = load_rows(SRC)
    res = analyze(rows)
    write_csvs(OUTDIR, res)
    charts = build_charts(OUTDIR, res)
    build_html(OUTDIR, res)
    write_summary(OUTDIR, res)

    print("Analysis complete.")
    print(f"  Output folder : {OUTDIR}/")
    print(f"  SVG charts    : {charts}/ ({len(os.listdir(charts))} files)")
    print(f"  Report        : {OUTDIR}/report.html")
    print(f"  Key findings  : {OUTDIR}/KEY_FINDINGS.md")
    print(f"  CSVs          : summary_by_category, summary_by_channel, monthly_trend, "
          f"discount_analysis, yoy_growth_by_category, revenue_by_year, "
          f"heatmap_category_channel, ad_spend_roi_by_category, key_metrics.json")
    print()
    print("Headline numbers:")
    t = res["totals"]
    print(f"  Total revenue      : ${t['revenue']:,.0f}")
    print(f"  Total units        : {int(t['units']):,}")
    print(f"  Avg selling price  : ${t['avg_selling_price']:,.2f}")
    print(f"  Avg discount       : {t['avg_discount']:.1f}%")
    print()
    print("Next: convert charts to PNG:")
    print(f"  node svg_to_png.js {OUTDIR}/charts {OUTDIR}/charts_png 200")

if __name__ == "__main__":
    main()