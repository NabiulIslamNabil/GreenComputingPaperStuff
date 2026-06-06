"""
RCAS Paper Figure Generator
============================

Run:
    python generate_figures.py

Output:
    Results and Analysis/
    ├── RCAS Output.txt
    ├── generate_figures.py   ← this file
    └── Result Figures/
        ├── rcas_fig1_dashboard.png
        ├── rcas_fig2_radar.png
        ├── rcas_fig3_reduction.png
        └── rcas_fig4_decision.png
"""

import os
import re
import sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

matplotlib.rcParams.update({
    'font.family'      : 'DejaVu Sans',
    'axes.spines.top'  : False,
    'axes.spines.right': False,
    'axes.grid'        : True,
    'grid.alpha'       : 0.35,
    'grid.linestyle'   : '--',
})

# ══════════════════════════════════════════════════════════════════════════════
#  PATHS  — always relative to this script's location
# ══════════════════════════════════════════════════════════════════════════════
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
TXT_FILE    = os.path.join(SCRIPT_DIR, 'RCAS Output.txt')
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, 'Result Figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

SYSTEMS  = ['RCAS', 'Cloud', 'Local', 'Threshold']
COLORS   = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e']

# ══════════════════════════════════════════════════════════════════════════════
#  PARSER  — reads every number we need directly from RCAS Output.txt
# ══════════════════════════════════════════════════════════════════════════════
def parse_output(path):
    if not os.path.exists(path):
        sys.exit(f"[ERROR] Cannot find '{path}'\n"
                 f"Make sure generate_figures.py is in the same folder as RCAS Output.txt")

    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    def grab(pattern, cast=float, flags=0):
        m = re.search(pattern, text, flags)
        if not m:
            sys.exit(f"[ERROR] Could not parse pattern: {pattern}")
        return cast(m.group(1))

    def grab_all(pattern, cast=float, flags=0):
        return [cast(x) for x in re.findall(pattern, text, flags)]

    data = {}

    # ── Confusion matrix ──────────────────────────────────────────────────────
    data['TP'] = grab(r'TP\s*=\s*(\d+)', int)
    data['TN'] = grab(r'TN\s*=\s*(\d+)', int)
    data['FP'] = grab(r'FP\s*=\s*(\d+)', int)
    data['FN'] = grab(r'FN\s*=\s*(\d+)', int)

    # ── Decision split ────────────────────────────────────────────────────────
    data['cloud_n'] = grab(r'Cloud\s*:\s*(\d+)', int)
    data['local_n'] = grab(r'Local\s*:\s*(\d+)', int)
    data['buf_q']   = grab(r'Buffer \(queued\)\s*[:\s]+(\d+)', int)
    data['buf_r']   = grab(r'Buffer resolved\s*[:\s]+(\d+)', int)
    data['total']   = data['cloud_n'] + data['local_n']

    # ── Comparison table ─────────────────────────────────────────────────────
    # Each metric row: name  RCAS  Cloud  Local  Threshold
    def row(label):
        pattern = rf'{label}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
        m = re.search(pattern, text)
        if not m:
            sys.exit(f"[ERROR] Could not parse row: {label}")
        return [float(m.group(i)) for i in range(1, 5)]

    data['energy']   = row(r'Energy \(mWh/node-day\)')
    data['carbon']   = row(r'Carbon \(gCO2/node-day\)')
    data['network']  = row(r'Network \(B/node-day\)')
    data['latency']  = row(r'Latency \(ms\)')
    data['battlife'] = row(r'BattLife \(days\)')

    # ── Detection metrics ─────────────────────────────────────────────────────
    data['rcas_prec'] = grab(r'RCAS\s+Precision:\s*([\d.]+)')
    data['rcas_rec']  = grab(r'RCAS\s+Precision:[\d.\s]+Recall:\s*([\d.]+)')
    data['rcas_f1']   = grab(r'RCAS\s+Precision:[\d.\s]+Recall:[\d.\s]+F1:\s*([\d.]+)')

    # ── Reduction percentages ─────────────────────────────────────────────────
    data['vs_cloud_energy']  = grab(r'RCAS VS ALWAYS CLOUD.*?Energy Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    data['vs_cloud_carbon']  = grab(r'RCAS VS ALWAYS CLOUD.*?Carbon Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    data['vs_cloud_network'] = grab(r'RCAS VS ALWAYS CLOUD.*?Network Reduction\s*:\s*([+-]?[\d.]+)',  flags=re.DOTALL)
    data['vs_local_energy']  = grab(r'RCAS VS ALWAYS LOCAL.*?Energy Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    data['vs_local_carbon']  = grab(r'RCAS VS ALWAYS LOCAL.*?Carbon Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    data['vs_thr_energy']    = grab(r'RCAS VS SIMPLE THRESHOLD.*?Energy Reduction\s*:\s*([+-]?[\d.]+)', flags=re.DOTALL)
    data['vs_thr_carbon']    = grab(r'RCAS VS SIMPLE THRESHOLD.*?Carbon Reduction\s*:\s*([+-]?[\d.]+)', flags=re.DOTALL)
    data['vs_thr_network']   = grab(r'RCAS VS SIMPLE THRESHOLD.*?Network Reduction\s*:\s*([+-]?[\d.]+)', flags=re.DOTALL)

    return data


# ══════════════════════════════════════════════════════════════════════════════
#  FIG 1 — ALL-METRICS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def fig1_dashboard(d):
    metrics = [
        ('Energy\n(mWh/node-day)',  d['energy'],   True),
        ('Carbon\n(gCO₂/node-day)', d['carbon'],   True),
        ('Network\n(B/node-day)',   d['network'],  True),
        ('Latency\n(ms)',           d['latency'],  True),
        ('Battery Life\n(days)',    d['battlife'], False),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(18, 5.5))
    fig.suptitle('RCAS vs Baseline Systems — All Metrics',
                 fontsize=15, fontweight='bold', y=1.01)

    for ax, (label, vals, lower) in zip(axes, metrics):
        bars = ax.bar(SYSTEMS, vals, color=COLORS, width=0.55,
                      edgecolor='white', linewidth=0.8)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(vals) * 0.015,
                    f'{v:,.2f}', ha='center', va='bottom',
                    fontsize=8.5, fontweight='bold')
        ax.set_title(label, fontsize=10, fontweight='bold', pad=6)
        note = '↓ lower is better' if lower else '↑ higher is better'
        ax.text(0.97, 0.97, note, transform=ax.transAxes,
                ha='right', va='top', fontsize=7.5,
                color='#555555', style='italic')
        ax.set_xticks(range(4))
        ax.set_xticklabels(SYSTEMS, fontsize=9)
        ax.set_ylim(0, max(vals) * 1.20)
        ax.yaxis.grid(True, linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig1_dashboard.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'  [Fig 1] Saved → {out}')


# ══════════════════════════════════════════════════════════════════════════════
#  FIG 2 — NORMALISED RADAR CHART
# ══════════════════════════════════════════════════════════════════════════════
def fig2_radar(d):
    radar_labels    = ['Energy', 'Carbon', 'Network', 'Latency', 'BattLife']
    lower_is_better = [True,     True,     True,      True,      False     ]

    raw = np.array([
        d['energy'],
        d['carbon'],
        d['network'],
        d['latency'],
        d['battlife'],
    ]).T   # shape (4, 5)

    scores = np.zeros_like(raw)
    for c in range(raw.shape[1]):
        col = raw[:, c]
        if lower_is_better[c]:
            if col.min() == 0:
                nz_min = col[col > 0].min()
                scores[:, c] = np.where(col == 0, 1.0, nz_min / col)
            else:
                scores[:, c] = col.min() / col
        else:
            scores[:, c] = col / col.max()

    print("\n  [Fig 2] Radar normalised scores:")
    print(f"  {'System':<12}" + "".join(f"{l:>10}" for l in radar_labels))
    for i, s in enumerate(SYSTEMS):
        print(f"  {s:<12}" + "".join(f"{scores[i, j]:>10.3f}" for j in range(5)))

    N      = len(radar_labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fill_alphas = [0.18, 0.10, 0.12, 0.10]
    lws         = [2.8,  1.8,  2.0,  2.0 ]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    for i in range(4):
        vals = scores[i].tolist() + [scores[i, 0]]
        ax.plot(angles, vals, color=COLORS[i], linewidth=lws[i], zorder=3 + i)
        ax.fill(angles, vals, color=COLORS[i], alpha=fill_alphas[i], zorder=1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_labels, fontsize=13, fontweight='bold')
    ax.set_yticks([0.25, 0.50, 0.75, 1.0])
    ax.set_yticklabels(['0.25', '0.50', '0.75', '1.0'],
                       fontsize=8, color='grey')
    ax.set_ylim(0, 1.05)
    ax.yaxis.grid(True, linestyle='--', linewidth=0.6, color='grey', alpha=0.6)
    ax.xaxis.grid(True, linestyle='-',  linewidth=0.5, color='grey', alpha=0.4)
    ax.spines['polar'].set_visible(False)

    patches = [mpatches.Patch(facecolor=COLORS[i], edgecolor=COLORS[i],
                              linewidth=1.5, label=SYSTEMS[i])
               for i in range(4)]
    ax.legend(handles=patches, loc='upper right',
              bbox_to_anchor=(1.32, 1.18), fontsize=11, framealpha=0.9)
    ax.set_title('Normalised Multi-Metric Radar\n(score = 1.0 → best in metric)',
                 size=13, fontweight='bold', pad=22)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig2_radar.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'  [Fig 2] Saved → {out}')


# ══════════════════════════════════════════════════════════════════════════════
#  FIG 3 — REDUCTION % CHART
# ══════════════════════════════════════════════════════════════════════════════
def fig3_reduction(d):
    groups    = ['Carbon', 'Energy', 'Network']
    baselines = ['vs Cloud\n(Always-Cloud)',
                 'vs Local\n(Always-Local)',
                 'vs Threshold\n(Simple Thresh.)']
    bar_colors = ['#1f77b4', '#2ca02c', '#ff7f0e']

    # Rows = baselines, Cols = [Carbon, Energy, Network]
    # Network vs Local is undefined (Local = 0) → None
    reductions = [
        [d['vs_cloud_carbon'],  d['vs_cloud_energy'],  d['vs_cloud_network']],
        [d['vs_local_carbon'],  d['vs_local_energy'],  None                 ],
        [d['vs_thr_carbon'],    d['vs_thr_energy'],    d['vs_thr_network']  ],
    ]

    x       = np.arange(len(groups))
    width   = 0.22
    offsets = np.linspace(-(len(baselines)-1)/2,
                           (len(baselines)-1)/2,
                           len(baselines)) * width

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axhline(0, color='black', linewidth=0.9, zorder=2)

    for i, (baseline, row_vals) in enumerate(zip(baselines, reductions)):
        for j, (grp, val) in enumerate(zip(groups, row_vals)):
            if val is None:
                continue
            xpos = x[j] + offsets[i]
            ax.bar(xpos, val, width=width * 0.92,
                   color=bar_colors[i], edgecolor='white',
                   linewidth=0.6, zorder=3,
                   label=baseline if j == 0 else '')
            color = '#1a7a1a' if val > 0 else '#cc0000'
            yoff  = 1.0 if val >= 0 else -2.5
            ax.text(xpos, val + yoff,
                    f'{val:+.1f}%',
                    ha='center',
                    va='bottom' if val >= 0 else 'top',
                    fontsize=8.5, fontweight='bold', color=color)

    # N/A label for Network vs Local
    ax.text(x[2] + offsets[1], 3, 'N/A\n(Local=0)',
            ha='center', va='bottom',
            fontsize=7.5, color='grey', style='italic')

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=12, fontweight='bold')
    ax.set_ylabel('Reduction vs Baseline (%)', fontsize=11)
    ax.set_title('RCAS Reduction (%) vs Baseline Systems\n'
                 '(+ve = RCAS is better;  –ve = RCAS uses more)',
                 fontsize=13, fontweight='bold')
    ax.legend(title='Baseline', fontsize=9, title_fontsize=9,
              loc='upper right', framealpha=0.9)
    ax.set_ylim(-70, 80)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig3_reduction.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'  [Fig 3] Saved → {out}')


