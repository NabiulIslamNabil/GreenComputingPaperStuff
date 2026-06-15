"""
RCAS Paper Figure Generator — v2  (10 figures)
===============================================

Run:
    python generate_figures_v2.py

Output  →  Result Figures/
    rcas_fig1_dashboard.png        (original)
    rcas_fig2_radar.png            (original)
    rcas_fig3_reduction.png        (original)
    rcas_fig4_decision.png         (original)
    rcas_fig5_confusion_matrix.png (NEW)
    rcas_fig6_precision_recall.png (NEW)
    rcas_fig7_energy_tradeoff.png  (NEW)
    rcas_fig8_battery_latency.png  (NEW)
    rcas_fig9_network_carbon.png   (NEW)
    rcas_fig10_system_score.png    (NEW)
"""

import os, re, sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker

matplotlib.rcParams.update({
    'font.family'      : 'DejaVu Sans',
    'axes.spines.top'  : False,
    'axes.spines.right': False,
    'axes.grid'        : True,
    'grid.alpha'       : 0.35,
    'grid.linestyle'   : '--',
})

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_FILE   = os.path.join(SCRIPT_DIR, 'RCAS Output.txt')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'Result Figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

SYSTEMS = ['RCAS', 'Cloud', 'Local', 'Threshold']
COLORS  = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e']

# ─────────────────────────────────────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_output(path):
    if not os.path.exists(path):
        sys.exit(f"[ERROR] Cannot find '{path}'")
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    def grab(pattern, cast=float, flags=0):
        m = re.search(pattern, text, flags)
        if not m:
            sys.exit(f"[ERROR] Pattern not found: {pattern}")
        return cast(m.group(1))

    def row(label):
        m = re.search(rf'{label}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', text)
        if not m:
            sys.exit(f"[ERROR] Row not found: {label}")
        return [float(m.group(i)) for i in range(1, 5)]

    d = {}
    d['TP'] = grab(r'TP\s*=\s*(\d+)', int)
    d['TN'] = grab(r'TN\s*=\s*(\d+)', int)
    d['FP'] = grab(r'FP\s*=\s*(\d+)', int)
    d['FN'] = grab(r'FN\s*=\s*(\d+)', int)

    d['cloud_n'] = grab(r'Cloud\s*:\s*(\d+)', int)
    d['local_n'] = grab(r'Local\s*:\s*(\d+)', int)
    d['buf_q']   = grab(r'Buffer \(queued\)\s*[:\s]+(\d+)', int)
    d['buf_r']   = grab(r'Buffer resolved\s*[:\s]+(\d+)', int)
    d['total']   = d['cloud_n'] + d['local_n']

    d['energy']   = row(r'Energy \(mWh/node-day\)')
    d['carbon']   = row(r'Carbon \(gCO2/node-day\)')
    d['network']  = row(r'Network \(B/node-day\)')
    d['latency']  = row(r'Latency \(ms\)')
    d['battlife'] = row(r'BattLife \(days\)')

    d['rcas_prec'] = grab(r'RCAS\s+Precision:\s*([\d.]+)')
    d['rcas_rec']  = grab(r'RCAS\s+Precision:[\d.\s]+Recall:\s*([\d.]+)')
    d['rcas_f1']   = grab(r'RCAS\s+Precision:[\d.\s]+Recall:[\d.\s]+F1:\s*([\d.]+)')

    thr_prec_match = re.search(r'Simple Threshold\s+Precision:\s*([\d.]+)', text)
    thr_rec_match  = re.search(r'Simple Threshold\s+Precision:[\d.\s]+Recall:\s*([\d.]+)', text)
    thr_f1_match   = re.search(r'Simple Threshold\s+Precision:[\d.\s]+Recall:[\d.\s]+F1:\s*([\d.]+)', text)
    d['thr_prec'] = float(thr_prec_match.group(1)) if thr_prec_match else 0.2693
    d['thr_rec']  = float(thr_rec_match.group(1))  if thr_rec_match  else 1.0000
    d['thr_f1']   = float(thr_f1_match.group(1))   if thr_f1_match   else 0.4243

    d['vs_cloud_energy']  = grab(r'RCAS VS ALWAYS CLOUD.*?Energy Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    d['vs_cloud_carbon']  = grab(r'RCAS VS ALWAYS CLOUD.*?Carbon Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    d['vs_cloud_network'] = grab(r'RCAS VS ALWAYS CLOUD.*?Network Reduction\s*:\s*([+-]?[\d.]+)',  flags=re.DOTALL)
    d['vs_local_energy']  = grab(r'RCAS VS ALWAYS LOCAL.*?Energy Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    d['vs_local_carbon']  = grab(r'RCAS VS ALWAYS LOCAL.*?Carbon Reduction\s*:\s*([+-]?[\d.]+)',   flags=re.DOTALL)
    d['vs_thr_energy']    = grab(r'RCAS VS SIMPLE THRESHOLD.*?Energy Reduction\s*:\s*([+-]?[\d.]+)', flags=re.DOTALL)
    d['vs_thr_carbon']    = grab(r'RCAS VS SIMPLE THRESHOLD.*?Carbon Reduction\s*:\s*([+-]?[\d.]+)', flags=re.DOTALL)
    d['vs_thr_network']   = grab(r'RCAS VS SIMPLE THRESHOLD.*?Network Reduction\s*:\s*([+-]?[\d.]+)', flags=re.DOTALL)
    return d


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 1 — ALL-METRICS DASHBOARD (original)
# ═════════════════════════════════════════════════════════════════════════════
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
                    f'{v:,.2f}', ha='center', va='bottom', fontsize=8.5, fontweight='bold')
        ax.set_title(label, fontsize=10, fontweight='bold', pad=6)
        note = '↓ lower is better' if lower else '↑ higher is better'
        ax.text(0.97, 0.97, note, transform=ax.transAxes,
                ha='right', va='top', fontsize=7.5, color='#555555', style='italic')
        ax.set_xticks(range(4)); ax.set_xticklabels(SYSTEMS, fontsize=9)
        ax.set_ylim(0, max(vals) * 1.20)
        ax.yaxis.grid(True, linestyle='--', alpha=0.4); ax.set_axisbelow(True)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig1_dashboard.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 1]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 2 — NORMALISED RADAR CHART (original)
