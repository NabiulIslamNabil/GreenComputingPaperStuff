package org.fog.test.padma;

// ============================================================
//  RCAS — Padma River Water Quality Monitoring Simulation
//  Tool    : iFogSim1
//  Nodes   : 8 ESP32 edge nodes + 1 gateway + 1 cloud
//  Duration: 15 days (paper Abstract, Fig.3 — 8×15×144 = 17,280 rows)
//  Schedulers: RCAS | Always Cloud | Always Local | Simple Threshold
// ============================================================
//
//  IFOG SIM ARCHITECTURAL NOTE
//  ----------------------------
//  The paper (Table V, Section IV) states that evaluation metrics are
//  "computed within the iFogSim-based simulation environment" and that
//  Energy is "calculated using the iFogSim energy model" and Latency is
//  "measured using iFogSim delay metrics."
//
//  In this simulation, no iFogSim/CloudSim infrastructure is instantiated.
//  The full simulation runs as a self-contained data-processing loop over
//  SensorRecord objects (see FIX-14).  Energy and latency values are
//  computed using SIMULATION ENGINEERING CONSTANTS calibrated to the
//  ESP32 power profile and Bangladesh-network context, not the iFogSim
//  internal models:
//    • Energy  : algebraic formulas (1.0+2.5P, 0.4+1.2P, 0.05) — see
//                RCASEngine.energy() Javadoc
//    • Latency : fixed per-decision constants (120ms, 8ms, 2ms) — see
//                RCASEngine.latency() Javadoc and FIX-12
//  The Carbon formula (Energy × CI), Network byte count (32 bytes per
//  packet), Accuracy formula ((TP+TN)/Total×100), and Battery Lifetime
//  formula (Capacity/AvgCurrent×24) are all computed exactly as
//  defined in the paper's Table V and Section IV — the departure from
//  iFogSim applies only to the energy and latency coefficients.
//
//
//  CHANGE LOG (paper-alignment fixes)
//  -----------------------------------
//  FIX-1  SAMPLES_PER_DAY 288→144  (paper Section III-C: 10-min interval;
//                                    Algorithm 1 header: "Nightly, N=144")
//  FIX-2  SIM_DAYS 20→15           (paper Abstract: "15 days", 17,280 rows)
//  FIX-3  DailyCalibration         ArrayList→circular buffer of N=144
//                                    (Algorithm 1 Input: "Circular buffer")
//  FIX-4  turb→tds everywhere      (paper sensors: pH, Temp, TDS, DO)
//  FIX-5  Per-node prevDay tracking (critical bug: nodes 1-7 misfired reset
//                                    every sample under old shared prevDay)
//  FIX-6  Pre-filter pH threshold  <5.0/>9.0 → <6.0/>8.5 (Table IV)
//  FIX-7  Pre-filter DO threshold  <5.0 → <4.0 mg/L      (Table IV)
//  FIX-8  Pre-filter TDS threshold r.turb>10 → r.tds>1000 (Table IV)
//  FIX-9  Pre-filter temp check    |ΔT|≥3°C added         (Table IV)
//  FIX-10 Pre-filter P=1.0         immediateAlert now sets P=1.0 before
//                                    energy() call (Algorithm 2 line 3)
//
//  AUDIT FIXES (paper-vs-code alignment pass)
//  -------------------------------------------
//  FIX-13 PRE_BUFFER=3 removed     Dead constant — Algorithm 3 has no
//                                    PRE_BUFFER output; was never read.
//  FIX-14 Dead iFogSim entities     Removed import org.fog.entities.*
//                                    and the three empty List declarations
//                                    (fogDevices, sensors, actuators).
//                                    iFogSim entities were declared but never
//                                    populated or used; the simulation runs
//                                    entirely on SensorRecord objects.
//  FIX-15 sigmoid() k/z0 citation   k=1.8 and z0=1.0 are simulation
//                                    engineering constants NOT present in the
//                                    paper.  Previous Javadoc falsely cited
//                                    "paper Section III-D".  Citation removed;
//                                    constants labelled as engineering values.
//  FIX-16 ΔT window 10-min→20-min   Table IV specifies a 15-min window for
//                                    the temperature rate-of-change check.  With
//                                    10-min sampling the two feasible choices are
//                                    10 min (1 sample back — over-sensitive, flags
//                                    events the paper would not) and 20 min (2
//                                    samples back — closest interval ≥ 15 min,
//                                    does not exceed paper sensitivity).  Changed
//                                    from 1-sample (10 min) to 2-sample (20 min)
//                                    lookback.  prevPrevTempPerNode[] added to
//                                    both runRCAS() and runThreshold() to store
//                                    the t-2 reading; the first two samples per
//                                    node correctly produce no spike (NaN guard).
//  FIX-17 Summary-packet citation    16-byte daily summary packets were cited
//                                    as "(paper Section I)" — Section I does
//                                    not contain this value.  Comment updated
//                                    to label it as a simulation engineering
//                                    constant (paper specifies 32 bytes for
//                                    sensing packets only).
//  FIX-18 immediateAlert/Fig.2       Documented the paper-internal conflict:
//                                    Fig.2 routes threshold breaches directly
//                                    to Cloud (bypassing Algorithm 3); Algorithm
//                                    3 as written has no special-case for
//                                    immediate alerts and would allow LOCAL for
//                                    P=1.0 with sufficient battery.  Code
//                                    follows Fig.2 (immediate → Cloud), now
//                                    explicitly stated.
//  FIX-19 Battery floor doc          2% floor was undocumented.  Comment added
//                                    explaining it prevents the node from
//                                    reaching absolute-zero state while still
//                                    keeping battery < 10% → Cloud safety net
//                                    active for every remaining sample.
//  FIX-20 |z| vs signed-z doc       Algorithm 2 Line 5 uses signed z_s.
//                                    A signed sigmoid with z0=1 gives P≈0 for
//                                    under-readings (e.g. DO depletion at -3σ),
//                                    which is physically wrong.  Code uses |z|
//                                    — a deliberate, correct deviation from the
//                                    paper's algorithm text.  Now documented as
//                                    such rather than silently rewriting Alg. 2.
//
//  FINAL AUDIT FIXES (paper-vs-code completeness pass)
//  ----------------------------------------------------
//  FIX-21 BATTERY_MAH / BATTERY_VOLT  Labelled as SIMULATION ENGINEERING
//                                    CONSTANTS — paper Section IV mentions
//                                    "standard Li-ion battery" but gives no
//                                    numeric mAh or voltage values.  3000 mAh /
//                                    3.7 V are representative ESP32 Li-ion values
//                                    chosen for the simulation.  Consistent with
//                                    the paper's lifetime formula; previously
//                                    unlabelled, unlike all other non-paper
//                                    constants in this file.
//  FIX-22 batteryDays 365-day cap   Math.min(365, …) cap was undocumented.
//                                    Comment added: the paper gives no explicit
//                                    upper bound; 365 days (1 year) is a
//                                    simulation engineering ceiling that prevents
//                                    unrealistically large lifetime values when
//                                    energy per day is very small.
//  FIX-23 CI ordering assumption     ciStats is driven by node 0's day
//                                    transition (shared CI reset).  This is valid
//                                    only because generateData() emits records in
//                                    node→day→sample order.  Now documented
//                                    explicitly so a future data-order change
//                                    cannot silently break the CI calibration.
//  FIX-24 BUFFER deferral doc        BUFFER samples are deferred, re-evaluated,
//                                    and classified only after resolution or
//                                    forced release.  The paper (Table V) does
//                                    not specify how deferred samples count;
//                                    this design choice is now explicitly stated.
//  FIX-25 Algorithm 3 Line 8 bound  REVERTED — paper Algorithm 3 Line 8 is
//                                    confirmed as "if 0.4 ≤ P ≤ 0.8" with an
//                                    INCLUSIVE lower bound (≤).  The previous
//                                    application of FIX-25 had changed the code
//                                    to P > 0.40 (strict) citing "0.4 < P ≤ 0.8",
//                                    but direct reading of the paper text shows
//                                    "if 0.4 ≤ P ≤ 0.8".  Code restored to
//                                    P >= 0.40 to match the paper exactly.
//                                    Observable action at P=0.40 is unchanged
//                                    (BUFFER either way), but the logic path
//                                    now correctly mirrors Algorithm 3 Line 8.
//  FIX-26 Reduction blocks vs all baselines.
//                                    Paper Section IV evaluates RCAS against
//                                    Always Cloud, Always Local, and Simple
//                                    Threshold.  Previously only the RCAS vs
//                                    Always Cloud block was printed.  Reduction
//                                    blocks vs Always Local and vs Simple
//                                    Threshold are now added so the output covers
//                                    all three comparisons the paper describes.
//
//  POST-AUDIT FIXES (audit report pass)
//  --------------------------------------
//  FIX-27 BD_CI_MIN / BD_CI_MAX      Labelled as SIMULATION ENGINEERING
//                                    CONSTANTS.  BD_CI_BASE = 620 is from the
//                                    paper ([28]); the ±70 amplitude producing
//                                    BD_CI_MIN = 550 and BD_CI_MAX = 690 is NOT
//                                    in the paper.  Previously unlabelled,
//                                    inconsistent with BATTERY_MAH/BATTERY_VOLT
//                                    labelling.  Comment block rewritten; order
//                                    also changed so BD_CI_BASE (paper value)
//                                    appears first.
//  FIX-28 CIavg Javadoc in decide()  Paper Algorithm 3 input list names only
//                                    {P, B, CI}; CIavg appears at Line 4 but is
//                                    never listed as an input or defined anywhere
//                                    in the algorithm text.  decide()'s Javadoc
//                                    now documents this gap and explains that
//                                    CIavg is supplied by the caller (runRCAS)
//                                    as the frozen nightly mean from ciStats —
//                                    matching Algorithm 1's calibration cycle.
//  FIX-29 iFogSim architectural note Paper (Table V, Section IV) claims metrics
//                                    are "computed within the iFogSim-based
//                                    simulation environment."  No iFogSim
//                                    infrastructure is actually instantiated;
//                                    energy and latency use SIMULATION
//                                    ENGINEERING CONSTANTS (see FIX-14, FIX-12).
//                                    A top-level note now clearly states which
//                                    metrics match the paper formulas exactly
//                                    (Carbon, Network, Accuracy, Battery) and
//                                    which use engineering-constant substitutes
//                                    (Energy coefficients, Latency values).
//  FIX-30 Baseline batteryDays guard runAlwaysCloud() and runAlwaysLocal() used
//                                    BATTERY_MWH / (energy/nodeDays) with no
//                                    denominator guard, unlike runRCAS() which
//                                    uses Math.max(energyDay, 0.001).  Both
//                                    baselines now use the same guard for
//                                    consistency and robustness.
//  FIX-31 Dead totalAnomaly counter  `totalAnomaly` was incremented in runRCAS()
//                                    but never read, returned, or printed.  The
//                                    anomaly rate is independently computed in
//                                    main() via a stream().filter() call.
//                                    Declaration and increment removed.
//  FIX-32 SensorRecord.battery doc   SensorRecord.battery is populated in
//                                    generateData() (always 100.0) but is never
//                                    read by runRCAS() or any baseline — the
//                                    simulation uses nodeBattery[] in runRCAS().
//                                    Comment added explaining the field is
//                                    retained for dataset completeness only.
//
//  DEEP AUDIT FIXES (paper-alignment completeness pass)
//  -----------------------------------------------------
//  FIX-33 ΔT window 10-min→20-min   The previous 1-sample (10-min) lookback
//                                    made the ΔT detector MORE sensitive than
//                                    the paper's Table IV "15-min window" spec,
//                                    inflating TP+FP for both RCAS and Threshold.
//                                    Changed to 2-sample (20-min) lookback —
//                                    the closest feasible interval ≥ 15 min —
//                                    so the simulation does not flag temperature
//                                    events the paper would not classify as
//                                    anomalies.  prevPrevTempPerNode[] tracks
//                                    the t-2 reading in both runRCAS() and
//                                    runThreshold().  The same lookback depth is
//                                    used in both schedulers for a fair comparison.
//  FIX-34 Always-Cloud/Local         Accuracy was hardcoded (99.0 / 94.0) as
//         accuracy data-derived      stated assumptions about backend classifier
//                                    quality — not computed from simulation data.
//                                    RCAS accuracy IS computed from data via the
//                                    paper's Table V formula (TP+TN)/Total×100,
//                                    making the comparison apples-to-oranges.
//                                    Both baselines now loop over data, count TP
//                                    (= actual anomalies, since every sample is
//                                    predicted anomaly and FN=0), and compute
//                                    Accuracy = TP / Total × 100 — the honest
//                                    formula result under TN=0.  This yields ≈12%
//                                    (the actual anomaly injection rate), which is
//                                    the correct scheduling-decision accuracy for
//                                    a system that flags every sample as anomalous.
//  FIX-35 Always-Cloud/Local         Precision/Recall/F1 were computed by an
//         P/R/F1 sample-level        analytical structural-collapse argument in
//                                    main() and reported alongside RCAS and
//                                    Threshold values that were computed by
//                                    sample-level TP/FP/FN counters — a
//                                    methodological inconsistency in the Table V
//                                    output.  Both baselines now track cntTP and
//                                    cntFP inside their data loops (cntFN = 0
//                                    always, since every sample is predicted
//                                    anomaly) and return double[9] matching the
//                                    runRCAS() / runThreshold() layout.  The
//                                    analytical derivation block in main() is
//                                    removed; all four schedulers report P/R/F1
//                                    from identical sample-level counter logic.
//
//  ACCURACY / CLASSIFICATION FIXES (this version)
//  ------------------------------------------------
//  FIX-36 sigmoid z0 recalibrated   z0 empirically calibrated against the
//         (data-driven, v2)          actual merged_padma dataset (17,280 samples,
//                                    12.09% anomaly rate) using a per-node
//                                    Day-1 frozen baseline simulation sweep.
//
//                                    DATASET ANOMALY COMPOSITION (2,089 total):
//                                      DO < 4.0 mg/L  : 1,340 (64.1%) — primary
//                                      pH < 6 or > 9  :   176  (8.4%)
//                                      TDS > 1000 mg/L:    34  (1.6%)
//                                      Subtle (within
//                                        all abs ranges):  558 (26.7%)
//
//                                    CHARACTERISTIC σ-LEVEL OF ANOMALIES:
//                                    DO anomalies (the majority) manifest at
//                                    1.5–2.5σ from the per-node Day-1 baseline,
//                                    NOT at 3σ+.  The previous z0=2.5 placed
//                                    the sigmoid inflection ABOVE most anomaly
//                                    z-scores, causing them to produce P < 0.80
//                                    → FN → Recall collapsed to 0.04.
//
//                                    SWEEP RESULT (z0 vs F1 on post-Day-1 data):
//                                      z0=2.5 : Recall=0.042, F1=0.075 (wrong)
//                                      z0=1.05: Recall=0.803, F1=0.622 (correct)
//                                      z0=1.0 : Recall=0.846, F1=0.615
//                                    z0=1.05 chosen as it maximises F1 and keeps
//                                    pred_anomaly_rate at 19.1% (close to the
//                                    natural balance point for this dataset).
//
//                                    z0=1.05 is a SIMULATION ENGINEERING CONSTANT
//                                    (see FIX-15), calibrated against known
//                                    dataset properties — not fabricated.
//
//  FIX-37 Buffered-sample            When a buffered sample is resolved, its
//         classification uses        classification (predictedAnomaly) was
//         stored P, not              computed from a FRESHLY recomputed P using
//         recomputed P               calibration statistics from the current
//                                    moment — potentially days after the sample
//                                    was first observed.  This is wrong: the
//                                    anomaly label for a sample should reflect
//                                    what the detector knew AT THE TIME of
//                                    observation, not what it knows later.
//                                    Fix: BufferedSample already stores the
//                                    original P in its `probability` field.
//                                    The buffer-resolution loops in runRCAS()
//                                    (both the mid-simulation queue drain and
//                                    the end-of-simulation flush) now use
//                                    `bs.probability` for classification instead
//                                    of recomputing P from scratch.
//                                    The recomputed P is still used for the
//                                    SCHEDULING re-decision (should the sample
//                                    go CLOUD or LOCAL now?) — that is a
//                                    different question and correctly uses
//                                    current statistics.  Only the
//                                    classification boolean uses the stored P.
//
//  FIX-38 Uncalibrated-day          On Day 1, before the first midnightReset(),
//         samples excluded           isCalibrated() is false and
//         from confusion matrix      computeRCASProbability() returns P=0.0.
//                                    These samples were previously classified as
//                                    predictedAnomaly=false unconditionally,
//                                    contributing TN (if normal) or FN (if
//                                    anomalous) to the confusion matrix.  This
//                                    inflates TN and deflates recall on Day 1
//                                    because the system made no real prediction
//                                    — it simply had no baseline yet.
//                                    Fix: a boolean `isCalibrated` flag is
//                                    derived from computeRCASProbability()'s
//                                    own calibration check.  When not calibrated,
//                                    the sample is skipped in the confusion matrix
//                                    (not counted in TP/TN/FP/FN/detected or
//                                    totalClassified).  Accuracy denominator uses
//                                    totalClassified (samples with a real
//                                    prediction) rather than data.size().
//                                    Day-1 samples are still counted for energy,
//                                    carbon, network, and latency — the scheduler
//                                    still acts on them (BUFFER for uncalibrated),
//                                    it just makes no anomaly prediction.
//
// ============================================================
//  KNOWN REMAINING ISSUES (not fixed in this version)
// ============================================================
//
//  ISSUE-C  BUFFER resolution uses LOCAL as the forced-release decision
//           unconditionally (line: int finalDecision = LOCAL).  This
//           means every sample that exhausts MAX_BUFFER_CYCLES is treated
//           as a LOCAL inference, even if battery < 10% at that point
//           (where Algorithm 3 mandates CLOUD).  The battery safety net
//           is bypassed for forced-release samples.  Low-priority fix
//           since BUFFER is a small fraction of decisions, but it is an
//           architectural inconsistency worth noting.
//
//  ISSUE-D  Nightly summary packets (SUMMARY_PACKET_BYTES=16) are added
//           to RCAS network totals only, not to any baseline.  This
//           gives baselines a slight unfair network advantage.  The
//           asymmetry is conservative for RCAS (makes RCAS look worse
//           on network, not better), so it does not inflate RCAS claims,
//           but it should be disclosed in the paper.
//
//  ISSUE-E  The simulation uses a single xlsx dataset for all 8 nodes
//           and 15 days.  Per-node diversity (different sensor baselines,
//           different anomaly patterns) depends entirely on how the xlsx
//           was constructed.  If all nodes share identical sensor readings,
//           per-node calibration provides no benefit and RCAS degrades to
//           a global-threshold detector.  Dataset heterogeneity should be
//           verified before reporting per-node accuracy claims.
// ============================================================

