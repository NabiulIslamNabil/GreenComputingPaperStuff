#!/usr/bin/env python3
"""
=============================================================================
Padma River CA-EDR Synthetic Dataset Generator  —  v5
Steps 0 – 7  (generation, evaluation, labelling, validation)
Step 8 (Decision Tree training) is intentionally excluded.
=============================================================================

Methodology references:
  Chia et al. 2023      — PCD / KLD / KS model evaluation framework
  Leigh et al. 2019     — out-of-range anomaly injection, physical plausibility
  Wang et al. 2024      — AC-i multi-parameter anomaly taxonomy
  Zhao et al. 2023      — compensation degree, subtype validation
  Huang 2025            — synthetic augmentation volume guidance
  ECR 2023 Tofshil-2   — Bangladesh inland surface water quality thresholds

Simulation config:
  Nodes       : 8
  Days        : 15
  Interval    : 10 minutes  →  144 readings / day / node
  Total rows  : 8 × 15 × 144 = 17,280

Label rule (ECR 2023, Tofshil-2, pp. 53 & 57):
  label = 1  if  DO < 4.0 mg/L
              OR  pH < 6.0
              OR  pH > 8.5
              OR  TDS > 1000 mg/L
  Temperature is excluded from labelling (seasonal variation, not a
  pollution indicator for natural Padma River conditions).

Physical plausibility bounds (corrected from v4 — see process document):
  pH            :  4.0  –  10.0      (river practical)
  temperature_C :  15.0 –  36.0 °C   (Bangladesh river seasonal range)
  TDS_mgl       :  50.0 –  5000.0    (freshwater river; NOT seawater)
  DO_mgl        :  0.1  –  9.5       (O₂ solubility at 25 °C ≈ 8.26 mg/L)

Usage:
  pip install sdv pandas numpy scipy openpyxl
  python generate_padma_dataset_v5.py

Input  : seed_dataset_final_v5.csv    (same folder)
Outputs: padma_synthetic_17280_v5.csv
         padma_synthetic_17280_v5.xlsx
         model_evaluation_metrics_v5.csv
         model_evaluation_metrics_v5.xlsx
         validation_report_v5.txt
=============================================================================
"""

from sdv.single_table import (
    CTGANSynthesizer,
    TVAESynthesizer,
    CopulaGANSynthesizer,
    GaussianCopulaSynthesizer,
)
from sdv.metadata import SingleTableMetadata
import sys
import warnings
import textwrap
from datetime import date, timedelta
from collections import Counter

import pandas as pd
import numpy as np
from scipy import stats

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SEED_CSV = "seed_dataset_final_v5.csv"
NODES = 8
DAYS = 15
INTERVAL_MIN = 10
READINGS_DAY = 1440 // INTERVAL_MIN       # 144 readings per node per day
FINAL_ROWS = NODES * DAYS * READINGS_DAY  # 17,280
EVAL_ROWS = 500                         # rows for model quality evaluation
EPOCHS = 500                         # training epochs for GAN / TVAE
RANDOM_SEED = 42
START_DATE = date(2025, 1, 1)

# Columns the SDV models train on — all metadata & label columns are excluded.
FEATURE_COLS = ["pH", "temperature_C", "TDS_mgl", "DO_mgl"]

BOUNDS = {
    "pH": (4.0,   10.0),
    "temperature_C": (15.0,  36.0),
    "TDS_mgl": (50.0,  5000.0),
    "DO_mgl": (0.1,   9.5),
}

# ECR 2023 anomaly thresholds
ECR_DO_LOW = 4.0
ECR_pH_LOW = 6.0
ECR_pH_HIGH = 8.5
ECR_TDS_MAX = 1000.0