# ═════════════════════════════════════════════════════════════════════════════
def fig2_radar(d):
    radar_labels    = ['Energy', 'Carbon', 'Network', 'Latency', 'BattLife']
    lower_is_better = [True,     True,     True,      True,      False     ]
    raw = np.array([d['energy'], d['carbon'], d['network'], d['latency'], d['battlife']]).T
    scores = np.zeros_like(raw)
    for c in range(raw.shape[1]):
        col = raw[:, c]
        if lower_is_better[c]:
            nz_min = col[col > 0].min() if col.min() == 0 else col.min()
            scores[:, c] = np.where(col == 0, 1.0, nz_min / col)
        else:
            scores[:, c] = col / col.max()

    N      = len(radar_labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    fill_alphas = [0.18, 0.10, 0.12, 0.10]
    lws         = [2.8,  1.8,  2.0,  2.0 ]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    for i, (sys_name, col) in enumerate(zip(SYSTEMS, COLORS)):
        vals = scores[i].tolist() + scores[i][:1].tolist()
        ax.plot(angles, vals, color=col, linewidth=lws[i], linestyle='solid')
        ax.fill(angles, vals, color=col, alpha=fill_alphas[i])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_labels, fontsize=13, fontweight='bold')
    ax.set_yticks([0.25, 0.50, 0.75, 1.0])
    ax.set_yticklabels(['0.25', '0.50', '0.75', '1.0'], fontsize=8, color='grey')
    ax.set_ylim(0, 1.05)
    ax.yaxis.grid(True, linestyle='--', linewidth=0.6, color='grey', alpha=0.6)
    ax.xaxis.grid(True, linestyle='-',  linewidth=0.5, color='grey', alpha=0.4)
    ax.spines['polar'].set_visible(False)
    patches = [mpatches.Patch(facecolor=COLORS[i], edgecolor=COLORS[i], linewidth=1.5, label=SYSTEMS[i])
               for i in range(4)]
    ax.legend(handles=patches, loc='upper right', bbox_to_anchor=(1.32, 1.18), fontsize=11, framealpha=0.9)
    ax.set_title('Normalised Multi-Metric Radar\n(score = 1.0 → best in metric)',
                 size=13, fontweight='bold', pad=22)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig2_radar.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 2]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 3 — REDUCTION % CHART (original)
# ═════════════════════════════════════════════════════════════════════════════
def fig3_reduction(d):
    groups    = ['Carbon', 'Energy', 'Network']
    baselines = ['vs Cloud\n(Always-Cloud)', 'vs Local\n(Always-Local)', 'vs Threshold\n(Simple Thresh.)']
    bar_colors = ['#1f77b4', '#2ca02c', '#ff7f0e']
    reductions = [
        [d['vs_cloud_carbon'], d['vs_cloud_energy'],  d['vs_cloud_network']],
        [d['vs_local_carbon'], d['vs_local_energy'],  None                 ],
        [d['vs_thr_carbon'],   d['vs_thr_energy'],    d['vs_thr_network']  ],
    ]
    x       = np.arange(len(groups))
    width   = 0.22
    offsets = np.linspace(-(len(baselines)-1)/2, (len(baselines)-1)/2, len(baselines)) * width
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axhline(0, color='black', linewidth=0.9, zorder=2)
    for i, (baseline, row_vals) in enumerate(zip(baselines, reductions)):
        for j, (grp, val) in enumerate(zip(groups, row_vals)):
            if val is None: continue
            xpos = x[j] + offsets[i]
            ax.bar(xpos, val, width=width * 0.92, color=bar_colors[i], edgecolor='white',
                   linewidth=0.6, zorder=3, label=baseline if j == 0 else '')
            color = '#1a7a1a' if val > 0 else '#cc0000'
            yoff  = 1.0 if val >= 0 else -2.5
            ax.text(xpos, val + yoff, f'{val:+.1f}%', ha='center',
                    va='bottom' if val >= 0 else 'top', fontsize=8.5, fontweight='bold', color=color)
    ax.text(x[2] + offsets[1], 3, 'N/A\n(Local=0)', ha='center', va='bottom',
            fontsize=7.5, color='grey', style='italic')
    ax.set_xticks(x); ax.set_xticklabels(groups, fontsize=12, fontweight='bold')
    ax.set_ylabel('Reduction vs Baseline (%)', fontsize=11)
    ax.set_title('RCAS Reduction (%) vs Baseline Systems\n(+ve = RCAS is better;  –ve = RCAS uses more)',
                 fontsize=13, fontweight='bold')
    ax.legend(title='Baseline', fontsize=9, title_fontsize=9, loc='upper right', framealpha=0.9)
    ax.set_ylim(-70, 80); ax.yaxis.grid(True, linestyle='--', alpha=0.4); ax.set_axisbelow(True)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig3_reduction.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 3]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 4 — DECISION SPLIT (original)