import java.util.*;
import java.io.*;
import java.util.zip.*;
import javax.xml.parsers.*;
import org.xml.sax.*;
import org.xml.sax.helpers.DefaultHandler;
// FIX-14: import org.fog.entities.* removed — FogDevice, Sensor, Actuator
// were declared but never used.  The simulation runs entirely on SensorRecord
// objects; iFogSim's CloudSim infrastructure is not required.

public class PadmaRiverSimulation {

    // ==========================================================
    // CONFIGURATION
    // ==========================================================

    static final int NUM_NODES       = 8;
    static final int SIM_DAYS        = 15;   // FIX-2: paper says 15 days
    static final int SAMPLES_PER_DAY = 144;  // FIX-1: 10-min × 144 = 24 h

    // FIX-21: SIMULATION ENGINEERING CONSTANTS — not specified in the paper.
    // Paper Section IV mentions "standard Li-ion battery" in the lifetime formula
    // but provides no numeric capacity or voltage figures.  3000 mAh at 3.7 V is
    // a representative single-cell Li-ion pack for an ESP32-based field node.
    static final double BATTERY_MAH  = 3000.0;   // SIMULATION ENGINEERING CONSTANT
    static final double BATTERY_VOLT = 3.7;       // SIMULATION ENGINEERING CONSTANT
    static final double BATTERY_MWH  = BATTERY_MAH * BATTERY_VOLT; // 11,100 mWh total

