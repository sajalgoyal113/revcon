#!/usr/bin/env python3
"""Standalone evaluation runner for the Concall Management Guidance Predictor.

Executes all unit tests and runs forward guidance predictions on benchmark companies.
Zero external network calls required.
"""
import os
import sys
import json
import unittest

# Ensure repo root is in python path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from saydo import predict, history, score, financials


def run_tests():
    print("=" * 70)
    print("1. RUNNING CORE ALGORITHM & GUIDANCE PREDICTION TESTS")
    print("=" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover tests
    core_tests = loader.discover(os.path.join(ROOT, "tests"), pattern="test_*.py")
    suite.addTests(core_tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        print("❌ Tests failed!")
        return False
    print("✅ All unit tests passed successfully!\n")
    return True


def run_sample_predictions():
    print("=" * 70)
    print("2. RUNNING LIVE BENCHMARK GUIDANCE PREDICTIONS")
    print("=" * 70)
    resolved_path = os.path.join(ROOT, "data", "out", "resolved.json")
    model_path = os.path.join(ROOT, "data", "out", "model.json")

    if not os.path.exists(resolved_path) or not os.path.exists(model_path):
        print(f"Data files missing in {ROOT}/data/out/")
        return

    with open(resolved_path) as f:
        resolved = json.load(f)
    with open(model_path) as f:
        model = json.load(f)

    benchmarks = [
        {
            "ticker": "KAYNES",
            "category": "revenue_growth",
            "value": 30.0,
            "horizon_months": 12,
            "role": "MD",
            "strength": "firm",
            "quote": "We are confident in guiding 30% revenue growth for the coming year."
        },
        {
            "ticker": "COFORGE",
            "category": "ebitda_margin",
            "value": 18.5,
            "horizon_months": 12,
            "role": "CFO",
            "strength": "firm",
            "quote": "We expect adjusted EBITDA margin to be around 18.5%."
        },
        {
            "ticker": "DIXON",
            "category": "revenue_growth",
            "value": 45.0,
            "horizon_months": 12,
            "role": "MD",
            "strength": "target",
            "quote": "Targeting 45% revenue growth driven by mobile and EMS expansion."
        },
        {
            "ticker": "SYRMA",
            "category": "ebitda_margin",
            "value": 10.5,
            "horizon_months": 12,
            "role": "MD",
            "strength": "firm",
            "quote": "We guide consolidated operating EBITDA margin of 10.5% for the full fiscal year."
        }
    ]

    for bm in benchmarks:
        pred = predict.predict_guidance_accuracy(
            model=model,
            resolved=resolved,
            ticker=bm["ticker"],
            category=bm["category"],
            value=bm["value"],
            horizon_months=bm["horizon_months"],
            strength=bm["strength"],
            role=bm["role"],
            quote=bm["quote"]
        )
        print(f"Company: {pred['ticker']} ({pred['category']})")
        print(f"  • Management Guided:     {pred['guided_value']}%")
        print(f"  • P(Guidance Kept):      {pred['p_kept']*100:.1f}% (Grade: {pred['grade']})")
        print(f"  • Credibility Adjusted:  {pred['adjusted_value']:.1f}% ({pred['adjustment_note']})")
        print(f"  • Historical Style:      {pred['track_record']['style']}")
        print(f"  • Track Record Score:    {pred['diagnostics']['historical_say_do_score']:.1f} / 100 "
              f"(Category Score: {pred['diagnostics']['category_say_do_score']:.1f} / 100)")
        if pred.get('risks'):
            print(f"  • Key Risk Flag:         {pred['risks'][0]}")
        print()

    ev = model.get("evaluation", {})
    loco = ev.get("loco", {})
    wf = ev.get("walk_forward", {})
    print("=" * 70)
    print("3. MODEL SUMMARY & GENERALIZATION METRICS")
    print("=" * 70)
    print("• Architecture: Ensemble Stacking (Bayesian MAP Logistic Regression + Pure-NumPy HistGBDT)")
    print(f"• Out-of-Sample LOCO ROC AUC:  {loco.get('auc_model', 0):.3f} (90% CI {loco.get('auc_ci90')}) | Brier: {loco.get('brier_model', 0):.3f}")
    print(f"• Temporal Walk-Forward AUC:   {wf.get('auc_model', 0):.3f} (90% CI {wf.get('auc_ci90')}) | Brier: {wf.get('brier_model', 0):.3f}")
    print(f"• Base Dataset Size:           {ev.get('n', 1121):,} resolved guidance promises across 35 companies")
    print("=" * 70)


if __name__ == "__main__":
    ok = run_tests()
    if ok:
        run_sample_predictions()