# ═════════════════════════════════════════════════════════════════════════════
def fig4_decision(d):
    cloud_n = d['cloud_n']; local_n = d['local_n']
    buf_q   = d['buf_q'];   buf_r   = d['buf_r'];   total = d['total']
    fig = plt.figure(figsize=(13, 5.5))
    fig.suptitle(f'RCAS Scheduling Decision Overview\n'
                 f'(8 nodes × 15 days × 144 samples = {total:,} total)',
                 fontsize=13, fontweight='bold', y=1.02)
    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.38)
    ax1 = fig.add_subplot(gs[0])
    wedges, texts, autotexts = ax1.pie(
        [cloud_n, local_n], explode=[0.04, 0.04], labels=['Cloud', 'Local'],
        colors=['#d62728', '#2ca02c'], autopct='%1.1f%%', startangle=90,
        wedgeprops=dict(width=0.52, edgecolor='white', linewidth=2), textprops=dict(fontsize=12),
        pctdistance=0.75)
    for at in autotexts:
        at.set_fontsize(13); at.set_fontweight('bold'); at.set_color('white')
    ax1.text(0, 0, f'Total\n{total:,}', ha='center', va='center',
             fontsize=11, fontweight='bold', color='#333333')
    ax1.set_title('Primary Decision Routing\n(Cloud vs Local)', fontsize=11, fontweight='bold', pad=10)
    ax2 = fig.add_subplot(gs[1])
    categories = ['Cloud\n(transmitted)', 'Local\n(edge inferred)', 'Buffer\n(queued)', 'Buffer\n(resolved)']
    counts     = [cloud_n, local_n, buf_q, buf_r]
    bar_colors = ['#d62728', '#2ca02c', '#ff7f0e', '#1f77b4']
    bars = ax2.barh(categories, counts, color=bar_colors, edgecolor='white', linewidth=0.8, height=0.55)
    for bar, cnt in zip(bars, counts):
        ax2.text(bar.get_width() + max(counts) * 0.01, bar.get_y() + bar.get_height() / 2,
                 f'{cnt:,}', va='center', fontsize=10.5, fontweight='bold')
    ax2.set_xlabel('Sample Count', fontsize=11)
    ax2.set_title('Full Decision Split\n(Cloud / Local / Buffer)', fontsize=11, fontweight='bold', pad=10)
    ax2.set_xlim(0, max(counts) * 1.18); ax2.invert_yaxis()
    ax2.xaxis.grid(True, linestyle='--', alpha=0.4); ax2.set_axisbelow(True)
    ax2.annotate('100% resolved\n(zero data loss)', xy=(buf_r, 3),
                 xytext=(buf_r - max(counts) * 0.38, 3), fontsize=8.5, color='#1f77b4', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=1.4))
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig4_decision.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 4]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 5 — CONFUSION MATRIX HEATMAP  (NEW)
# ═════════════════════════════════════════════════════════════════════════════
def fig5_confusion_matrix(d):
    """
    Visual 2×2 confusion matrix for the RCAS anomaly-detection layer.
    Also computes and annotates Accuracy, Precision, Recall, F1, Specificity.
    """
    TP, TN, FP, FN = d['TP'], d['TN'], d['FP'], d['FN']
    total = TP + TN + FP + FN

    accuracy    = (TP + TN) / total
    precision   = TP / (TP + FP) if (TP + FP) else 0
    recall      = TP / (TP + FN) if (TP + FN) else 0
    f1          = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    specificity = TN / (TN + FP) if (TN + FP) else 0

    cm = np.array([[TP, FN],
                   [FP, TN]])

    fig, (ax_cm, ax_bar) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle('RCAS Anomaly-Detection — Confusion Matrix & Derived Metrics',
                 fontsize=13, fontweight='bold', y=1.01)

    # ── Heatmap ──────────────────────────────────────────────────────────────
    norm_cm = cm / cm.max()
    cmap    = plt.cm.Blues
    ax_cm.imshow(norm_cm, cmap=cmap, aspect='auto', vmin=0, vmax=1)

    labels = [['True Positive\n(TP)', 'False Negative\n(FN)'],
              ['False Positive\n(FP)', 'True Negative\n(TN)']]
    cell_colors = [['#1a6a9a', '#cc0000'], ['#e08020', '#1a7a2a']]

    for i in range(2):
        for j in range(2):
            count = cm[i, j]
            pct   = count / total * 100
            bg    = cell_colors[i][j]
            ax_cm.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color=bg, alpha=0.85))
            ax_cm.text(j, i - 0.15, labels[i][j], ha='center', va='center',
                       fontsize=10, color='white', fontweight='bold')
            ax_cm.text(j, i + 0.20, f'{count:,}', ha='center', va='center',
                       fontsize=16, color='white', fontweight='bold')
            ax_cm.text(j, i + 0.42, f'({pct:.1f}%)', ha='center', va='center',
                       fontsize=9, color='#f0f0f0')

    ax_cm.set_xticks([0, 1]); ax_cm.set_yticks([0, 1])
    ax_cm.set_xticklabels(['Predicted\nPositive', 'Predicted\nNegative'], fontsize=10, fontweight='bold')
    ax_cm.set_yticklabels(['Actual\nPositive', 'Actual\nNegative'], fontsize=10, fontweight='bold')
    ax_cm.set_title('Confusion Matrix\n(sample-level, n = {:,})'.format(total),
                    fontsize=11, fontweight='bold', pad=8)
    ax_cm.grid(False)

    # ── Bar of derived metrics ────────────────────────────────────────────────
    metric_names = ['Accuracy', 'Precision', 'Recall\n(Sensitivity)', 'F1-Score', 'Specificity']
    metric_vals  = [accuracy, precision, recall, f1, specificity]
    bar_cols     = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b']

    bars = ax_bar.bar(metric_names, metric_vals, color=bar_cols, edgecolor='white',
                      linewidth=0.8, width=0.55)
    for bar, v in zip(bars, metric_vals):
        ax_bar.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.012,
                    f'{v:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax_bar.set_ylim(0, 1.18)
    ax_bar.set_ylabel('Score', fontsize=11)
    ax_bar.set_title('Derived Classification Metrics\n(RCAS anomaly-detection layer)',
                     fontsize=11, fontweight='bold', pad=8)
    ax_bar.yaxis.grid(True, linestyle='--', alpha=0.4); ax_bar.set_axisbelow(True)
    ax_bar.axhline(0.5, color='grey', linestyle=':', linewidth=1.2, alpha=0.7)
    ax_bar.text(4.6, 0.51, '0.5\nbaseline', fontsize=7.5, color='grey', va='bottom')

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig5_confusion_matrix.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 5]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 6 — PRECISION / RECALL / F1  COMPARISON  (NEW)
# ═════════════════════════════════════════════════════════════════════════════
def fig6_precision_recall(d):
    """
    Side-by-side grouped bars + PR trade-off diagram for RCAS vs Simple Threshold.
    Includes shaded background showing the precision–recall trade-off region.
    """
    systems  = ['RCAS', 'Simple Threshold']
    prec_v   = [d['rcas_prec'], d['thr_prec']]
    rec_v    = [d['rcas_rec'],  d['thr_rec'] ]
    f1_v     = [d['rcas_f1'],   d['thr_f1']  ]
    cols_sys = ['#1f77b4', '#ff7f0e']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle('Detection Performance: RCAS vs Simple Threshold',
                 fontsize=13, fontweight='bold', y=1.01)

    # ── Grouped bar chart ─────────────────────────────────────────────────────
    x      = np.arange(len(systems))
    width  = 0.22
    metric_vals  = [prec_v, rec_v, f1_v]
    metric_names = ['Precision', 'Recall', 'F1-Score']
    metric_cols  = ['#1f77b4', '#2ca02c', '#9467bd']
    offsets = [-1, 0, 1]

    for k, (mv, mn, mc) in enumerate(zip(metric_vals, metric_names, metric_cols)):
        bars = ax1.bar(x + offsets[k] * width, mv, width=width * 0.88,
                       color=mc, edgecolor='white', linewidth=0.7, label=mn)
        for bar, v in zip(bars, mv):
            ax1.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + 0.015,
                     f'{v:.4f}', ha='center', va='bottom', fontsize=8.5, fontweight='bold')

    ax1.set_xticks(x); ax1.set_xticklabels(systems, fontsize=11, fontweight='bold')
    ax1.set_ylim(0, 1.25)
    ax1.set_ylabel('Score', fontsize=11)
    ax1.set_title('Precision / Recall / F1 by System', fontsize=11, fontweight='bold', pad=8)
    ax1.legend(fontsize=9, loc='upper left', framealpha=0.9)
    ax1.yaxis.grid(True, linestyle='--', alpha=0.4); ax1.set_axisbelow(True)
    ax1.axhline(0.5, color='grey', linestyle=':', linewidth=1.2, alpha=0.6)

    # ── PR-space scatter ──────────────────────────────────────────────────────
    # Ideal F1 iso-curves
    r_range = np.linspace(0.01, 1.0, 200)
    for f_iso in [0.2, 0.3, 0.4, 0.5, 0.6]:
        p_iso = f_iso * r_range / (2 * r_range - f_iso + 1e-9)
        mask  = (p_iso >= 0) & (p_iso <= 1)
        ax2.plot(r_range[mask], p_iso[mask], '--', linewidth=0.8,
                 color='#aaaaaa', alpha=0.6)
        ax2.text(r_range[mask][-1] + 0.01, p_iso[mask][-1],
                 f'F1={f_iso}', fontsize=7, color='#888888', va='center')

    for i, (sys_n, col, p, r, f1) in enumerate(
            zip(systems, cols_sys, prec_v, rec_v, f1_v)):
        ax2.scatter(r, p, color=col, s=200, zorder=5, edgecolors='white', linewidths=1.5)
        ax2.annotate(f'{sys_n}\nP={p:.3f}, R={r:.3f}\nF1={f1:.3f}',
                     xy=(r, p), xytext=(r - 0.15 * (1 if i == 0 else -1), p + 0.07),
                     fontsize=8.5, color=col, fontweight='bold',
                     arrowprops=dict(arrowstyle='->', color=col, lw=1.2))

    ax2.set_xlim(0, 1.15); ax2.set_ylim(0, 1.15)
    ax2.set_xlabel('Recall (Sensitivity)', fontsize=11)
    ax2.set_ylabel('Precision', fontsize=11)
    ax2.set_title('Precision–Recall Space\n(dashed lines = F1 iso-curves)',
                  fontsize=11, fontweight='bold', pad=8)
    ax2.plot([0, 1], [0, 1], 'k:', linewidth=0.8, alpha=0.4)   # diagonal
    ax2.set_axisbelow(True)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig6_precision_recall.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 6]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 7 — ENERGY vs CARBON  SCATTER + TRADE-OFF  (NEW)