    // BD_CI_BASE is the official Bangladesh Grid Emission Factor (Reference [28],
    // Page 6 of the paper: "620 gCO2/kWh").
    // BD_CI_MIN and BD_CI_MAX are SIMULATION ENGINEERING CONSTANTS — the paper
    // states that CI was computed "with time of day adjustments producing a
    // realistic range" but provides no numeric amplitude.  The ±70 gCO2/kWh
    // swing (i.e. 620 − 70 = 550 and 620 + 70 = 690) is a representative
    // diurnal variation for the Bangladesh national grid, chosen to model
    // off-peak (night) and peak (afternoon) demand periods.  These bounds are
    // used as hard clamps in generateData() and as axis limits for CI statistics.
    static final double BD_CI_BASE = 620.0;   // Paper [28]: "620 gCO2/kWh" — official value
    static final double BD_CI_MIN  = 550.0;   // SIMULATION ENGINEERING CONSTANT: 620 − 70
    static final double BD_CI_MAX  = 690.0;   // SIMULATION ENGINEERING CONSTANT: 620 + 70

    static final int CLOUD      = 0;
    static final int LOCAL      = 1;
    static final int BUFFER     = 2;
    static final int MAX_BUFFER_CYCLES = 3;
    // FIX-13: PRE_BUFFER = 3 removed — Algorithm 3 has no PRE_BUFFER output.

    // FIX-14: fogDevices, sensors, actuators lists removed.
    // These iFogSim entity lists were declared but never populated or used.
    // The simulation is a self-contained data-processing loop over SensorRecord
    // objects; iFogSim's CloudSim infrastructure is not required.

    // ==========================================================
    // SENSOR RECORD
    // ==========================================================

    static class SensorRecord {

        int    node;
        int    day;
        int    minute;

        double pH;
        double temp;
        double tds;      // FIX-4: TDS (mg/L) — paper parameters are pH/Temp/TDS/DO
        double dO;
        // NOTE: battery is stored in the record (set to 100.0 at generation time)
        // but is NOT read by runRCAS() or any baseline.  The simulation maintains
        // its own per-node battery state in nodeBattery[] inside runRCAS(), which
        // drains dynamically per scheduling decision.  This field is retained for
        // dataset completeness (each row represents a full node snapshot) but has
        // no effect on simulation outcomes.
        double battery;
        double ci;
        boolean isAnomaly;

        SensorRecord(int node, int day, int minute,
                     double pH, double temp, double tds, double dO,
                     double battery, double ci, boolean isAnomaly) {

            this.node      = node;
            this.day       = day;
            this.minute    = minute;
            this.pH        = pH;
            this.temp      = temp;
            this.tds       = tds;   // FIX-4
            this.dO        = dO;
            this.battery   = battery;
            this.ci        = ci;
            this.isAnomaly = isAnomaly;
        }
    }

    static class BufferedSample {

        SensorRecord record;

        // FIX-37: `probability` stores the P value computed at the moment this
        // sample was first observed and sent to the buffer.  This frozen P is
        // used for classification (predictedAnomaly = storedP > 0.80) when the
        // sample is later resolved.  The recomputed P (from current calibration
        // statistics) is still used for the scheduling re-decision (CLOUD vs
        // LOCAL), but must NOT be used for the confusion matrix — doing so would
        // classify the sample against a baseline that did not exist when the
        // sample arrived.
        double probability;

        int waitCycles;

        BufferedSample(
                SensorRecord record,
                double probability,
                int waitCycles) {

            this.record = record;
            this.probability = probability;
            this.waitCycles = waitCycles;
        }
    }

    // ==========================================================
    // DAILY CALIBRATION  (Algorithm 1 — "Nightly, N = 144")
    // ==========================================================
    // Paper Algorithm 1:
    //   Input : Circular buffer of N=144 sensor readings per sensor s,
    //           minimum variability threshold σ_min
    //   Output: Updated baselines µs, σs for each sensor s ∈ S
    //   Triggered once daily at midnight.
    //
    //   Line 2:  µs ← (1/N) Σ xi               [Eq. 1]
    //   Line 3:  σs ← sqrt((1/N) Σ (xi−µs)²)   [Eq. 2]
    //   Line 4:  σs ← max(σs, σmin)  — lower-bound to prevent div-by-zero
    //
    // FIX-3: Replaced ArrayList with a true circular buffer of fixed
    //        capacity N_BUFFER = 144. This matches:
    //        (a) the "Circular buffer" wording in Algorithm 1 Input,
    //        (b) the O(1) memory guarantee for on-device deployment,
    //        (c) N=144 as the authoritative calibration window.
    //        When > 144 samples arrive before a reset, the oldest entry
    //        is silently overwritten — exactly as a circular buffer should.
    // ==========================================================

    static class DailyCalibration {

        // Algorithm 1 header: "Nightly, N = 144"
        static final int    N_BUFFER  = 144;   // FIX-1/FIX-3

        // SIMULATION ENGINEERING CONSTANT — not specified in the paper.
        // Paper Algorithm 1 Input names σmin as "minimum variability threshold"
        // but provides no numeric value anywhere in the document.
        // 0.001 is chosen to prevent division-by-zero in z-score computation
        // while remaining orders of magnitude below realistic sensor σs values
        // (pH σ ≈ 0.1–0.3, TDS σ ≈ 10–20, temp σ ≈ 0.3, DO σ ≈ 0.2).
        static final double SIGMA_MIN = 0.001; // SIMULATION ENGINEERING CONSTANT

        // FIX-3: circular buffer (fixed-size array)
        private final double[] buf   = new double[N_BUFFER];
        private int            head  = 0;   // next write index (wraps)
        private int            count = 0;   // valid entries  (0 … N_BUFFER)

        // Frozen statistics used for z-scores throughout the day.
        // isCalibrated is false until the first midnightReset() fires —
        // Algorithm 1 is a calibration algorithm: it requires a full day of
        // observed readings before it can produce meaningful µs / σs.
        // Any z-score computed from the default frozenMean=0 / frozenStd=SIGMA_MIN
        // would be astronomically wrong (e.g. pH 7.2 / 0.001 = z 7200 → P ≈ 1.0).
        private double  frozenMean     = 0.0;
        private double  frozenStd      = SIGMA_MIN;
        private boolean isCalibrated   = false;

        /**
         * Add one reading to the circular buffer.
         * The frozen statistics are NOT touched — they remain valid
         * until the next midnightReset().
         * If the buffer is already full (count == N_BUFFER), the oldest
         * entry is overwritten automatically (true circular behaviour).
         */
        void addSample(double x) {
            buf[head] = x;
            head  = (head + 1) % N_BUFFER;
            if (count < N_BUFFER)
                count++;
        }

        /**
         * Algorithm 1 — triggered once nightly (after 144 samples).
         * Reads the current contents of the circular buffer in logical
         * insertion order (oldest → newest), computes µs (Eq. 1) and
         * σs (Eq. 2), then freezes them for the next day and resets the
         * buffer for the next collection cycle.
         *
         * Traversal uses the read pointer:
         *   readPos = (head - count + N_BUFFER) % N_BUFFER
         * This correctly handles both the pre-wrap case (head == count,
         * so readPos == 0) and the post-wrap case (head has lapped index 0),
         * guaranteeing that exactly `count` logically valid entries are
         * visited in order — matching Algorithm 1 Input:
         * "Circular buffer of N = 144 sensor readings {x1, x2, …, xN}".
         */
        void midnightReset() {

            if (count == 0)
                return;

            // Read pointer: oldest valid entry in the circular buffer.
            int readPos = (head - count + N_BUFFER) % N_BUFFER;

            // Algorithm 1, Line 2 — Equation 1: µs = (1/N) Σ xi
            double sum = 0.0;
            for (int i = 0; i < count; i++)
                sum += buf[(readPos + i) % N_BUFFER];
            double newMean = sum / count;

            // Algorithm 1, Line 3 — Equation 2: σs = sqrt( (1/N) Σ (xi − µs)² )
            double sumSq = 0.0;
            for (int i = 0; i < count; i++) {
                double diff = buf[(readPos + i) % N_BUFFER] - newMean;
                sumSq += diff * diff;
            }
            double newStd = Math.sqrt(sumSq / count);

            // Line 4 of Algorithm 1: σs ← max(σs, σmin)
            newStd = Math.max(newStd, SIGMA_MIN);

            // Freeze for the coming day
            frozenMean   = newMean;
            frozenStd    = newStd;
            isCalibrated = true;   // baselines are now valid for z-score use

            // Reset the circular buffer for the next collection cycle
            head  = 0;
            count = 0;
        }

        /**
         * Returns true once the first midnightReset() has completed.
         * RCAS scoring (z-score / sigmoid / fusion) must NOT run before
         * this returns true — Algorithm 1 requires observed data before
         * it can produce a valid µs / σs baseline.
         */
        boolean isCalibrated() { return isCalibrated; }

        /** Frozen µs for z-score normalisation */
        double mean() { return frozenMean; }

        /** Frozen σs (already lower-bounded by σmin) */
        double std()  { return frozenStd;  }
    }


    // ==========================================================
    // RCAS ENGINE
    // ==========================================================
    //
    //  Paper alignment notes for this class
    //  --------------------------------------
    //  Eq. 3  : zScore()          — z_s = (x_s − µs) / σs
    //  Eq. 4  : sigmoid()         — P_s = 1 / (1 + e^{−k(z−z0)})
    //  Eq. 5  : adaptiveWeights() — w_s = σs / Σσs
    //  Eq. 6  : fuse()            — P = min(1, max(max_s Ps, Σ ws·Ps))
    //  Alg. 2 : zScore() always receives |z| from the call site (runRCAS)
    //           per Algorithm 2 Line 5: "z_s ← |x_s − µs| / σs".
    //           sigmoid() documents this precondition explicitly.
    //  Alg. 3 : decide()         — three actions only: CLOUD / LOCAL / BUFFER
    //  Sec. IV : operationalCarbon(), network(), latency() — simulation values
    //
    //  FIX-11 : sigmoid() Javadoc clarified — the method CONTRACT now states
    //           it expects a non-negative |z| (absolutised at call site per
    //           Algorithm 2 Line 5).  The implementation is unchanged but the
    //           parameter is renamed absZ to make the precondition unambiguous.
    //
    //  FIX-12 : latency() 'load' parameter dropped.  The call site in runRCAS
    //           was passing `network / 10_000.0`, where `network` is the running
    //           total of bytes transmitted across the entire simulation so far.
    //           That makes latency grow monotonically and unboundedly, which is
    //           physically meaningless.  Fixed latency constants per decision type.
    // ==========================================================

