"""Tests for management guidance accuracy prediction and track-record analysis."""
import json
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saydo import history, predict, score


class TestGuidancePredict(unittest.TestCase):
    def setUp(self):
        self.resolved_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "out", "resolved.json")
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "out", "model.json")
        with open(self.resolved_path) as f:
            self.resolved = json.load(f)
        with open(self.model_path) as f:
            self.model = json.load(f)

    def test_guidance_track_record_structure(self):
        rec = history.guidance_track_record(self.resolved, "KAYNES")
        self.assertEqual(rec["ticker"], "KAYNES")
        self.assertIn("delivery_rate", rec)
        self.assertIn("style", rec)
        self.assertIn("revenue_guidance", rec)
        self.assertIn("margin_guidance", rec)
        self.assertIn("capex_guidance", rec)
        self.assertIn("behavior", rec)
        self.assertGreater(rec["total_guided"], 0)

    def test_predict_guidance_accuracy(self):
        pred = predict.predict_guidance_accuracy(
            model=self.model,
            resolved=self.resolved,
            ticker="KAYNES",
            category="revenue_growth",
            value=30.0,
            horizon_months=12,
            strength="firm",
            role="MD",
            quote="We are confident in guiding 30% revenue growth for the coming year.",
            asof="2026-03-31"
        )
        self.assertEqual(pred["ticker"], "KAYNES")
        self.assertEqual(pred["category"], "revenue_growth")
        self.assertEqual(pred["guided_value"], 30.0)
        self.assertIsNotNone(pred["adjusted_value"])
        self.assertGreaterEqual(pred["p_kept"], 0.0)
        self.assertLessEqual(pred["p_kept"], 1.0)
        self.assertIn(pred["grade"], ["A", "B", "C", "D", "F"])
        self.assertIn("diagnostics", pred)
        self.assertIn("historical_say_do_score", pred["diagnostics"])

    def test_margin_guidance_adjustment(self):
        pred = predict.predict_guidance_accuracy(
            model=self.model,
            resolved=self.resolved,
            ticker="COFORGE",
            category="ebitda_margin",
            value=18.5,
            horizon_months=12,
            strength="firm",
            role="CFO",
            asof="2026-01-01"
        )
        self.assertEqual(pred["category"], "ebitda_margin")
        self.assertIsNotNone(pred["adjusted_value"])
        self.assertGreater(pred["p_kept"], 0.0)

    def test_no_leak_of_future_guidance(self):
        # A test run as of 2024-01-01 should not include outcomes settled in 2025 or 2026
        past_record = history.guidance_track_record(self.resolved, "KAYNES", asof="2024-01-01")
        current_record = history.guidance_track_record(self.resolved, "KAYNES", asof="2026-11-01")
        self.assertLessEqual(past_record["total_guided"], current_record["total_guided"])

    def test_simulate_guidance_hurdle_curve(self):
        curve = predict.simulate_guidance_hurdle_curve(
            model=self.model,
            resolved=self.resolved,
            ticker="KAYNES",
            category="revenue_growth",
            steps=7
        )
        self.assertEqual(curve["ticker"], "KAYNES")
        self.assertEqual(curve["category"], "revenue_growth")
        self.assertEqual(len(curve["points"]), 7)
        self.assertIn("benchmark_trailing", curve)
        self.assertGreater(curve["benchmark_trailing"], 0.0)
        # Check that as guided revenue target increases, delivery probability does not increase (monotonic/decreasing)
        p_vals = [pt["p_kept"] for pt in curve["points"]]
        self.assertGreaterEqual(p_vals[0], p_vals[-1])
        for pt in curve["points"]:
            self.assertGreaterEqual(pt["p_kept"], 0.0)
            self.assertLessEqual(pt["p_kept"], 1.0)
            self.assertIsNotNone(pt["adjusted_value"])


if __name__ == "__main__":
    unittest.main()