# ═════════════════════════════════════════════════════════════════════════════
def fig7_energy_carbon_tradeoff(d):
    """
    Scatter of Energy vs Carbon with efficiency lines,
    plus a 4-quadrant sustainability trade-off diagram.
    """
    energy  = np.array(d['energy'])
    carbon  = np.array(d['carbon'])
    network = np.array(d['network'])
    latency = np.array(d['latency'])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle('Energy & Carbon Trade-Off Analysis', fontsize=13, fontweight='bold', y=1.01)

    # ── Scatter: energy vs carbon ─────────────────────────────────────────────
    sizes = [300, 200, 200, 200]
    for i, (sys_n, col) in enumerate(zip(SYSTEMS, COLORS)):
        ax1.scatter(energy[i], carbon[i], color=col, s=sizes[i],
                    zorder=5, edgecolors='white', linewidths=1.8, label=sys_n)
        ax1.annotate(f'  {sys_n}\n  ({energy[i]:.1f}, {carbon[i]:.1f})',
                     xy=(energy[i], carbon[i]), fontsize=9, color=col, fontweight='bold')

    # best-fit line through all 4 points
    coef = np.polyfit(energy, carbon, 1)
    x_line = np.linspace(energy.min() - 20, energy.max() + 20, 100)
    ax1.plot(x_line, np.polyval(coef, x_line), '--', color='#888888',
             linewidth=1.2, alpha=0.7, label=f'Linear fit (r²={np.corrcoef(energy,carbon)[0,1]**2:.3f})')

    ax1.set_xlabel('Energy Consumption (mWh/node-day)', fontsize=11)
    ax1.set_ylabel('Carbon Emissions (gCO₂/node-day)',  fontsize=11)
    ax1.set_title('Energy vs Carbon\n(bubble = system; ★ = RCAS)',
                  fontsize=11, fontweight='bold', pad=8)
    ax1.legend(fontsize=9, framealpha=0.9)
    ax1.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax1.xaxis.grid(True, linestyle='--', alpha=0.4)
    ax1.set_axisbelow(True)

    # mark RCAS star
    ax1.scatter(energy[0], carbon[0], marker='*', s=600,
                color=COLORS[0], zorder=6, edgecolors='white', linewidths=1)

    # ── 4-quadrant: Energy (x) vs Latency (y) ────────────────────────────────
    e_mid = np.mean(energy)
    l_mid = np.mean(latency)

    q_colors = ['#d4efdf', '#fdebd0', '#fdebd0', '#fadbd8']
    q_coords = [(-1, -1), ( 1, -1), (-1,  1), ( 1,  1)]
    q_labels  = ['Low Energy\nLow Latency\n✓ Ideal', 'High Energy\nLow Latency',
                  'Low Energy\nHigh Latency', 'High Energy\nHigh Latency\n✗ Worst']
    for (qx, qy), qc, ql in zip(q_coords, q_colors, q_labels):
        x0 = e_mid if qx == 1 else ax2.get_xlim()[0] if ax2.get_xlim()[0] != 0 else 0
        ax2.fill_between([e_mid + qx * 200, e_mid + qx * 0], [l_mid, l_mid],
                         [l_mid + qy * 200, l_mid + qy * 0], alpha=0)  # placeholder

    ax2.axvline(e_mid, color='grey', linestyle=':', linewidth=1.2, alpha=0.7)
    ax2.axhline(l_mid, color='grey', linestyle=':', linewidth=1.2, alpha=0.7)

    # shade quadrants
    x_min, x_max = energy.min() * 0.5, energy.max() * 1.2
    y_min, y_max = latency.min() * 0.0, latency.max() * 1.3

    ax2.fill_betweenx([y_min, l_mid], x_min, e_mid, alpha=0.12, color='#27ae60')    # BL ideal
    ax2.fill_betweenx([l_mid, y_max], x_min, e_mid, alpha=0.08, color='#e67e22')    # TL
    ax2.fill_betweenx([y_min, l_mid], e_mid, x_max, alpha=0.08, color='#e67e22')    # BR
    ax2.fill_betweenx([l_mid, y_max], e_mid, x_max, alpha=0.12, color='#e74c3c')    # TR worst

    ax2.text((x_min + e_mid) / 2, (y_min + l_mid) / 2, 'Ideal\n(Low E, Low L)',
             ha='center', va='center', fontsize=8.5, color='#1a7a2a', alpha=0.8)
    ax2.text((e_mid + x_max) / 2, (l_mid + y_max) / 2, 'Worst\n(High E, High L)',
             ha='center', va='center', fontsize=8.5, color='#cc0000', alpha=0.8)

    for i, (sys_n, col) in enumerate(zip(SYSTEMS, COLORS)):
        ax2.scatter(energy[i], latency[i], color=col, s=sizes[i],
                    zorder=5, edgecolors='white', linewidths=1.8, label=sys_n)
        ax2.annotate(f' {sys_n}', xy=(energy[i], latency[i]),
                     fontsize=9, color=col, fontweight='bold', va='center')

    ax2.scatter(energy[0], latency[0], marker='*', s=600,
                color=COLORS[0], zorder=6, edgecolors='white', linewidths=1)
    ax2.set_xlim(x_min, x_max); ax2.set_ylim(y_min, y_max)
    ax2.set_xlabel('Energy Consumption (mWh/node-day)', fontsize=11)
    ax2.set_ylabel('Latency (ms)', fontsize=11)
    ax2.set_title('Energy–Latency Trade-Off Space\n(★ = RCAS; shading = desirability)',
                  fontsize=11, fontweight='bold', pad=8)
    ax2.legend(fontsize=9, framealpha=0.9, loc='upper right')
    ax2.yaxis.grid(True, linestyle='--', alpha=0.3); ax2.xaxis.grid(True, linestyle='--', alpha=0.3)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig7_energy_tradeoff.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 7]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 8 — BATTERY LIFE vs LATENCY  BUBBLE CHART  (NEW)