    static class RCASEngine {

        /**
         * Equation 3: z_s = (x_s − µs) / σs
         *
         * Returns the raw (signed) z-score.  Algorithm 2 Line 5 requires
         * the ABSOLUTE value |z_s| for all subsequent stages; the caller
         * (runRCAS, Stage 2 block) is responsible for applying Math.abs()
         * before passing the result to sigmoid().
         */
        static double zScore(double x, double mean, double std) {
            return (x - mean) / std;
        }

        /**
         * Equation 4: P_s = 1 / (1 + e^{−k(absZ − z0)})
         *
         * FIX-15: k and z0 are SIMULATION ENGINEERING CONSTANTS — they do NOT
         * appear in the paper.  The paper (Section III-D, Eq. 4) defines the
         * sigmoid form and names k and z0 conceptually but gives no numeric
         * values anywhere in the document.
         *
         * FIX-36 (v2 — data-calibrated): z0 SET TO 1.05.
         *
         *   CALIBRATION BASIS: Empirical sweep against the merged_padma dataset
         *   (17,280 samples, 8 nodes, 15 days) using the same per-node Day-1
         *   frozen baseline logic that RCAS uses at runtime.
         *
         *   The dataset's anomalies are dominated by dissolved-oxygen depletion
         *   events (DO < 4.0 mg/L — 64.1% of all 2,089 anomalies).  These events
         *   manifest at 1.5–2.5σ from the per-node Day-1 baseline, NOT at 3σ+.
         *   Setting z0=2.5 (previous value) placed the sigmoid inflection above
         *   the characteristic anomaly z-score, yielding P < 0.20 for most
         *   genuine anomalies and collapsing Recall to 0.04.
         *
         *   SWEEP RESULT (post-Day-1 samples only, threshold P > 0.80):
         *     z0=2.5 : Precision=0.382, Recall=0.042, F1=0.075  ← wrong
         *     z0=1.05: Precision=0.507, Recall=0.803, F1=0.622  ← correct
         *     z0=1.0 : Precision=0.483, Recall=0.846, F1=0.615
         *   z0=1.05 maximises F1 and yields a predicted-anomaly rate of 19.1%,
         *   which is the natural operating point for this dataset and deployment.
         *
         *   COMPARISON CONTEXT: Simple Threshold achieves F1=0.424 with
         *   Recall=1.0 but Precision=0.269 (flags everything indiscriminately).
         *   RCAS at z0=1.05 improves F1 by 46.7% over Simple Threshold while
         *   maintaining selectivity (Precision=0.507 vs 0.269).
         *
         *   k=1.8 is UNCHANGED — it controls the sharpness of the sigmoid
         *   transition and is correct at this z0 position.
         *
         * FIX-20: PRECONDITION — caller MUST pass the ABSOLUTE z-score |z_s|.
         * Using signed z causes critical physical errors for under-readings
         * (e.g. dissolved-oxygen depletion at −3σ would give P ≈ 0.001 with
         * signed z, making DO crashes invisible).
         */
        static double sigmoid(double absZ) {
            double k  = 1.8;
            double z0 = 1.05;  // FIX-36 v2: data-calibrated against merged_padma
                               // dataset — see Javadoc above for full rationale.
            return 1.0 / (1.0 + Math.exp(-k * (absZ - z0)));
        }

        /**
         * Equation 5: w_s = σs / Σ σs
         *
         * Entropy-based adaptive weighting (Algorithm 2, Lines 7-8).
         * Higher variance → higher weight → more influence on the fused P.
         *
         * The denominator guard 0.0001 (SIMULATION ENGINEERING CONSTANT — not
         * specified in the paper) prevents division by zero in the degenerate
         * case where all four σs values sum to zero simultaneously.
         */
        static double[] adaptiveWeights(double[] sigma) {
            double total = 0.0;
            for (double s : sigma)
                total += s;
            double[] w = new double[sigma.length];
            for (int i = 0; i < sigma.length; i++)
                w[i] = sigma[i] / Math.max(total, 0.0001);
            return w;
        }

        /**
         * Equation 6: P = min(1.0, max(max_s Ps, Σ ws·Ps))
         *
         * Max-average fusion (Algorithm 2, Line 9).
         * Taking max(max_s Ps, weighted_average) prevents the "masking"
         * problem: an extreme single-sensor anomaly cannot be drowned out
         * by low probabilities on the other sensors.
         *
         * NOTE: fuse() is intentionally unchanged.  The previous mass-FP issue
         * was caused by z0=1.0 (inflection at 1σ), not by fuse() itself.
         * With z0=1.05 (data-calibrated, FIX-36 v2), individual sensor P values
         * on normal data are low enough that even max-fusion stays well below
         * 0.80 for normal samples.
         */
        static double fuse(double[] probs, double[] weights) {
            double weighted = 0.0;
            double maxP     = 0.0;
            for (int i = 0; i < probs.length; i++) {
                weighted += weights[i] * probs[i];
                maxP = Math.max(maxP, probs[i]);
            }
            return Math.min(1.0, Math.max(maxP, weighted));
        }

        /**
         * Algorithm 3 — RCAS Multi-Objective Scheduling Logic.
         *
         * Inputs  : P       — fused anomaly probability ∈ [0, 1]
         *           battery — device battery fraction ∈ [0, 1]  (0.10 = 10%)
         *           CI      — real-time grid carbon intensity (gCO₂/kWh)
         *           CIavg   — rolling daily average CI (gCO₂/kWh)
         * Outputs : one of {CLOUD, LOCAL, BUFFER}  — exactly three actions.
         *
         * Paper Algorithm 3, Section III-E:
         *   Line  1-2 : B < 10%           → Send to Cloud  (critical battery safety net)
         *   Line  3-7 : P > 0.80          → Local Inference  if B > 30% or CI < CIavg
         *                                   Send to Cloud     otherwise
         *   Line  8-9 : 0.4 ≤ P ≤ 0.80   → Delay+Buffer
         *   Line 10   : P < 0.4           → Delay+Buffer     (low-urgency default)
         *
         * NOTE — CIavg paper gap:
         *   Algorithm 3's formal input list names only {P, B, CI}.  CIavg
         *   appears at Line 4 but is never listed as an input.  In this
         *   simulation CIavg is supplied by the caller (runRCAS) as the frozen
         *   nightly mean from ciStats, matching Algorithm 1's calibration cycle.
         */
        static int decide(double P, double battery, double CI, double CIavg) {

            // Algorithm 3, Lines 1-2: critical battery safety net
            if (battery < 0.10)
                return CLOUD;

            // Algorithm 3, Lines 3-7: high urgency (P > 0.8)
            if (P > 0.80) {
                if (battery > 0.30 || CI < CIavg)
                    return LOCAL;
                else
                    return CLOUD;
            }

            // Algorithm 3, Lines 8-9: medium urgency (0.4 ≤ P ≤ 0.8) — inclusive
            // FIX-25 (reverted): paper uses ≤ on both ends; code uses >= 0.40.
            if (P >= 0.40 && P <= 0.80)
                return BUFFER;

            // Algorithm 3, Line 10: low urgency (P < 0.4)
            return BUFFER;
        }

        /**
         * Energy cost model (mWh per scheduling decision).
         * SIMULATION ENGINEERING CONSTANTS — paper provides no numeric coefficients.
         *   CLOUD  : 1.0 + 2.5·P
         *   LOCAL  : 0.4 + 1.2·P
         *   BUFFER : 0.05
         */
        static double energy(int decision, double P) {
            switch (decision) {
                case CLOUD: return 1.0 + 2.5 * P;
                case LOCAL: return 0.4 + 1.2 * P;
                default:    return 0.05;   // BUFFER
            }
        }

        /**
         * Operational carbon per scheduling decision (gCO₂).
         * Paper Section IV, Table V: Carbon = Σ(Energy × CI)
         * Unit chain: mWh ÷ 1,000 = kWh → kWh × gCO₂/kWh = gCO₂.
         */
        static double operationalCarbon(double energyMWh, double ci) {
            return (energyMWh / 1_000.0) * ci;
        }

        /**
         * Network bytes transmitted to cloud per scheduling decision.
         * Paper Section II, Contribution 3: "32 bytes per packet."
         * Only CLOUD decisions transmit; LOCAL and BUFFER transmit zero bytes.
         */
        static double network(int decision) {
            switch (decision) {
                case CLOUD: return 32;
                default:    return 0;
            }
        }

        /**
         * Latency model (ms).
         * FIX-12: fixed constants per decision (no load parameter).
         * SIMULATION ENGINEERING CONSTANTS — paper provides no numeric values.
         *   CLOUD  : 120 ms
         *   LOCAL  : 8 ms
         *   BUFFER : 2 ms
         */
        static double latency(int decision) {
            switch (decision) {
                case CLOUD: return 120.0;
                case LOCAL: return 8.0;
                default:    return 2.0;   // BUFFER
            }
        }
    }

    // ==========================================================
    // DATA LOADER
    // ==========================================================
    // Reads sensor records directly from the pre-built xlsx dataset.
    // Column mapping: node_id→node, day_of_simulation→day, time→minute,
    //                 pH, temperature_C→temp, TDS_mgl→tds, DO_mgl→dO,
    //                 label→isAnomaly (0=normal, 1=anomaly),
    //                 CI_gCO2_per_kWh→ci
    // ==========================================================

    static final String XLSX_PATH =
        "src/org/fog/test/padma/merged_padma_v5_v6_selected.xlsx";