EXPECTED_SUBTYPES = [
    "AC1_DO_only",
    "AC1_pH_low_only",
    "AC1_pH_high_only",
    "AC1_TDS_only",
    "AC2_DO_pH",
    "AC3_DO_pH_TDS",
    "multi_other",
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def ecr_label(pH, TDS, DO):
    if DO < ECR_DO_LOW or pH < ECR_pH_LOW or pH > ECR_pH_HIGH or TDS > ECR_TDS_MAX:
        return 1
    return 0


def get_anomaly_subtype(pH, TDS, DO):
    do_anom = DO < ECR_DO_LOW
    ph_low = pH < ECR_pH_LOW
    ph_high = pH > ECR_pH_HIGH
    tds_anom = TDS > ECR_TDS_MAX
    ph_anom = ph_low or ph_high

    if do_anom and ph_anom and tds_anom:
        return "AC3_DO_pH_TDS"
    if do_anom and ph_anom and not tds_anom:
        return "AC2_DO_pH"
    if do_anom and tds_anom and not ph_anom:
        return "AC2_DO_TDS"
    if ph_anom and tds_anom and not do_anom:
        return "AC2_pH_TDS"
    if do_anom and not ph_anom and not tds_anom:
        return "AC1_DO_only"
    if ph_low and not do_anom and not tds_anom:
        return "AC1_pH_low_only"
    if ph_high and not do_anom and not tds_anom:
        return "AC1_pH_high_only"
    if tds_anom and not do_anom and not ph_anom:
        return "AC1_TDS_only"
    return "multi_other"


def compute_pcd(real_df, syn_df, cols):
    C_real = real_df[cols].corr().values
    C_syn = syn_df[cols].corr().values
    return float(np.linalg.norm(C_real - C_syn, "fro"))


def compute_kld_per_col(real_df, syn_df, cols, n_bins=20):
    kld = {}
    for col in cols:
        r = real_df[col].values
        s = syn_df[col].values
        lo = min(r.min(), s.min())
        hi = max(r.max(), s.max())
        if lo == hi:
            kld[col] = 0.0
            continue
        bins = np.linspace(lo, hi, n_bins + 1)
        p, _ = np.histogram(r, bins=bins, density=True)
        q, _ = np.histogram(s, bins=bins, density=True)
        p = p + 1e-10
        p /= p.sum()
        q = q + 1e-10
        q /= q.sum()
        kld[col] = float(np.sum(p * np.log(p / q)))
    return kld


def compute_ks_per_col(real_df, syn_df, cols):
    ks = {}
    for col in cols:
        stat, pval = stats.ks_2samp(real_df[col].values, syn_df[col].values)
        ks[col] = {"D": float(stat), "p": float(pval)}
    return ks


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 — Load and prepare seed
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 0 — Loading seed dataset  (seed_dataset_final_v5.csv)")

try:
    seed_full = pd.read_csv(SEED_CSV)
except FileNotFoundError:
    sys.exit(f"ERROR: '{SEED_CSV}' not found. Place it in the same folder.")

print(f"  Loaded {len(seed_full)} rows from '{SEED_CSV}'")

n_anom = (seed_full["label"] == 1).sum()
n_norm = (seed_full["label"] == 0).sum()
print(f"  Seed anomaly (label=1): {n_anom}  ({n_anom/len(seed_full)*100:.1f}%)")
print(f"  Seed normal  (label=0): {n_norm}  ({n_norm/len(seed_full)*100:.1f}%)")

if "anomaly_type" in seed_full.columns:
    print("\n  Seed anomaly subtype breakdown:")
    for atype, cnt in seed_full[seed_full["label"] == 1]["anomaly_type"].value_counts().items():
        print(f"    {atype:<30} {cnt:>3} rows")

COLS_TO_DROP = ["seed_row_id", "source", "label", "anomaly_type", "label_reason"]
seed_train = seed_full.drop(
    columns=[c for c in COLS_TO_DROP if c in seed_full.columns]
).copy()

missing = [c for c in FEATURE_COLS if c not in seed_train.columns]
if missing:
    sys.exit(f"ERROR: Expected feature columns missing from seed: {missing}")
seed_train = seed_train[FEATURE_COLS]

print(f"\n  Training columns for SDV: {FEATURE_COLS}")
print(f"\n  Seed statistics:")
print(seed_train.describe().round(3).to_string())


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Build SDV metadata
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 1 — Building SDV metadata")

metadata = SingleTableMetadata()
metadata.detect_from_dataframe(seed_train)
for col in FEATURE_COLS:
    metadata.update_column(col, sdtype="numerical")

print("  Metadata configured — all 4 columns marked numerical.")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Train all 4 SDV models
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 2 — Training 4 SDV models on 100-row enriched seed (v5)")

model_configs = {
    "CTGAN": CTGANSynthesizer(metadata, epochs=EPOCHS, verbose=False),
    "TVAE": TVAESynthesizer(metadata, epochs=EPOCHS),
    "CopulaGAN": CopulaGANSynthesizer(metadata, epochs=EPOCHS, verbose=False),
    "GaussianCopula": GaussianCopulaSynthesizer(metadata),
}

trained_models = {}
for name, model in model_configs.items():
    print(f"  Training {name:<20}", end="", flush=True)
    model.fit(seed_train)
    trained_models[name] = model
    print("✓")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Evaluate models
# ─────────────────────────────────────────────────────────────────────────────
section(f"STEP 3 — Evaluating models on {EVAL_ROWS} eval rows")

eval_records = []
eval_generated = {}

for name, model in trained_models.items():
    print(f"\n  [{name}]")
    gen = model.sample(num_rows=EVAL_ROWS)
    eval_generated[name] = gen

    pcd = compute_pcd(seed_train, gen, FEATURE_COLS)
    kld_cols = compute_kld_per_col(seed_train, gen, FEATURE_COLS)
    kld_mean = sum(kld_cols.values()) / len(FEATURE_COLS)
    kld_tot = sum(kld_cols.values())
    ks_cols = compute_ks_per_col(seed_train, gen, FEATURE_COLS)
    ks_mean_d = np.mean([v["D"] for v in ks_cols.values()])
    ks_pass = sum(1 for v in ks_cols.values() if v["p"] > 0.05)
    composite = pcd + kld_mean + ks_mean_d

    print(f"    PCD         = {pcd:.6f}")
    print(f"    KLD total   = {kld_tot:.6f}   KLD mean = {kld_mean:.6f}")
    for col, kv in kld_cols.items():
        flag = " ← CRITICAL: pH/TDS distribution may be smoothed" if (col in ("pH", "TDS_mgl") and kv > 0.3) else ""
        print(f"       {col:<16} KLD = {kv:.6f}{flag}")
    print(f"    KS mean D   = {ks_mean_d:.6f}   ({ks_pass}/{len(FEATURE_COLS)} cols pass p>0.05)")
    for col, kv in ks_cols.items():
        flag = "✓ PASS" if kv["p"] > 0.05 else "✗ FAIL ← consider different model"
        print(f"       {col:<16} D={kv['D']:.4f}  p={kv['p']:.4f}  {flag}")
    print(f"    COMPOSITE   = {composite:.6f}")

    eval_records.append({
        "Model": name,
        "PCD": round(pcd, 6),
        "KLD_pH": round(kld_cols["pH"], 6),
        "KLD_temp": round(kld_cols["temperature_C"], 6),
        "KLD_TDS": round(kld_cols["TDS_mgl"], 6),
        "KLD_DO": round(kld_cols["DO_mgl"], 6),
        "KLD_total": round(kld_tot, 6),
        "KLD_mean": round(kld_mean, 6),
        "KS_pH_D": round(ks_cols["pH"]["D"], 6),
        "KS_pH_p": round(ks_cols["pH"]["p"], 6),
        "KS_temp_D": round(ks_cols["temperature_C"]["D"], 6),
        "KS_temp_p": round(ks_cols["temperature_C"]["p"], 6),
        "KS_TDS_D": round(ks_cols["TDS_mgl"]["D"], 6),
        "KS_TDS_p": round(ks_cols["TDS_mgl"]["p"], 6),
        "KS_DO_D": round(ks_cols["DO_mgl"]["D"], 6),
        "KS_DO_p": round(ks_cols["DO_mgl"]["p"], 6),
        "KS_mean_D": round(ks_mean_d, 6),
        "KS_pass_cols": ks_pass,
        "Composite": round(composite, 6),
    })

metrics_df = pd.DataFrame(eval_records).set_index("Model").sort_values("Composite")

print("\n" + "─" * 70)
print("MODEL RANKING — lowest Composite wins:")
print(metrics_df[["PCD", "KLD_mean", "KS_mean_D", "KS_pass_cols", "Composite"]].to_string())
print("─" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Select winner
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 4 — Selecting winning model")

winner_name = metrics_df.index[0]
winner_model = trained_models[winner_name]
winner_row = metrics_df.loc[winner_name]

print(f"  WINNER: {winner_name}")
print(f"  PCD       = {winner_row['PCD']:.6f}")
print(f"  KLD mean  = {winner_row['KLD_mean']:.6f}")
print(f"  KS mean D = {winner_row['KS_mean_D']:.6f}")
print(f"  KS pass   = {int(winner_row['KS_pass_cols'])}/{len(FEATURE_COLS)} columns")
print(f"  Composite = {winner_row['Composite']:.6f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Generate final dataset
# ─────────────────────────────────────────────────────────────────────────────
section(f"STEP 5 — Generating final {FINAL_ROWS:,} rows using {winner_name}")

synthetic_raw = winner_model.sample(num_rows=FINAL_ROWS)

# Physical bounds clamping
print("\n  Physical bounds clamping:")
print(f"  {'Column':<16} {'Bound':<18} {'Clamped':>8}  {'Pre-clamp range'}")
print("  " + "-" * 62)

clamped_rows = set()
for col, (lo, hi) in BOUNDS.items():
    before = synthetic_raw[col].copy()
    synthetic_raw[col] = synthetic_raw[col].clip(lower=lo, upper=hi)
    changed = (synthetic_raw[col] != before)
    n_ch = changed.sum()
    clamped_rows.update(changed[changed].index.tolist())
    range_str = f"[{before.min():.3f}, {before.max():.3f}]"
    bound_str = f"[{lo}, {hi}]"
    note = "" if n_ch == 0 else f"  ← {n_ch} values clamped"
    print(f"  {col:<16} {bound_str:<18} {n_ch:>8}  {range_str}{note}")

n_clamped = len(clamped_rows)
print(f"\n  Total rows needing clamping : {n_clamped} / {FINAL_ROWS} ({n_clamped/FINAL_ROWS*100:.2f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Re-apply labels
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 6 — Re-applying ECR 2023 anomaly labels")

labels = []
subtypes = []
for i in synthetic_raw.index:
    row_pH = synthetic_raw.loc[i, "pH"]
    row_TDS = synthetic_raw.loc[i, "TDS_mgl"]
    row_DO = synthetic_raw.loc[i, "DO_mgl"]
    lbl = ecr_label(row_pH, row_TDS, row_DO)
    labels.append(lbl)
    if lbl == 1:
        subtypes.append(get_anomaly_subtype(row_pH, row_TDS, row_DO))
    else:
        subtypes.append("normal")

synthetic_raw["label"] = labels
synthetic_raw["anomaly_type"] = subtypes

anomaly_count = sum(labels)
anomaly_pct = anomaly_count / FINAL_ROWS * 100
print(f"\n  Anomaly rows (label=1) : {anomaly_count:>6}  ({anomaly_pct:.2f}%)")
print(f"  Normal  rows (label=0) : {FINAL_ROWS-anomaly_count:>6}  ({100-anomaly_pct:.2f}%)")

print("\n  Generated anomaly subtype distribution:")
subtype_counts = Counter([s for s in subtypes if s != "normal"])
for st, cnt in sorted(subtype_counts.items(), key=lambda x: -x[1]):
    pct = cnt / anomaly_count * 100 if anomaly_count > 0 else 0
    print(f"    {st:<25} {cnt:>6}  ({pct:.1f}% of anomalies)")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Assign temporal structure
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 7 — Assigning node_id, date, day_of_simulation, time_of_day_min")

node_ids = []
dates = []
days_of_sim = []
times_of_day = []

for node in range(1, NODES + 1):
    for day in range(1, DAYS + 1):
        for interval in range(READINGS_DAY):
            node_ids.append(f"NODE_{node:02d}")
            dates.append(str(START_DATE + timedelta(days=day - 1)))
            days_of_sim.append(day)
            times_of_day.append(interval * INTERVAL_MIN)

final_df = pd.DataFrame({
    "date": dates,
    "node_id": node_ids,
    "day_of_simulation": days_of_sim,
    "time_of_day_min": times_of_day,
    "pH": synthetic_raw["pH"].values.round(3),
    "temperature_C": synthetic_raw["temperature_C"].values.round(2),
    "TDS_mgl": synthetic_raw["TDS_mgl"].values.round(2),
    "DO_mgl": synthetic_raw["DO_mgl"].values.round(3),
    "label": synthetic_raw["label"].values,
    "anomaly_type": synthetic_raw["anomaly_type"].values,
})

print(f"\n  Final dataset shape : {final_df.shape}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7B — Validation Checks
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 7B — Three Validation Checks")

validation_lines = []

def vprint(line=""):
    print(line)
    validation_lines.append(line)


vprint("=" * 65)
vprint("VALIDATION REPORT  —  seed_dataset_final_v5.csv  →  17,280 rows")
vprint("=" * 65)

# ── Validation A: KS test (Fixed) ────────────────────────────────────────────
vprint("\n── VALIDATION A: KS Test — seed vs. final generated dataset ──")
vprint("  Method: Chia et al. 2023, Eq. 5 (with Fix 2)")
vprint("  Using random sample of final dataset to match evaluation size")
vprint("  Pass criterion: D < 0.20 (more reliable when n_seed << n_synthetic)\n")

val_a_pass = True
for col in FEATURE_COLS:
    sample_for_ks = final_df[col].sample(EVAL_ROWS, random_state=RANDOM_SEED).values
    d_stat, p_val = stats.ks_2samp(seed_train[col].values, sample_for_ks)
    status = "PASS ✓" if d_stat < 0.20 else "FAIL ✗"
    if d_stat >= 0.20:
        val_a_pass = False
    vprint(f"  {col:<16}  D={d_stat:.4f}  p={p_val:.4f}  →  {status}")
    if d_stat >= 0.20 and col in ("pH", "TDS_mgl"):
        vprint(f"  !! CRITICAL: {col} KS fail — generator may not have reproduced anomaly distribution")

vprint(f"\n  Overall Validation A: {'PASS ✓' if val_a_pass else 'FAIL ✗ — review KS failures above'}")

# ── Validation B: Physical bounds ───────────────────────────────────────────
vprint("\n── VALIDATION B: Physical Bounds Check ──")
vprint("  Method: Leigh et al. 2019 physical plausibility\n")

val_b_pass = True
total_viol = 0
for col, (lo, hi) in BOUNDS.items():
    n_lo = (final_df[col] < lo).sum()
    n_hi = (final_df[col] > hi).sum()
    n_viol = n_lo + n_hi
    total_viol += n_viol
    status = "PASS ✓" if n_viol == 0 else f"FAIL ✗ — {n_viol} rows out of bounds"
    if n_viol > 0:
        val_b_pass = False
    vprint(f"  {col:<16}  range=[{final_df[col].min():.2f}, {final_df[col].max():.2f}]"
           f"  violations={n_viol}  →  {status}")

vprint(f"\n  Total violations  : {total_viol}")
vprint(f"  Overall Validation B: {'PASS ✓' if val_b_pass else 'FAIL ✗'}")

# ── Validation C: Anomaly subtypes ──────────────────────────────────────────
vprint("\n── VALIDATION C: Anomaly Subtype Presence Check ──")
vprint("  Method: Zhao et al. 2023 / Wang et al. 2024 AC-i taxonomy\n")

subtype_in_final = Counter(final_df[final_df["label"] == 1]["anomaly_type"])
critical_types = ["AC1_DO_only", "AC1_pH_low_only", "AC1_pH_high_only", "AC1_TDS_only"]
important_types = ["AC2_DO_pH", "AC3_DO_pH_TDS"]

val_c_pass = True
for st in critical_types:
    cnt = subtype_in_final.get(st, 0)
    status = "PASS ✓" if cnt > 0 else "FAIL ✗ — generator did not learn this subtype"
    if cnt == 0:
        val_c_pass = False
    pct = cnt / anomaly_count * 100 if anomaly_count > 0 else 0
    vprint(f"  {st:<25}  {cnt:>6} rows  ({pct:.1f}%)  →  {status}")

for st in important_types:
    cnt = subtype_in_final.get(st, 0)
    pct = cnt / anomaly_count * 100 if anomaly_count > 0 else 0
    status = "present ✓" if cnt > 0 else "absent"
    vprint(f"  {st:<25}  {cnt:>6} rows  ({pct:.1f}%)  →  {status}")

vprint(f"\n  Overall Validation C: {'PASS ✓' if val_c_pass else 'FAIL ✗ — see above'}")

# Overall summary
overall = val_a_pass and val_b_pass and val_c_pass
vprint("\n" + "=" * 65)
vprint(f"OVERALL VALIDATION: {'ALL PASS ✓' if overall else 'ONE OR MORE FAILURES — see above'}")
vprint("=" * 65)
vprint(f"\n  Winning model   : {winner_name}")
vprint(f"  Generated rows  : {FINAL_ROWS:,}")
vprint(f"  Anomaly (label=1): {anomaly_count:,}  ({anomaly_pct:.2f}%)")
vprint(f"  Validation A (KS)         : {'PASS' if val_a_pass else 'FAIL'}")
vprint(f"  Validation B (bounds)     : {'PASS' if val_b_pass else 'FAIL'}")
vprint(f"  Validation C (subtypes)   : {'PASS' if val_c_pass else 'FAIL'}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Save outputs
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 8 — Saving outputs")

FINAL_CSV = "padma_synthetic_17280_v5.csv"
METRICS_CSV = "model_evaluation_metrics_v5.csv"
REPORT_TXT = "validation_report_v5.txt"

final_df.to_csv(FINAL_CSV, index=False)
metrics_df.reset_index().to_csv(METRICS_CSV, index=False)
with open(REPORT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(validation_lines))

print(f"  Saved: {FINAL_CSV}")
print(f"  Saved: {METRICS_CSV}")
print(f"  Saved: {REPORT_TXT}")

print("\n" + "=" * 70)
print("GENERATION COMPLETE")
print("=" * 70)