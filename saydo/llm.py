"""Multi-provider LLM client supporting Google Gemini and Meta Model API (OpenAI-compatible).

- Google Gemini models (gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash) for state-of-the-art
  earnings call reasoning, guidance extraction, and credibility synthesis.
- Meta Model API (muse-spark-1.3, muse-wonder-1.0, muse-voice-transcribe-1.0) for backwards
  compatibility and hackathon reproducibility.
- Disk cache keyed by (model, system, user, reasoning_effort) so full pipelines and evaluations
  can re-run for free with zero API cost.
- Token accounting and error-resilient JSON parsing.
"""
import base64
import hashlib
import json
import os
import re
import threading
import time

import requests

from . import config

_lock = threading.Lock()
USAGE = {"calls": 0, "cached": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}

_meta_client = None
_student_client = None
_http_session = requests.Session()


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


def is_gemini_model(model_name):
    if not model_name:
        return config.LLM_PROVIDER == "gemini"
    m = model_name.lower()
    return m.startswith("gemini") or "gemini" in m


def _call_gemini(system, user, model="gemini-3.8-flash", max_tokens=8192, api_key=None, timeout=120):
    """Direct Google Gemini REST API call with JSON mode and schema resilience (Gemini 3.8 primary)."""
    key = (api_key or config.GEMINI_API_KEY).strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required to use Google Gemini models.")
    
    api_model = model
    if api_model.startswith("models/"):
        api_model = api_model[7:]
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system}\n\nUSER INPUT:\n{user}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json"
        }
    }
    
    resp = _http_session.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
    
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return None, 0, 0
    
    part_text = ""
    parts = candidates[0].get("content", {}).get("parts", [])
    for p in parts:
        if "text" in p:
            part_text += p["text"]
            
    usage = data.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", 0)
    completion_tokens = usage.get("candidatesTokenCount", 0)
    
    return part_text, prompt_tokens, completion_tokens


def chat_json(system, user, model=None, max_tokens=8000, reasoning_effort="low", retries=3, use_cache=True, api_key=None):
    """One JSON-returning model call supporting Gemini and Meta/OpenAI. Returns parsed JSON or None."""
    model = model or config.EXTRACT_MODEL
    key = hashlib.sha256(json.dumps([model, system, user, reasoning_effort]).encode()).hexdigest()
    path = _cache_path(key)
    if use_cache and os.path.exists(path):
        with _lock:
            USAGE["cached"] += 1
        return json.load(open(path))["parsed"]

    use_gemini = is_gemini_model(model)
    last_err = None

    for attempt in range(retries):
        try:
            if use_gemini:
                text, p_tok, c_tok = _call_gemini(
                    system=system, user=user, model=model, max_tokens=max_tokens, api_key=api_key or config.GEMINI_API_KEY
                )
                parsed = parse_json(text)
                with _lock:
                    USAGE["calls"] += 1
                    USAGE["prompt_tokens"] += p_tok
                    USAGE["completion_tokens"] += c_tok
            else:
                if config.LLM_PROVIDER == "gemini":
                    raise RuntimeError(f"Attempted to call non-Gemini model '{model}' while LLM_PROVIDER is set to gemini. Please use gemini-3.8-flash or gemini-3.8-pro.")
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
    """Earnings-call audio -> text using Gemini multimodal audio or Meta Muse."""
    if config.GEMINI_API_KEY or api_key:
        # Native audio transcription with Gemini
        key = (api_key or config.GEMINI_API_KEY).strip()
        mime_type = "audio/mp3" if audio_path.endswith(".mp3") else "audio/wav" if audio_path.endswith(".wav") else "audio/m4a"
        with open(audio_path, "rb") as f:
            audio_bytes = base64.b64encode(f.read()).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_TRANSCRIBE_MODEL}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": audio_bytes}},
                        {"text": "Transcribe this earnings conference call audio completely and verbatim. Preserve speaker names and timestamps where possible."}
                    ]
                }
            ]
        }
        resp = _http_session.post(url, headers=headers, json=payload, timeout=300)
        if resp.status_code == 200:
            candidates = resp.json().get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"]

    if config.LLM_PROVIDER == "gemini":
        raise RuntimeError("GEMINI_API_KEY is not set. Please provide a GEMINI_API_KEY in .env or the sidebar to transcribe audio with Gemini 3.8.")

    # Fallback to Meta Muse (only if provider is meta)
    with open(audio_path, "rb") as f:
        r = meta_client().audio.transcriptions.create(model=config.TRANSCRIBE_MODEL, file=f)
    return getattr(r, "text", None) or str(r)