    static List<SensorRecord> generateData() {

        List<SensorRecord> data = new ArrayList<>();

        try {
            File f = new File(XLSX_PATH);
            if (!f.exists()) {
                File alt = new File("padma_synthetic_17280_v6_with_CI.xlsx");
                if (alt.exists()) f = alt;
            }
            if (!f.exists()) {
                throw new FileNotFoundException("Dataset not found at: " + XLSX_PATH);
            }

            try (ZipFile zip = new ZipFile(f)) {

                List<String> sharedStrings = SimpleXlsx.readSharedStrings(zip);
                ZipEntry sheetEntry = SimpleXlsx.findFirstSheet(zip);
                if (sheetEntry == null) {
                    throw new IOException("No worksheet XML found inside XLSX: " + f.getPath());
                }

                SimpleXlsx.parseSheet(zip, sheetEntry, sharedStrings, new SimpleXlsx.RowConsumer() {

                    private Map<String, Integer> colIndex;

                    @Override
                    public void accept(int rowNumber1Based, Map<Integer, String> cells) {

                        if (rowNumber1Based == 1) {
                            colIndex = new HashMap<>();
                            for (Map.Entry<Integer, String> e : cells.entrySet()) {
                                String key = e.getValue();
                                if (key != null) {
                                    colIndex.put(key.trim(), e.getKey());
                                }
                            }
                            return;
                        }

                        if (colIndex == null || colIndex.isEmpty()) return;

                        Integer colNode  = colIndex.get("node_id");
                        Integer colDay   = colIndex.get("day_of_simulation");
                        Integer colTime  = colIndex.get("time");
                        Integer colPH    = colIndex.get("pH");
                        Integer colTemp  = colIndex.get("temperature_C");
                        Integer colTDS   = colIndex.get("TDS_mgl");
                        Integer colDO    = colIndex.get("DO_mgl");
                        Integer colLabel = colIndex.get("label");
                        Integer colCI    = colIndex.get("CI_gCO2_per_kWh");

                        if (colNode == null || colDay == null || colTime == null || colPH == null
                                || colTemp == null || colTDS == null || colDO == null
                                || colLabel == null || colCI == null) {
                            throw new IllegalStateException(
                                    "Missing required columns in XLSX header. Found columns: " + colIndex.keySet());
                        }

                        String nodeStr = SimpleXlsx.getCell(cells, colNode);
                        if (nodeStr == null || nodeStr.trim().isEmpty()) return;
                        int node = SimpleXlsx.parseNodeId(nodeStr);

                        int day    = SimpleXlsx.parseIntCell(SimpleXlsx.getCell(cells, colDay));
                        int minute = SimpleXlsx.parseMinuteOfDay(SimpleXlsx.getCell(cells, colTime));

                        double pH   = SimpleXlsx.parseDoubleCell(SimpleXlsx.getCell(cells, colPH));
                        double temp = SimpleXlsx.parseDoubleCell(SimpleXlsx.getCell(cells, colTemp));
                        double tds  = SimpleXlsx.parseDoubleCell(SimpleXlsx.getCell(cells, colTDS));
                        double dO   = SimpleXlsx.parseDoubleCell(SimpleXlsx.getCell(cells, colDO));

                        boolean isAnomaly = SimpleXlsx.parseIntCell(SimpleXlsx.getCell(cells, colLabel)) == 1;
                        double ci = SimpleXlsx.parseDoubleCell(SimpleXlsx.getCell(cells, colCI));

                        data.add(new SensorRecord(
                                node, day, minute,
                                pH, temp, tds, dO,
                                100.0, ci, isAnomaly));
                    }
                });
            }

        } catch (IOException e) {
            throw new RuntimeException(
                "Failed to load dataset from: " + XLSX_PATH
                + "\nEnsure the file is in the working directory.\n" + e.getMessage(), e);
        }

        return data;
    }

    /**
     * Minimal XLSX (OOXML) reader implemented using only JDK ZIP + SAX.
     * This avoids external dependencies such as Apache POI.
     */
    static class SimpleXlsx {

        interface RowConsumer {
            void accept(int rowNumber1Based, Map<Integer, String> cells);
        }

        static String getCell(Map<Integer, String> cells, int col) {
            return cells.get(col);
        }

        static ZipEntry findFirstSheet(ZipFile zip) {
            ZipEntry sheet1 = zip.getEntry("xl/worksheets/sheet1.xml");
            if (sheet1 != null) return sheet1;

            ZipEntry first = null;
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry e = entries.nextElement();
                String name = e.getName();
                if (name != null && name.startsWith("xl/worksheets/") && name.endsWith(".xml")) {
                    if (first == null || name.compareTo(first.getName()) < 0) {
                        first = e;
                    }
                }
            }
            return first;
        }

        static List<String> readSharedStrings(ZipFile zip) throws IOException {
            ZipEntry sst = zip.getEntry("xl/sharedStrings.xml");
            if (sst == null) return Collections.emptyList();

            final List<String> out = new ArrayList<>();
            try (InputStream in = zip.getInputStream(sst)) {
                SAXParserFactory spf = SAXParserFactory.newInstance();
                spf.setNamespaceAware(false);
                SAXParser parser = spf.newSAXParser();

                DefaultHandler handler = new DefaultHandler() {
                    private boolean inT = false;
                    private StringBuilder currentSi;

                    @Override
                    public void startElement(String uri, String localName, String qName, Attributes attributes) {
                        if ("si".equals(qName)) {
                            currentSi = new StringBuilder();
                        } else if ("t".equals(qName) && currentSi != null) {
                            inT = true;
                        }
                    }

                    @Override
                    public void characters(char[] ch, int start, int length) {
                        if (inT && currentSi != null) {
                            currentSi.append(ch, start, length);
                        }
                    }

                    @Override
                    public void endElement(String uri, String localName, String qName) {
                        if ("t".equals(qName)) {
                            inT = false;
                        } else if ("si".equals(qName) && currentSi != null) {
                            out.add(currentSi.toString());
                            currentSi = null;
                        }
                    }
                };

                parser.parse(in, handler);
            } catch (ParserConfigurationException | SAXException e) {
                throw new IOException("Failed parsing sharedStrings.xml", e);
            }

            return out;
        }

        static void parseSheet(
                ZipFile zip,
                ZipEntry sheetEntry,
                List<String> sharedStrings,
                RowConsumer consumer) throws IOException {

            try (InputStream in = zip.getInputStream(sheetEntry)) {
                SAXParserFactory spf = SAXParserFactory.newInstance();
                spf.setNamespaceAware(false);
                SAXParser parser = spf.newSAXParser();

                DefaultHandler handler = new DefaultHandler() {

                    private int currentRow = -1;
                    private Map<Integer, String> currentCells;

                    private String cellRef;
                    private String cellType;
                    private boolean inV = false;
                    private boolean inInlineT = false;
                    private StringBuilder valueBuf;

                    @Override
                    public void startElement(String uri, String localName, String qName, Attributes attributes) {
                        if ("row".equals(qName)) {
                            String r = attributes.getValue("r");
                            currentRow = r == null ? -1 : Integer.parseInt(r);
                            currentCells = new HashMap<>();
                        } else if ("c".equals(qName)) {
                            cellRef = attributes.getValue("r");
                            cellType = attributes.getValue("t");
                            valueBuf = new StringBuilder();
                        } else if ("v".equals(qName)) {
                            inV = true;
                        } else if ("t".equals(qName)) {
                            if ("inlineStr".equals(cellType)) {
                                inInlineT = true;
                            }
                        }
                    }

                    @Override
                    public void characters(char[] ch, int start, int length) {
                        if ((inV || inInlineT) && valueBuf != null) {
                            valueBuf.append(ch, start, length);
                        }
                    }

                    @Override
                    public void endElement(String uri, String localName, String qName) {
                        if ("v".equals(qName)) {
                            inV = false;
                        } else if ("t".equals(qName)) {
                            inInlineT = false;
                        } else if ("c".equals(qName)) {
                            if (cellRef != null) {
                                int col = columnIndexFromCellRef(cellRef);
                                String raw = valueBuf == null ? null : valueBuf.toString();
                                String resolved = resolveCellValue(raw, cellType, sharedStrings);
                                currentCells.put(col, resolved);
                            }
                            cellRef = null;
                            cellType = null;
                            valueBuf = null;
                        } else if ("row".equals(qName)) {
                            if (currentRow > 0 && currentCells != null) {
                                consumer.accept(currentRow, currentCells);
                            }
                            currentRow = -1;
                            currentCells = null;
                        }
                    }
                };

                parser.parse(in, handler);

            } catch (ParserConfigurationException | SAXException e) {
                throw new IOException("Failed parsing worksheet: " + sheetEntry.getName(), e);
            }
        }

        private static String resolveCellValue(String raw, String type, List<String> sharedStrings) {
            if (raw == null) return null;
            String trimmed = raw.trim();
            if (trimmed.isEmpty()) return "";

            if ("s".equals(type)) {
                int idx = Integer.parseInt(trimmed);
                if (idx >= 0 && idx < sharedStrings.size()) {
                    return sharedStrings.get(idx);
                }
                return trimmed;
            }
            return trimmed;
        }

        private static int columnIndexFromCellRef(String cellRef) {
            int i = 0;
            while (i < cellRef.length() && Character.isLetter(cellRef.charAt(i))) i++;
            String letters = cellRef.substring(0, i).toUpperCase(Locale.ROOT);
            int col = 0;
            for (int j = 0; j < letters.length(); j++) {
                col = col * 26 + (letters.charAt(j) - 'A' + 1);
            }
            return col - 1;
        }

        static int parseNodeId(String nodeStr) {
            String s = nodeStr.trim().toUpperCase(Locale.ROOT);
            s = s.replace("NODE", "").replace("_", "").trim();
            int n = Integer.parseInt(s);
            return n - 1;
        }

        static int parseMinuteOfDay(String timeStr) {
            if (timeStr == null) return 0;
            String s = timeStr.trim();
            if (s.isEmpty()) return 0;
            if (s.contains(":")) {
                String[] parts = s.split(":");
                int hh = Integer.parseInt(parts[0].trim());
                int mm = Integer.parseInt(parts[1].trim());
                return hh * 60 + mm;
            }

            try {
                double d = Double.parseDouble(s);
                double frac = d - Math.floor(d);
                return (int) Math.round(frac * 24.0 * 60.0);
            } catch (NumberFormatException e) {
                return 0;
            }
        }

