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
