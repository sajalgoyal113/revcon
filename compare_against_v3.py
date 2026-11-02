#!/usr/bin/env python3
"""Side-by-side benchmark comparison: De-Overfitted V4 vs Earnings Algorithm vs Package V3.

Executes all algorithms on identical benchmark forward guidance statements and
compares empirical validation metrics (LOCO AUC, Brier calibration, Walk-forward splits).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from saydo import predict

BENCHMARKS = [
    {
        "ticker": "KAYNES",
        "category": "revenue_growth",
        "value": 30.0,
        "horizon_months": 12,
        "role": "MD",
        "strength": "firm",
        "quote": "We are confident in guiding 30% revenue growth for the coming year.",
    },
    {
        "ticker": "COFORGE",
        "category": "ebitda_margin",
        "value": 18.5,
        "horizon_months": 12,
        "role": "CFO",
        "strength": "firm",
        "quote": "We expect adjusted EBITDA margin to be around 18.5%.",
    },
    {
        "ticker": "DIXON",
        "category": "revenue_growth",
        "value": 45.0,
        "horizon_months": 12,
        "role": "MD",
        "strength": "target",
        "quote": "Targeting 45% revenue growth driven by mobile and EMS expansion.",
    },
    {
        "ticker": "SYRMA",
        "category": "ebitda_margin",
        "value": 10.5,
        "horizon_months": 12,
        "role": "MD",
        "strength": "firm",
        "quote": "We guide consolidated operating EBITDA margin of 10.5% for the full fiscal year.",
    },
    {
        "ticker": "EMMVEE",
        "category": "capacity",
        "value": 6.0,
        "horizon_months": 12,
        "role": "MD",
        "strength": "firm",
        "quote": "We will commission our 6 GW solar cell and module facility on schedule by Q4.",
    },
]


def main():
    model = json.load(open(os.path.join(ROOT, "data", "out", "model.json")))
    resolved = json.load(open(os.path.join(ROOT, "data", "out", "resolved.json")))

    loco = model["evaluation"]["loco"]
    wf = model["evaluation"]["walk_forward"]

    # Reference baselines from earnings_algorithm_package and v3
    earn_ref = {
        "loco_auc": 0.6537, "loco_ci": "[0.625, 0.682]", "loco_brier": 0.2246,
        "wf_auc": 0.6483, "wf_brier": 0.2295, "n_feat": 26,
        "prior_auc": 0.5334, "muse_auc": 0.5486, "cat_w": +0.001,
        "preds": {"KAYNES": 0.594, "COFORGE": 0.855, "DIXON": 0.634, "SYRMA": 0.738, "EMMVEE": 0.638},
    }
    v3_ref = {
        "loco_auc": 0.6456, "loco_ci": "[0.617, 0.675]", "loco_brier": 0.2255,
        "wf_auc": 0.6483, "wf_brier": 0.2295, "n_feat": 27,
        "prior_auc": 0.5334, "muse_auc": None, "cat_w": -0.129,
        "preds": {"KAYNES": 0.653, "COFORGE": 0.876, "DIXON": 0.627, "SYRMA": 0.867, "EMMVEE": 0.655},
    }

    coef_map = dict(model["coefficients"])

    print("=" * 94)
    print(" 🎯 HEAD-TO-HEAD EVALUATION: DE-OVERFITTED V4 vs. EARNINGS_ALGO vs. PACKAGE V3")
    print("=" * 94)
    print(f"{'Evaluation Metric':<36} | {'De-Overfitted V4':<18} | {'Earnings Algo':<16} | {'Overfit V3':<14}")
    print("-" * 94)
    print(f"{'Out-of-Company (LOCO) ROC AUC':<36} | {loco['auc_model']:<18.4f} | {earn_ref['loco_auc']:<16.4f} | {v3_ref['loco_auc']:<14.4f}")
    print(f"{'  90% Confidence Interval':<36} | {str(loco['auc_ci90']):<18} | {earn_ref['loco_ci']:<16} | {v3_ref['loco_ci']:<14}")
    print(f"{'LOCO Brier Score (Lower=Better)':<36} | {loco['brier_model']:<18.4f} | {earn_ref['loco_brier']:<16.4f} | {v3_ref['loco_brier']:<14.4f}")
    print(f"{'Temporal Walk-Forward ROC AUC':<36} | {wf['auc_model']:<18.4f} | {earn_ref['wf_auc']:<16.4f} | {v3_ref['wf_auc']:<14.4f}")
    print(f"{'Walk-Forward Brier (Lower=Better)':<36} | {wf['brier_model']:<18.4f} | {earn_ref['wf_brier']:<16.4f} | {v3_ref['wf_brier']:<14.4f}")
    print(f"{'Company Prior Score Only AUC':<36} | {loco['auc_prior_score_only']:<18.4f} | {earn_ref['prior_auc']:<16.4f} | {v3_ref['prior_auc']:<14.4f}")
    print(f"{'Zero-Shot Muse Forecast Prior AUC':<36} | {loco['auc_muse_forecast_only']:<18.4f} | {earn_ref['muse_auc']:<16.4f} | {'N/A (Dropped)':<14}")
    print(f"{'`cat_kept_shrunk` Learned Weight':<36} | {coef_map.get('cat_kept_shrunk', 0):<+18.3f} | {earn_ref['cat_w']:<+16.3f} | {v3_ref['cat_w']:<+14.3f}")
    print(f"{'Feature Dimensionality':<36} | {len(model['features']):<18} | {earn_ref['n_feat']:<16} | {v3_ref['n_feat']:<14}")

    print("\n2. LIVE BENCHMARK GUIDANCE PREDICTIONS SIDE-BY-SIDE")
    print("-" * 94)
    print(f"{'Company':<9} | {'Guided Target':<17} | {'De-Overfitted V4':<22} | {'Earnings Algo':<16} | {'Overfit V3':<14}")
    print("-" * 94)
    for b in BENCHMARKS:
        t = b["ticker"]
        pr = predict.predict_guidance_accuracy(model=model, resolved=resolved, **b)
        p4 = pr["p_kept"]
        g4 = pr["grade"]
        adj4 = pr.get("adjusted_value")
        s4 = f"{p4*100:.1f}% ({g4}) -> {adj4:g}" if adj4 else f"{p4*100:.1f}% ({g4})"
        se = f"{earn_ref['preds'][t]*100:.1f}%"
        sv = f"{v3_ref['preds'][t]*100:.1f}%"
        target_str = f"{b['value']:g}% {b['category'][:9]}"
        print(f"{t:<9} | {target_str:<17} | {s4:<22} | {se:<16} | {sv:<14}")
    print("=" * 94)


if __name__ == "__main__":
    main()