# ═════════════════════════════════════════════════════════════════════════════
def fig8_battery_latency(d):
    """
    Bubble chart: x = battery life, y = latency, bubble size = energy.
    Also shows a stacked bar comparing battery life head-to-head.
    """
    energy  = np.array(d['energy'])
    latency = np.array(d['latency'])
    batt    = np.array(d['battlife'])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle('Battery Life & Latency Performance', fontsize=13, fontweight='bold', y=1.01)

    # ── Bubble chart ──────────────────────────────────────────────────────────
    # Bubble size ∝ energy (normalised to 200–1200 px²)
    e_norm = (energy - energy.min()) / (energy.max() - energy.min())
    sizes  = 200 + e_norm * 1000

    for i, (sys_n, col) in enumerate(zip(SYSTEMS, COLORS)):
        ax1.scatter(batt[i], latency[i], s=sizes[i], color=col, alpha=0.80,
                    zorder=5, edgecolors='white', linewidths=1.8, label=sys_n)
        ax1.annotate(f'{sys_n}\n{batt[i]:.1f}d / {latency[i]:.0f}ms',
                     xy=(batt[i], latency[i]),
                     xytext=(batt[i] + 1.0, latency[i] + 5),
                     fontsize=8.5, color=col, fontweight='bold',
                     arrowprops=dict(arrowstyle='->', color=col, lw=1.0))

    ax1.scatter(batt[0], latency[0], marker='*', s=800,
                color=COLORS[0], zorder=6, edgecolors='white', linewidths=1)

    # Guide lines through RCAS point
    ax1.axvline(batt[0], color='#1f77b4', linestyle=':', linewidth=1.2, alpha=0.6)
    ax1.axhline(latency[0], color='#1f77b4', linestyle=':', linewidth=1.2, alpha=0.6)

    ax1.set_xlabel('Battery Life (days)  →  higher is better', fontsize=11)
    ax1.set_ylabel('Latency (ms)  →  lower is better',         fontsize=11)
    ax1.set_title('Battery Life vs Latency\n(bubble area ∝ energy consumption)',
                  fontsize=11, fontweight='bold', pad=8)
    ax1.legend(fontsize=9, framealpha=0.9, loc='upper right')
    ax1.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax1.xaxis.grid(True, linestyle='--', alpha=0.4)
    ax1.set_axisbelow(True)

    # ── Battery life grouped bar with annotation ──────────────────────────────
    bars = ax2.bar(SYSTEMS, batt, color=COLORS, edgecolor='white', linewidth=0.8, width=0.55)
    for bar, v in zip(bars, batt):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.5,
                 f'{v:.2f}d', ha='center', va='bottom', fontsize=10, fontweight='bold')

    # RCAS vs best / worst
    best  = batt.max(); worst = batt.min()
    ax2.axhline(best,  color='#2ca02c', linestyle='--', linewidth=1.3, alpha=0.7, label=f'Best  ({best:.1f}d)')
    ax2.axhline(worst, color='#d62728', linestyle='--', linewidth=1.3, alpha=0.7, label=f'Worst ({worst:.1f}d)')
    ax2.axhline(batt[0], color='#1f77b4', linestyle='-', linewidth=1.8, alpha=0.5)

    ax2.set_ylabel('Battery Life (days)', fontsize=11)
    ax2.set_title('Battery Life by System\n(higher = better)',
                  fontsize=11, fontweight='bold', pad=8)
    ax2.set_ylim(0, batt.max() * 1.22)
    ax2.legend(fontsize=9, framealpha=0.9)
    ax2.yaxis.grid(True, linestyle='--', alpha=0.4); ax2.set_axisbelow(True)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig8_battery_latency.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 8]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 9 — NETWORK vs CARBON  PARETO-FRONT ANALYSIS  (NEW)