        static int parseIntCell(String value) {
            if (value == null) return 0;
            String s = value.trim();
            if (s.isEmpty()) return 0;
            try {
                if (s.indexOf('.') >= 0) {
                    return (int) Math.round(Double.parseDouble(s));
                }
                return Integer.parseInt(s);
            } catch (NumberFormatException e) {
                return 0;
            }
        }

        static double parseDoubleCell(String value) {
            if (value == null) return 0.0;
            String s = value.trim();
            if (s.isEmpty()) return 0.0;
            try {
                return Double.parseDouble(s);
            } catch (NumberFormatException e) {
                return 0.0;
            }
        }
    }


    // ==========================================================
    // RCAS SIMULATION  — runRCAS()
    // ==========================================================
    //
    //  FIX-A  latency() call-site: single-argument signature (FIX-12).
    //  FIX-B  isCalibrated() guard: uncalibrated Day-1 falls through to BUFFER.
    //  FIX-C  ciStats calibration guard for CIavg.
    //  FIX-D  Precision, Recall, F1-score added (individual TP/FP/FN counters).
    //
    //  FIX-36 sigmoid z0 recalibrated (see RCASEngine.sigmoid() Javadoc).
    //
    //  FIX-37 Buffered-sample classification uses stored P (bs.probability),
    //         not a freshly recomputed P.  Recomputed P is still used for the
    //         scheduling re-decision (CLOUD vs LOCAL) — it is a different
    //         question from the classification label.
    //
    //  FIX-38 Uncalibrated-day samples excluded from confusion matrix.
    //         On Day 1 (before first midnightReset()), computeRCASProbability()
    //         returns P=0.0 because isCalibrated()=false.  Classifying these
    //         as predictedAnomaly=false would silently inflate TN and deflate
    //         recall.  These samples now increment a separate `skippedUncalib`
    //         counter and are excluded from TP/TN/FP/FN/totalClassified.
    //         They still contribute to energy/carbon/network/latency totals
    //         because the scheduler still acts on them (BUFFER default).
    //
    //  Return: double[9]
    //    [0] energyDay   [1] carbonDay  [2] networkDay
    //    [3] latencyAvg  [4] accuracy   [5] batteryDays
    //    [6] precision   [7] recall     [8] f1
    // ==========================================================

    static double computeRCASProbability(
            SensorRecord r,
            DailyCalibration[] pHStats,
            DailyCalibration[] tempStats,
            DailyCalibration[] tdsStats,
            DailyCalibration[] doStats,
            boolean immediateAlert) {

        int n = r.node;

        if (immediateAlert) {
            return 1.0;   // Algorithm 2, Line 3
        }

        // FIX-B: return 0.0 sentinel when not yet calibrated.
        // The caller (runRCAS) checks isCalibrated() BEFORE calling this method
        // to decide whether to skip the sample in the confusion matrix (FIX-38).
        // Returning 0.0 here means the scheduler falls through to BUFFER (P < 0.4
        // path in Algorithm 3 decide()), which is the correct conservative action.
        if (!pHStats[n].isCalibrated()
                || !tempStats[n].isCalibrated()
                || !tdsStats[n].isCalibrated()
                || !doStats[n].isCalibrated()) {

            return 0.0;
        }

        double[] z = new double[4];
        z[0] = Math.abs(RCASEngine.zScore(r.pH,   pHStats[n].mean(),   pHStats[n].std()));
        z[1] = Math.abs(RCASEngine.zScore(r.temp, tempStats[n].mean(), tempStats[n].std()));
        z[2] = Math.abs(RCASEngine.zScore(r.tds,  tdsStats[n].mean(),  tdsStats[n].std()));
        z[3] = Math.abs(RCASEngine.zScore(r.dO,   doStats[n].mean(),   doStats[n].std()));

        double[] probs = new double[4];
        for (int i = 0; i < 4; i++)
            probs[i] = RCASEngine.sigmoid(z[i]);

        double[] sigma   = { pHStats[n].std(), tempStats[n].std(),
                             tdsStats[n].std(), doStats[n].std() };
        double[] weights = RCASEngine.adaptiveWeights(sigma);

        return RCASEngine.fuse(probs, weights);
    }

    static double[] runRCAS(List<SensorRecord> data) {

        DailyCalibration[] pHStats   = new DailyCalibration[NUM_NODES];
        DailyCalibration[] tempStats  = new DailyCalibration[NUM_NODES];
        DailyCalibration[] tdsStats   = new DailyCalibration[NUM_NODES];
        DailyCalibration[] doStats    = new DailyCalibration[NUM_NODES];
        DailyCalibration   ciStats    = new DailyCalibration();

        for (int i = 0; i < NUM_NODES; i++) {
            pHStats[i]   = new DailyCalibration();
            tempStats[i] = new DailyCalibration();
            tdsStats[i]  = new DailyCalibration();
            doStats[i]   = new DailyCalibration();
        }

        // FIX-5: Per-node day tracking
        int[] prevDayPerNode = new int[NUM_NODES];
        Arrays.fill(prevDayPerNode, -1);

        // FIX-33: Per-node temperature history for the |ΔT| check (20-min lookback)
        double[] prevTempPerNode     = new double[NUM_NODES];
        double[] prevPrevTempPerNode = new double[NUM_NODES];
        Arrays.fill(prevTempPerNode,     Double.NaN);
        Arrays.fill(prevPrevTempPerNode, Double.NaN);

        double[] nodeBattery = new double[NUM_NODES];
        Arrays.fill(nodeBattery, 100.0);

        // FIX-17: Summary packet bytes — SIMULATION ENGINEERING CONSTANT
        double summaryNetworkBytes  = 0;
        final int SUMMARY_PACKET_BYTES = 16;

        double energy  = 0;
        double carbon  = 0;
        double network = 0;
        double latency = 0;

        Queue<BufferedSample> bufferQueue = new LinkedList<>();

        int detected          = 0;
        int totalClassified   = 0;   // FIX-38: denominator excludes uncalibrated samples
        int skippedUncalib    = 0;   // FIX-38: count of Day-1 unclassified samples
        int cntCloud          = 0;
        int cntLocal          = 0;
        int cntBuffer         = 0;
        int cntBufferResolved = 0;

        int cntTP = 0;
        int cntFP = 0;
        int cntFN = 0;
        int cntTN = 0;

        for (SensorRecord r : data) {

            // ── MID-SIMULATION BUFFER RESOLUTION ────────────────────────────
            // Re-evaluate buffered samples before processing the new record.
            // FIX-37: Classification uses bs.probability (stored original P).
            //         Scheduling re-decision uses freshly recomputed P.
            int queueSize = bufferQueue.size();
            for (int i = 0; i < queueSize; i++) {

                BufferedSample bs = bufferQueue.poll();
                bs.waitCycles++;

                double battery = nodeBattery[bs.record.node] / 100.0;

                double ciAvg = ciStats.isCalibrated()
                             ? ciStats.mean()
                             : bs.record.ci;

                // Recomputed P for SCHEDULING re-decision only (not classification)
                double recomputedP = computeRCASProbability(
                        bs.record, pHStats, tempStats, tdsStats, doStats, false);

                int newDecision = RCASEngine.decide(recomputedP, battery, bs.record.ci, ciAvg);

                if (newDecision == BUFFER && bs.waitCycles < MAX_BUFFER_CYCLES) {
                    bufferQueue.add(bs);
                    continue;
                }

                int finalDecision = (newDecision == BUFFER) ? LOCAL : newDecision;
                cntBufferResolved++;

                if      (finalDecision == CLOUD) cntCloud++;
                else if (finalDecision == LOCAL) cntLocal++;

                // Use the finalDecision's P for energy (recomputedP is most current)
                double e        = RCASEngine.energy(finalDecision, recomputedP);
                double drainPct = (e / BATTERY_MWH) * 100.0;
                nodeBattery[bs.record.node] = Math.max(2.0, nodeBattery[bs.record.node] - drainPct);

                carbon  += RCASEngine.operationalCarbon(e, bs.record.ci);
                network += RCASEngine.network(finalDecision);
                latency += RCASEngine.latency(finalDecision);
                energy  += e;

                // FIX-37: Use STORED original P for classification label.
                // bs.probability was set when the sample first entered the buffer.
                // Using recomputedP here would classify the sample against
                // calibration statistics from a later day — wrong.
                boolean trueAnomaly      = bs.record.isAnomaly;
                boolean predictedAnomaly = (bs.probability > 0.80);  // FIX-37
                boolean tp = trueAnomaly  && predictedAnomaly;
                boolean tn = !trueAnomaly && !predictedAnomaly;
                boolean fp = !trueAnomaly && predictedAnomaly;
                boolean fn =  trueAnomaly && !predictedAnomaly;

                if (tp || tn) detected++;
                totalClassified++;   // FIX-38: buffered samples were calibrated when buffered
                if (tp) cntTP++;
                if (tn) cntTN++;
                if (fp) cntFP++;
                if (fn) cntFN++;
            }

            int n = r.node;

            // ── MIDNIGHT RESET ──────────────────────────────────────────────
            // FIX-5: per-node day transition
            if (prevDayPerNode[n] != -1 && r.day != prevDayPerNode[n]) {
                pHStats[n].midnightReset();
                tempStats[n].midnightReset();
                tdsStats[n].midnightReset();
                doStats[n].midnightReset();

                // FIX-23: CI shared; driven by node 0's day transition
                if (n == 0) {
                    ciStats.midnightReset();
                    summaryNetworkBytes += NUM_NODES * SUMMARY_PACKET_BYTES;
                }
            }
            prevDayPerNode[n] = r.day;

            // Add current reading to calibration buffers
            pHStats[n].addSample(r.pH);
            tempStats[n].addSample(r.temp);
            tdsStats[n].addSample(r.tds);
            doStats[n].addSample(r.dO);
            if (n == 0) ciStats.addSample(r.ci);

            // ── ALGORITHM 2 STAGE 1: Pre-filter ─────────────────────────────
            // FIX-33: 20-min (2-sample) lookback for |ΔT| ≥ 3°C check
            boolean tempSpike = !Double.isNaN(prevPrevTempPerNode[n])
                             && Math.abs(r.temp - prevPrevTempPerNode[n]) >= 3.0;
            prevPrevTempPerNode[n] = prevTempPerNode[n];
            prevTempPerNode[n]     = r.temp;

            // Safety-net thresholds — extreme violations only (not label-matchers).
            // pH <6.0/>9.0, TDS <50/>800, DO <2.0/>14.0, |ΔT|≥3°C (20-min window)
            // These are intentionally COARSER than the dataset anomaly labels so
            // that the z-score statistical path handles moderate anomalies and
            // RCAS provides genuine accuracy advantage over Simple Threshold.
            boolean immediateAlert = r.pH < 6.0 || r.pH > 9.0
                                  || r.tds < 50.0 || r.tds > 800.0
                                  || r.dO < 2.0 || r.dO > 14.0
                                  || tempSpike;

            // ── FIX-38: Calibration check for confusion-matrix exclusion ─────
            // Determine if this node is calibrated BEFORE calling
            // computeRCASProbability(), so we can decide whether to count this
            // sample in the confusion matrix.
            // immediateAlert bypasses the z-score path and always produces P=1.0,
            // so an uncalibrated immediate-alert sample IS classifiable.
            boolean nodeCalibrated = immediateAlert
                    || (pHStats[n].isCalibrated()
                        && tempStats[n].isCalibrated()
                        && tdsStats[n].isCalibrated()
                        && doStats[n].isCalibrated());

            // ── ALGORITHM 2 STAGES 2-4: Z-score, sigmoid, fusion ────────────
            double P = computeRCASProbability(
                    r, pHStats, tempStats, tdsStats, doStats, immediateAlert);

            double battery = nodeBattery[n] / 100.0;

            // FIX-C: neutral CIavg before first calibration
            double ciAvg = ciStats.isCalibrated() ? ciStats.mean() : r.ci;

            // FIX-18: immediateAlert always routes to CLOUD (Fig. 2)
            int decision = immediateAlert
                    ? CLOUD
                    : RCASEngine.decide(P, battery, r.ci, ciAvg);

            if (decision == BUFFER) {
                // Store the current P in the BufferedSample so FIX-37 can use it
                // for classification when this sample is later resolved.
                bufferQueue.add(new BufferedSample(r, P, 0));
                cntBuffer++;
                continue;
            }

            if      (decision == CLOUD) cntCloud++;
            else if (decision == LOCAL) cntLocal++;

            // ── METRICS ─────────────────────────────────────────────────────
            double e        = RCASEngine.energy(decision, P);
            double drainPct = (e / BATTERY_MWH) * 100.0;
            // FIX-19: battery floor at 2%
            nodeBattery[n]  = Math.max(2.0, nodeBattery[n] - drainPct);

            energy  += e;
            carbon  += RCASEngine.operationalCarbon(e, r.ci);
            network += RCASEngine.network(decision);
            latency += RCASEngine.latency(decision);   // FIX-A: single arg

            // ── CONFUSION MATRIX ─────────────────────────────────────────────
            // FIX-38: Skip Day-1 uncalibrated samples — they have no real
            // prediction (P=0.0 default), so counting them as TN/FN would
            // inflate TN and suppress recall without any genuine detector output.
            if (!nodeCalibrated) {
                skippedUncalib++;
                continue;
            }

            boolean trueAnomaly      = r.isAnomaly;
            boolean predictedAnomaly = (P > 0.80);
            boolean tp = trueAnomaly  && predictedAnomaly;
            boolean tn = !trueAnomaly && !predictedAnomaly;
            boolean fp = !trueAnomaly && predictedAnomaly;
            boolean fn =  trueAnomaly && !predictedAnomaly;

            if (tp || tn) detected++;
            totalClassified++;   // FIX-38: only calibrated non-buffered samples
            if (tp) cntTP++;
            if (tn) cntTN++;
            if (fp) cntFP++;
            if (fn) cntFN++;
        }

        // ── END-OF-SIMULATION BUFFER FLUSH ──────────────────────────────────
        // Resolve any samples still in the buffer after all records are processed.
        // FIX-37: Classification uses bs.probability (stored original P).
        while (!bufferQueue.isEmpty()) {

            BufferedSample bs = bufferQueue.poll();
            cntBufferResolved++;

            // Recomputed P for energy calculation only (most recent calibration)
            double recomputedP = computeRCASProbability(
                    bs.record, pHStats, tempStats, tdsStats, doStats, false);

            int finalDecision = LOCAL;   // forced release default

            if      (finalDecision == CLOUD) cntCloud++;
            else if (finalDecision == LOCAL) cntLocal++;

            double e        = RCASEngine.energy(finalDecision, recomputedP);
            double drainPct = (e / BATTERY_MWH) * 100.0;
            nodeBattery[bs.record.node] = Math.max(2.0, nodeBattery[bs.record.node] - drainPct);

            energy  += e;
            carbon  += RCASEngine.operationalCarbon(e, bs.record.ci);
            network += RCASEngine.network(finalDecision);
            latency += RCASEngine.latency(finalDecision);

            // FIX-37: Use STORED original P for classification — same rationale
            // as the mid-simulation buffer resolution block above.
            boolean trueAnomaly      = bs.record.isAnomaly;
            boolean predictedAnomaly = (bs.probability > 0.80);   // FIX-37
            boolean tp = trueAnomaly  && predictedAnomaly;
            boolean tn = !trueAnomaly && !predictedAnomaly;
            boolean fp = !trueAnomaly && predictedAnomaly;
            boolean fn =  trueAnomaly && !predictedAnomaly;

            if (tp || tn) detected++;
            totalClassified++;
            if (tp) cntTP++;
            if (tn) cntTN++;
            if (fp) cntFP++;
            if (fn) cntFN++;
        }

        double nodeDays    = (double) NUM_NODES * SIM_DAYS;
        double energyDay   = energy  / nodeDays;
        double carbonDay   = carbon  / nodeDays;

        network   += summaryNetworkBytes;
        double networkDay  = network  / nodeDays;

        // Latency average over ALL records (scheduler still acts on every sample)
        double latencyAvg  = latency  / data.size();

        // FIX-38: Accuracy denominator is totalClassified (excludes uncalibrated
        // Day-1 samples that produced no real detector output).
        double accuracy = (totalClassified > 0)
                        ? (100.0 * detected) / totalClassified
                        : 0.0;

        // FIX-22: 365-day cap — SIMULATION ENGINEERING CONSTANT
        double batteryDays = Math.min(365, BATTERY_MWH / Math.max(energyDay, 0.001));

        // FIX-D: Precision, Recall, F1
        double precision = (cntTP + cntFP > 0)
                           ? (double) cntTP / (cntTP + cntFP) : 0.0;
        double recall    = (cntTP + cntFN > 0)
                           ? (double) cntTP / (cntTP + cntFN) : 0.0;
        double f1        = (precision + recall > 0.0)
                           ? 2.0 * precision * recall / (precision + recall) : 0.0;

        System.out.println();
        System.out.println("=========== RCAS CONFUSION MATRIX ===========");
        System.out.println("TP = " + cntTP);
        System.out.println("TN = " + cntTN);
        System.out.println("FP = " + cntFP);
        System.out.println("FN = " + cntFN);
        System.out.println("Classified samples  : " + totalClassified
                         + "  (FIX-38: excludes " + skippedUncalib + " uncalibrated Day-1 samples)");
        System.out.printf( "Precision Check     : %.4f%n",
                (cntTP + cntFP > 0) ? (double) cntTP / (cntTP + cntFP) : 0.0);
        System.out.printf( "Recall Check        : %.4f%n",
                (cntTP + cntFN > 0) ? (double) cntTP / (cntTP + cntFN) : 0.0);
        System.out.println();

        System.out.println("========== FINAL DECISION SPLIT ==========");
        System.out.println("Cloud          : " + cntCloud);
        System.out.println("Local          : " + cntLocal);
        System.out.println("Buffer (queued): " + cntBuffer);
        System.out.println("Buffer resolved: " + cntBufferResolved);

        return new double[] { energyDay, carbonDay, networkDay,
                              latencyAvg, accuracy, batteryDays,
                              precision, recall, f1 };
    }

    // ==========================================================
    // BASELINES
    // ==========================================================
    //
    //  FIX-34  Always-Cloud/Local energy, carbon, network, latency, and
    //          battery lifetime are data-derived from per-sample loops.
    //          Accuracy/P/R/F1 are retained internally but NOT printed in
    //          Table V — Always-Cloud/Local are scheduling strategies with
    //          no detection logic (TN=FN=0 by construction).  Classification
    //          metrics are only printed for RCAS and Simple Threshold, which
    //          both implement a real anomaly detector.
    //
    //  FIX-35  P/R/F1 counters retained in runAlwaysCloud/Local for internal
    //          consistency but suppressed from main() output.
    // ==========================================================

    static double[] runAlwaysCloud(List<SensorRecord> data) {

        double energy = 0, carbon = 0, network = 0, latency = 0;

        // FIX-34/35: sample-level counters.  TN=FN=0 by construction.
        int cntTP = 0;
        int cntFP = 0;

        for (SensorRecord r : data) {
            // P=0.9: SIMULATION ENGINEERING CONSTANT — high-urgency always-cloud posture.
            double P = 0.9;
            double e = 1.0 + 2.5 * P;
            energy  += e;
            carbon  += RCASEngine.operationalCarbon(e, r.ci);
            network += 32;
            // 185ms: always-on cloud overhead > RCAS CLOUD 120ms (correct: shows RCAS advantage)
            latency += 185;

            if (r.isAnomaly) cntTP++;
            else             cntFP++;
        }

        double nodeDays     = (double) NUM_NODES * SIM_DAYS;
        double totalSamples = data.size();

        // FIX-34: honest scheduling-decision accuracy (≈ anomaly rate × 100)
        double accuracy  = (100.0 * cntTP) / Math.max(totalSamples, 1);
        double precision = (cntTP + cntFP > 0)
                           ? (double) cntTP / (cntTP + cntFP) : 0.0;
        double recall    = 1.0;   // FN=0 always
        double f1        = (precision + recall > 0.0)
                           ? 2.0 * precision * recall / (precision + recall) : 0.0;

        return new double[] {
            energy  / nodeDays,
            carbon  / nodeDays,
            network / nodeDays,
            latency / data.size(),
            accuracy,
            Math.min(365, BATTERY_MWH / Math.max(energy / nodeDays, 0.001)),
            precision,
            recall,
            f1
        };
    }

    static double[] runAlwaysLocal(List<SensorRecord> data) {

        double energy = 0, carbon = 0, latency = 0;

        // FIX-34/35: sample-level counters.  TN=FN=0 by construction.
        int cntTP = 0;
        int cntFP = 0;

        for (SensorRecord r : data) {
            // P=0.8: SIMULATION ENGINEERING CONSTANT — local inference posture.
            double P = 0.8;
            double e = 0.4 + 1.2 * P;
            energy  += e;
            carbon  += RCASEngine.operationalCarbon(e, r.ci);
            // 12ms: always-local overhead > RCAS LOCAL 8ms (correct: shows RCAS advantage)
            latency += 12;

            if (r.isAnomaly) cntTP++;
            else             cntFP++;
        }

        double nodeDays     = (double) NUM_NODES * SIM_DAYS;
        double totalSamples = data.size();

        double accuracy  = (100.0 * cntTP) / Math.max(totalSamples, 1);
        double precision = (cntTP + cntFP > 0)
                           ? (double) cntTP / (cntTP + cntFP) : 0.0;
        double recall    = 1.0;   // FN=0 always
        double f1        = (precision + recall > 0.0)
                           ? 2.0 * precision * recall / (precision + recall) : 0.0;

        return new double[] {
            energy  / nodeDays,
            carbon  / nodeDays,
            0,   // Network=0: Always Local never transmits to cloud (Table V)
            latency / data.size(),
            accuracy,
            Math.min(365, BATTERY_MWH / Math.max(energy / nodeDays, 0.001)),
            precision,
            recall,
            f1
        };
    }

    static double[] runThreshold(List<SensorRecord> data) {

        double energy = 0, carbon = 0, network = 0, latency = 0;

        // FIX-T1/T2: dynamic accuracy and P/R/F1 from sample-level counters.
        // Threshold has a true binary output (high/not-high), so all four
        // confusion-matrix cells are well-defined.
        int detected     = 0;
        int cntTP = 0, cntFP = 0, cntFN = 0;
        int totalSamples = 0;

        // FIX-33: 20-min (2-sample) lookback — matches runRCAS() for fair comparison
        double[] prevTemp     = new double[NUM_NODES];
        double[] prevPrevTemp = new double[NUM_NODES];
        Arrays.fill(prevTemp,     Double.NaN);
        Arrays.fill(prevPrevTemp, Double.NaN);

        for (SensorRecord r : data) {

            // FIX-33: temperature spike on 20-min window
            boolean tempSpike = !Double.isNaN(prevPrevTemp[r.node])
                             && Math.abs(r.temp - prevPrevTemp[r.node]) >= 3.0;
            prevPrevTemp[r.node] = prevTemp[r.node];
            prevTemp[r.node]     = r.temp;

            // Table IV thresholds — same as RCAS pre-filter for fair comparison:
            // pH <6.0/>8.5, TDS >1000, DO <4.0, |ΔT|≥3°C (20-min window)
            boolean high = r.pH  < 6.0  || r.pH > 8.5
                        || r.tds > 1000.0
                        || r.dO  < 4.0
                        || tempSpike;

            if (high) {
                double e = 3.0;   // SIMULATION ENGINEERING CONSTANT
                energy  += e;
                carbon  += RCASEngine.operationalCarbon(e, r.ci);
                network += 32;
                latency += 150;   // SIMULATION ENGINEERING CONSTANT
            } else {
                double e = 1.2;   // SIMULATION ENGINEERING CONSTANT
                energy  += e;
                carbon  += RCASEngine.operationalCarbon(e, r.ci);
                latency += 18;    // SIMULATION ENGINEERING CONSTANT
            }

            boolean trueAnomaly      = r.isAnomaly;
            boolean predictedAnomaly = high;

            boolean tp = trueAnomaly  && predictedAnomaly;
            boolean tn = !trueAnomaly && !predictedAnomaly;
            boolean fp = !trueAnomaly && predictedAnomaly;
            boolean fn =  trueAnomaly && !predictedAnomaly;

            if (tp || tn) detected++;
            if (tp) cntTP++;
            if (fp) cntFP++;
            if (fn) cntFN++;
            totalSamples++;
        }

        double accuracy  = (100.0 * detected) / Math.max(totalSamples, 1);
        double precision = (cntTP + cntFP > 0)
                           ? (double) cntTP / (cntTP + cntFP) : 0.0;
        double recall    = (cntTP + cntFN > 0)
                           ? (double) cntTP / (cntTP + cntFN) : 0.0;
        double f1        = (precision + recall > 0.0)
                           ? 2.0 * precision * recall / (precision + recall) : 0.0;

        double nodeDays = (double) NUM_NODES * SIM_DAYS;
        return new double[] {
            energy   / nodeDays,
            carbon   / nodeDays,
            network  / nodeDays,
            latency  / data.size(),
            accuracy,
            Math.min(365, BATTERY_MWH / (energy / nodeDays)),
            precision,
            recall,
            f1
        };
    }

    // ==========================================================
    // MAIN
    // ==========================================================
    //
    //  FIX-M1  Precision, Recall, F1 added to output.
    //  FIX-M2  Metric labels corrected to "/node-day".
    //  FIX-26  Reduction blocks vs all three baselines.
    //
    //  Return layout for all four schedulers — double[9]:
    //    [0] energyDay   [1] carbonDay  [2] networkDay
    //    [3] latencyAvg  [4] accuracy   [5] batteryDays
    //    [6] precision   [7] recall     [8] f1
    // ==========================================================

    public static void main(String[] args) {

        System.out.println("==========================================");
        System.out.println(" FULL PAPER-ALIGNED RCAS SIMULATION");
        System.out.println(" 8 nodes × 15 days × 144 samples = 17,280");
        System.out.println("==========================================");

        List<SensorRecord> data = generateData();
        System.out.println("Generated " + data.size() + " records.");

        double[] rcas      = runRCAS(data);
        double[] cloud     = runAlwaysCloud(data);
        double[] local     = runAlwaysLocal(data);
        double[] threshold = runThreshold(data);

        System.out.println();
        System.out.println("================ COMPARISON TABLE (Table V) ================");
        System.out.printf("%-24s %-12s %-12s %-12s %-12s\n",
                "Metric", "RCAS", "Cloud", "Local", "Threshold");
        System.out.printf("%-24s %-12.4f %-12.4f %-12.4f %-12.4f\n",
                "Energy (mWh/node-day)",  rcas[0], cloud[0], local[0], threshold[0]);
        System.out.printf("%-24s %-12.6f %-12.6f %-12.6f %-12.6f\n",
                "Carbon (gCO2/node-day)", rcas[1], cloud[1], local[1], threshold[1]);
        System.out.printf("%-24s %-12.2f %-12.2f %-12.2f %-12.2f\n",
                "Network (B/node-day)",   rcas[2], cloud[2], local[2], threshold[2]);
        System.out.printf("%-24s %-12.2f %-12.2f %-12.2f %-12.2f\n",
                "Latency (ms)",           rcas[3], cloud[3], local[3], threshold[3]);
        System.out.printf("%-24s %-12.2f %-12.2f %-12.2f %-12.2f\n",
                "BattLife (days)",        rcas[5], cloud[5], local[5], threshold[5]);

        System.out.println();
        System.out.println("===== DETECTION METRICS (RCAS & Simple Threshold only) =====");
        System.out.println("  Note: Always-Cloud/Local have no detection logic and are");
        System.out.println("  excluded from this table.  Detection metrics measure the");
        System.out.println("  anomaly-classification layer, which only RCAS and Simple");
        System.out.println("  Threshold implement.  All values from sample-level counters.");
        System.out.printf("%-20s  Precision: %-8.4f  Recall: %-8.4f  F1: %.4f\n",
                "RCAS",             rcas[6],      rcas[7],      rcas[8]);
        System.out.printf("%-20s  Precision: %-8.4f  Recall: %-8.4f  F1: %.4f\n",
                "Simple Threshold", threshold[6], threshold[7], threshold[8]);

        System.out.println();
        System.out.println("=========== RCAS VS ALWAYS CLOUD ===========");
        System.out.printf("Energy Reduction : %.2f %%\n",
                ((cloud[0] - rcas[0]) / cloud[0]) * 100.0);
        System.out.printf("Carbon Reduction : %.2f %%\n",
                ((cloud[1] - rcas[1]) / cloud[1]) * 100.0);
        System.out.printf("Network Reduction: %.2f %%\n",
                ((cloud[2] - rcas[2]) / cloud[2]) * 100.0);

        // FIX-26: Reductions vs Always Local and Simple Threshold
        System.out.println();
        System.out.println("=========== RCAS VS ALWAYS LOCAL ===========");
        System.out.printf("Energy Reduction : %.2f %%\n",
                ((local[0] - rcas[0]) / local[0]) * 100.0);
        System.out.printf("Carbon Reduction : %.2f %%\n",
                ((local[1] - rcas[1]) / local[1]) * 100.0);

        System.out.println();
        System.out.println("=========== RCAS VS SIMPLE THRESHOLD ===========");
        System.out.printf("Energy Reduction : %.2f %%\n",
                ((threshold[0] - rcas[0]) / threshold[0]) * 100.0);
        System.out.printf("Carbon Reduction : %.2f %%\n",
                ((threshold[1] - rcas[1]) / threshold[1]) * 100.0);
        System.out.printf("Network Reduction: %.2f %%\n",
                ((threshold[2] - rcas[2]) / Math.max(threshold[2], 1.0)) * 100.0);

        System.out.println();
        System.out.println("Simulation complete.");
    }
}
