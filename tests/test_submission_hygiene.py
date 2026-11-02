"""Submission hygiene: no corporate proxy script, no offline-broken UI paths, theme consistency."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _app_source():
    with open(os.path.join(ROOT, "app.py")) as f:
        return f.read()


def test_no_corporate_proxy_script():
    assert not os.path.exists(os.path.join(ROOT, "deploy", "trust_netskope.sh"))


def test_no_offline_memo_button():
    src = _app_source()
    assert "Synthesize Credibility Memo" not in src
    assert "credibility_memo" not in src


def test_no_dead_llama_provider_option():
    src = _app_source()
    assert "Llama Student" not in src
    assert "llm_choice" not in src


def test_dark_theme_consistency():
    src = _app_source()
    assert 'SURF, INK, INK2, MUTED, GRID, AXIS = "#06080d", "#f8fafc"' in src
    assert 'SURF = "#fcfcfb"' not in src
    assert 'INK = "#0b0b0b"' not in src
    with open(os.path.join(ROOT, ".streamlit", "config.toml")) as f:
        cfg = f.read()
    assert 'base = "dark"' in cfg
    assert 'backgroundColor = "#06080d"' in cfg


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