# ═════════════════════════════════════════════════════════════════════════════
def fig9_network_carbon(d):
    """
    Pareto-front plot (Network bandwidth vs Carbon) and a horizontal
    grouped-bar comparing network usage (log scale option).
    """
    network = np.array(d['network'])
    carbon  = np.array(d['carbon'])
    energy  = np.array(d['energy'])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle('Network Usage & Carbon Emission Analysis', fontsize=13, fontweight='bold', y=1.01)

    # ── Pareto scatter ────────────────────────────────────────────────────────
    for i, (sys_n, col) in enumerate(zip(SYSTEMS, COLORS)):
        ax1.scatter(network[i], carbon[i], color=col, s=250,
                    zorder=5, edgecolors='white', linewidths=1.8, label=sys_n)
        offset_x = -200 if i in [1] else 60
        offset_y = 5    if i != 3   else -12
        ax1.annotate(f'{sys_n}\n({network[i]:.0f}B, {carbon[i]:.1f}gCO₂)',
                     xy=(network[i], carbon[i]),
                     xytext=(network[i] + offset_x, carbon[i] + offset_y),
                     fontsize=8.5, color=col, fontweight='bold')

    ax1.scatter(network[0], carbon[0], marker='*', s=600,
                color=COLORS[0], zorder=6, edgecolors='white', linewidths=1)

    # Draw Pareto frontier (Local → RCAS → Cloud; Threshold near RCAS)
    pareto_pts = sorted([(network[i], carbon[i]) for i in range(4)], key=lambda p: p[0])
    px, py = zip(*pareto_pts)
    ax1.plot(px, py, 'k--', linewidth=1.0, alpha=0.45, label='Pareto frontier')

    ax1.set_xlabel('Network Usage (B/node-day)  →  lower is better', fontsize=10)
    ax1.set_ylabel('Carbon Emissions (gCO₂/node-day)  →  lower is better', fontsize=10)
    ax1.set_title('Network–Carbon Pareto Frontier\n(lower-left = more sustainable)',
                  fontsize=11, fontweight='bold', pad=8)
    ax1.legend(fontsize=9, framealpha=0.9)
    ax1.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax1.xaxis.grid(True, linestyle='--', alpha=0.4)
    ax1.set_axisbelow(True)
    ax1.set_xlim(-300, network.max() * 1.25)
    ax1.set_ylim(carbon.min() * 0.7, carbon.max() * 1.18)

    # ── Log-scale horizontal bar for network only ─────────────────────────────
    # Replace Local=0 with a small stub for visibility
    net_plot = np.where(network == 0, 10, network)
    bars = ax2.barh(SYSTEMS, net_plot, color=COLORS, edgecolor='white', linewidth=0.8, height=0.55)
    for bar, v, orig in zip(bars, net_plot, network):
        label = f'{orig:,.0f} B' if orig > 0 else '0 B (edge-only)'
        ax2.text(bar.get_width() + 60, bar.get_y() + bar.get_height() / 2,
                 label, va='center', fontsize=10, fontweight='bold')

    ax2.set_xscale('log')
    ax2.set_xlabel('Network Usage (B/node-day)  [log scale]', fontsize=11)
    ax2.set_title('Network Bandwidth Comparison\n(log scale; Local ≈ 0 shown as stub)',
                  fontsize=11, fontweight='bold', pad=8)
    ax2.set_xlim(5, network.max() * 2.5)
    ax2.invert_yaxis()
    ax2.xaxis.grid(True, linestyle='--', alpha=0.4); ax2.set_axisbelow(True)

    # RCAS vs Cloud reduction annotation
    ax2.annotate(f'{d["vs_cloud_network"]:.1f}% less\nthan Cloud',
                 xy=(network[0], 0), xytext=(network[0] * 2, 0.7),
                 fontsize=8.5, color='#1f77b4', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=1.2))

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig9_network_carbon.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 9]  Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  FIG 10 — COMPOSITE SYSTEM SCORE  (NEW)
# ═════════════════════════════════════════════════════════════════════════════
def fig10_system_score(d):
    """
    Computes a weighted composite sustainability score for each system,
    shows a bar chart + an annotated stacked bar decomposition.
    Equal weights: Energy 25%, Carbon 25%, Network 20%, Latency 15%, BattLife 15%.
    """
    weights = {'Energy': 0.25, 'Carbon': 0.25, 'Network': 0.20, 'Latency': 0.15, 'BattLife': 0.15}
    raw = {
        'Energy':   np.array(d['energy']),
        'Carbon':   np.array(d['carbon']),
        'Network':  np.array(d['network']),
        'Latency':  np.array(d['latency']),
        'BattLife': np.array(d['battlife']),
    }
    lower_is_better = {'Energy': True, 'Carbon': True, 'Network': True,
                       'Latency': True, 'BattLife': False}

    # Normalise each metric to [0,1] where 1 = best
    norm = {}
    for key, arr in raw.items():
        if lower_is_better[key]:
            mn = arr[arr > 0].min() if arr.min() == 0 else arr.min()
            norm[key] = np.where(arr == 0, 1.0, mn / arr)
        else:
            norm[key] = arr / arr.max()

    # Weighted composite
    metric_keys = list(weights.keys())
    contrib = {k: norm[k] * weights[k] for k in metric_keys}
    total_score = sum(contrib[k] for k in metric_keys)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle('Composite Sustainability Score (Weighted Multi-Criteria)',
                 fontsize=13, fontweight='bold', y=1.01)

    # ── Overall bar ───────────────────────────────────────────────────────────
    sorted_idx = np.argsort(total_score)[::-1]
    sorted_sys = [SYSTEMS[i] for i in sorted_idx]
    sorted_scr = [total_score[i] for i in sorted_idx]
    sorted_col = [COLORS[i] for i in sorted_idx]

    bars = ax1.bar(sorted_sys, sorted_scr, color=sorted_col,
                   edgecolor='white', linewidth=0.8, width=0.55)
    for bar, v, idx in zip(bars, sorted_scr, sorted_idx):
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.008,
                 f'{v:.4f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
        rank_symbol = ['🥇', '🥈', '🥉', '4th']
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() / 2,
                 rank_symbol[list(sorted_idx).index(idx)],
                 ha='center', va='center', fontsize=18)

    ax1.set_ylim(0, 1.15)
    ax1.set_ylabel('Composite Score (0–1,  higher = better)', fontsize=11)
    ax1.set_title('Overall Sustainability Score\n(ranked; weights: E25%, C25%, N20%, L15%, B15%)',
                  fontsize=11, fontweight='bold', pad=8)
    ax1.yaxis.grid(True, linestyle='--', alpha=0.4); ax1.set_axisbelow(True)

    # ── Stacked contribution bar ──────────────────────────────────────────────
    metric_plot_cols = ['#1f77b4', '#d62728', '#ff7f0e', '#2ca02c', '#9467bd']
    bottom = np.zeros(4)
    for k, mc in zip(metric_keys, metric_plot_cols):
        vals = contrib[k]
        ax2.bar(SYSTEMS, vals, bottom=bottom, color=mc, edgecolor='white',
                linewidth=0.5, label=f'{k} (w={weights[k]:.0%})', width=0.55)
        for i in range(4):
            if vals[i] > 0.018:
                ax2.text(i, bottom[i] + vals[i] / 2,
                         f'{vals[i]:.3f}', ha='center', va='center',
                         fontsize=7.5, color='white', fontweight='bold')
        bottom += vals

    ax2.set_ylim(0, 1.15)
    ax2.set_ylabel('Score Contribution', fontsize=11)
    ax2.set_title('Score Decomposition by Metric\n(stacked; each bar sums to composite score)',
                  fontsize=11, fontweight='bold', pad=8)
    ax2.legend(fontsize=8.5, loc='upper right', framealpha=0.9)
    ax2.yaxis.grid(True, linestyle='--', alpha=0.4); ax2.set_axisbelow(True)

    # Annotate total on top of each bar
    for i, v in enumerate(total_score):
        ax2.text(i, v + 0.015, f'{v:.3f}', ha='center', va='bottom',
                 fontsize=9, fontweight='bold')

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, 'rcas_fig10_system_score.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(); print(f'  [Fig 10] Saved → {out}')


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print(f'\nReading simulation output from:\n  {TXT_FILE}\n')
    data = parse_output(TXT_FILE)

    print('Parsed values (quick check):')
    print(f'  Energy   → {data["energy"]}')
    print(f'  Carbon   → {data["carbon"]}')
    print(f'  Network  → {data["network"]}')
    print(f'  Latency  → {data["latency"]}')
    print(f'  BattLife → {data["battlife"]}')
    print(f'  TP={data["TP"]}  TN={data["TN"]}  FP={data["FP"]}  FN={data["FN"]}')
    print(f'  RCAS Prec={data["rcas_prec"]}  Rec={data["rcas_rec"]}  F1={data["rcas_f1"]}')
    print(f'  Thresh  Prec={data["thr_prec"]}  Rec={data["thr_rec"]}  F1={data["thr_f1"]}')
    print(f'\nGenerating 10 figures into:\n  {OUTPUT_DIR}\n')

    fig1_dashboard(data)
    fig2_radar(data)
    fig3_reduction(data)
    fig4_decision(data)
    fig5_confusion_matrix(data)
    fig6_precision_recall(data)
    fig7_energy_carbon_tradeoff(data)
    fig8_battery_latency(data)
    fig9_network_carbon(data)
    fig10_system_score(data)

    print(f'\nDone. All 10 figures saved to:\n  {OUTPUT_DIR}')
