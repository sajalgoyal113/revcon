"""Meta Model API client (Muse Spark, Muse Wonder, Muse Voice) plus the Llama student endpoint.

- Meta Model API (muse-spark-1.3, muse-wonder-1.0, muse-voice-transcribe-1.0)
  via OpenAI-compatible SDK (`https://api.meta.ai/v1`).
- Disk cache keyed by (model, system, user, reasoning_effort) so full pipelines and evaluations
  can re-run for free with zero API cost.
- Token accounting and error-resilient JSON parsing.
"""
import hashlib
import json
import os
import re
import threading
import time

from . import config

_lock = threading.Lock()
USAGE = {"calls": 0, "cached": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}

_meta_client = None
_student_client = None


def meta_client():
    global _meta_client
    if _meta_client is None:
        from openai import OpenAI
        if not config.META_API_KEY:
            raise RuntimeError("META_MODEL_API_KEY is not set (copy .env.example to .env).")
        _meta_client = OpenAI(api_key=config.META_API_KEY, base_url=config.META_BASE_URL, timeout=240)
    return _meta_client


def student_client():
    """Fine-tuned Llama student on Baseten."""
    global _student_client
    if _student_client is None:
        from openai import OpenAI
        if not config.STUDENT_URL:
            raise RuntimeError("SAYDO_STUDENT_URL is not set")
        _student_client = OpenAI(api_key=config.STUDENT_KEY, base_url=config.STUDENT_URL, timeout=240)
    return _student_client


def _cache_path(key):
    return os.path.join(config.CACHE, key[:2], key + ".json")


def parse_json(text):
    """Parse a JSON object/array from model output, tolerating code fences and prose."""
    if text is None:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = t.find(open_c), t.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                continue
    return None


def chat_json(system, user, model=None, max_tokens=8000, reasoning_effort="low", retries=3, use_cache=True, api_key=None):
    """One JSON-returning model call via Meta Model API (or the Llama student). Returns parsed JSON or None."""
    model = model or config.EXTRACT_MODEL
    key = hashlib.sha256(json.dumps([model, system, user, reasoning_effort]).encode()).hexdigest()
    path = _cache_path(key)
    if use_cache and os.path.exists(path):
        with _lock:
            USAGE["cached"] += 1
        return json.load(open(path))["parsed"]

    last_err = None

    for attempt in range(retries):
        try:
            # Meta Model API / OpenAI endpoint
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            is_student = model == config.STUDENT_MODEL and bool(config.STUDENT_URL)
            kw = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=0)
            if not is_student:
                kw["response_format"] = {"type": "json_object"}
                if reasoning_effort:
                    kw["reasoning_effort"] = reasoning_effort
            r = (student_client() if is_student else meta_client()).chat.completions.create(**kw)
            content = r.choices[0].message.content
            parsed = parse_json(content)
            u = r.usage
            with _lock:
                USAGE["calls"] += 1
                USAGE["prompt_tokens"] += u.prompt_tokens or 0
                USAGE["completion_tokens"] += u.completion_tokens or 0
                d = getattr(u, "completion_tokens_details", None)
                USAGE["reasoning_tokens"] += (getattr(d, "reasoning_tokens", 0) or 0) if d else 0

            if parsed is None:
                last_err = "unparseable JSON output"
                max_tokens = min(int(max_tokens * 1.8), 32000)
                continue

            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump({"model": model, "parsed": parsed}, open(path, "w"))
            return parsed

        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1) ** 2)

    print(f"   [llm] giving up after {retries} attempts: {str(last_err)[:200]}")
    return None


def transcribe(audio_path, api_key=None):
    """Earnings-call audio -> text using Meta Muse voice transcription."""
    with open(audio_path, "rb") as f:
        r = meta_client().audio.transcriptions.create(model=config.TRANSCRIBE_MODEL, file=f)
    return getattr(r, "text", None) or str(r)
