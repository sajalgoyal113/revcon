"""Submission hygiene: no corporate proxy script, no offline-broken UI paths, theme consistency."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _app_source():
    with open(os.path.join(ROOT, "app.py")) as f:
        return f.read()


def test_no_corporate_proxy_script():
    assert not os.path.exists(os.path.join(ROOT, "deploy", "trust_netskope.sh"))


def test_theme_consistency():
    src = _app_source()
    assert 'BG_CANVAS = "#FAF9F6"' in src
    assert 'BG_CARD = "#FFFFFF"' in src
    with open(os.path.join(ROOT, ".streamlit", "config.toml")) as f:
        cfg = f.read()
    assert 'base = "light"' in cfg
    assert 'backgroundColor = "#FAF9F6"' in cfg
    assert 'primaryColor = "#2563EB"' in cfg


def test_scores_integrity_no_artificial_inflation():
    import json
    with open(os.path.join(ROOT, "data", "out", "scores.json")) as f:
        scores = json.load(f)
    base_rate = scores.get("base_rate", 0)
    assert 45.0 <= base_rate <= 60.0, f"Base rate {base_rate} is out of realistic empirical bounds [45, 60]%"
    for c in scores.get("companies", []):
        assert c["score"] < 85.0, f"Company {c['ticker']} has inflated score {c['score']} >= 85.0; check evidence integrity!"


def test_evidence_negative_outcomes_preserved():
    import json
    with open(os.path.join(ROOT, "data", "out", "stats.json")) as f:
        stats = json.load(f)
    outcomes = stats.get("outcomes", {})
    missed = outcomes.get("MISSED", 0)
    revised_down = outcomes.get("REVISED_DOWN", 0)
    ghosted = outcomes.get("GHOSTED", 0)
    negative_total = missed + revised_down + ghosted
    assert negative_total >= 300, f"Negative outcomes too low ({negative_total}); evidence was likely overwritten by naive heuristic!"


def test_model_auc_generalization_bounds():
    import json
    with open(os.path.join(ROOT, "data", "out", "model.json")) as f:
        model = json.load(f)
    loco_auc = model.get("evaluation", {}).get("loco", {}).get("auc_model", 0)
    assert 0.60 <= loco_auc <= 0.70, f"LOCO AUC {loco_auc} is out of expected realistic bounds [0.60, 0.70]; check feature leakage!"


class TestSubmissionHygiene(unittest.TestCase):
    def test_all_hygiene_checks(self):
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
