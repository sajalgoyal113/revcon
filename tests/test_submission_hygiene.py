"""Submission hygiene: no corporate proxy script, no offline-broken UI paths."""
import os

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