# ══════════════════════════════════════════════════════════════════════════════
#  FIG 4 — DECISION SPLIT (donut + horizontal bar)
# ══════════════════════════════════════════════════════════════════════════════
def fig4_decision(d):
    cloud_n = d['cloud_n']
    local_n = d['local_n']
    buf_q   = d['buf_q']
    buf_r   = d['buf_r']
    total   = d['total']

    fig = plt.figure(figsize=(13, 5.5))
    fig.suptitle(
        f'RCAS Scheduling Decision Overview\n'
        f'(8 nodes × 15 days × 144 samples = {total:,} total)',
        fontsize=13, fontweight='bold', y=1.02)

    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.38)
    ax1 = fig.add_subplot(gs[0])

    # ── Donut ─────────────────────────────────────────────────────────────────
    wedges, texts, autotexts = ax1.pie(
        [cloud_n, local_n],
        explode=[0.04, 0.04],
        labels=['Cloud', 'Local'],
        colors=['#d62728', '#2ca02c'],
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops=dict(width=0.52, edgecolor='white', linewidth=2),
        textprops=dict(fontsize=12),
        pctdistance=0.75,
    )
    for at in autotexts:
        at.set_fontsize(13)
        at.set_fontweight('bold')
        at.set_color('white')
    ax1.text(0, 0, f'Total\n{total:,}',
             ha='center', va='center',
             fontsize=11, fontweight='bold', color='#333333')
    ax1.set_title('Primary Decision Routing\n(Cloud vs Local)',
                  fontsize=11, fontweight='bold', pad=10)

    # ── Horizontal bar ────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1])
    categories = ['Cloud\n(transmitted)', 'Local\n(edge inferred)',
                  'Buffer\n(queued)',      'Buffer\n(resolved)']
    counts     = [cloud_n, local_n, buf_q, buf_r]
    bar_colors = ['#d62728', '#2ca02c', '#ff7f0e', '#1f77b4']

    bars = ax2.barh(categories, counts, color=bar_colors,
                    edgecolor='white', linewidth=0.8, height=0.55)
    for bar, cnt in zip(bars, counts):
        ax2.text(bar.get_width() + max(counts) * 0.01,
                 bar.get_y() + bar.get_height() / 2,
                 f'{cnt:,}', va='center',
                 fontsize=10.5, fontweight='bold')

    ax2.set_xlabel('Sample Count', fontsize=11)
    ax2.set_title('Full Decision Split\n(Cloud / Local / Buffer)',
                  fontsize=11, fontweight='bold', pad=10)
    ax2.set_xlim(0, max(counts) * 1.18)
    ax2.invert_yaxis()
    ax2.xaxis.grid(True, linestyle='--', alpha=0.4)
    ax2.set_axisbelow(True)

    # 100% buffer resolution annotation
    ax2.annotate(
        '100% resolved\n(zero data loss)',
        xy=(buf_r, 3),
        xytext=(buf_r - max(counts) * 0.38, 3),
        fontsize=8.5, color='#1f77b4', fontweight='bold',
        arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=1.4),
    )

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig4_decision.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'  [Fig 4] Saved → {out}')


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print(f'\nReading simulation output from:\n  {TXT_FILE}\n')
    data = parse_output(TXT_FILE)

    print('Parsed values (quick check):')
    print(f'  Energy   → {data["energy"]}')
    print(f'  Carbon   → {data["carbon"]}')
    print(f'  Network  → {data["network"]}')
    print(f'  Latency  → {data["latency"]}')
    print(f'  BattLife → {data["battlife"]}')
    print(f'  Decisions → Cloud={data["cloud_n"]:,}  '
          f'Local={data["local_n"]:,}  '
          f'Buf={data["buf_q"]:,}  Resolved={data["buf_r"]:,}')
    print(f'\nGenerating figures into:\n  {OUTPUT_DIR}\n')

    fig1_dashboard(data)
    fig2_radar(data)
    fig3_reduction(data)
    fig4_decision(data)

    print(f'\nDone. All 4 figures saved to:\n  {OUTPUT_DIR}')
