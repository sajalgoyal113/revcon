"""Paths and model configuration. Everything is overridable via environment / .env."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("SAYDO_DATA", os.path.join(ROOT, "data"))
TRANSCRIPTS = os.path.join(DATA, "transcripts")
CACHE = os.path.join(DATA, "cache")            # LLM response cache (hash-keyed, makes reruns free)
FINANCIALS = os.path.join(DATA, "financials")  # Screener P&L + price snapshots
OUT = os.path.join(DATA, "out")                # pipeline artifacts


def _load_dotenv():
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# Provider configuration: "gemini", "meta", or "openai"
LLM_PROVIDER = os.environ.get("CONCALL_LLM_PROVIDER", "gemini").lower()

# Google Gemini API (Gemini 3.8 frontier models)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_EXTRACT_MODEL = os.environ.get("GEMINI_EXTRACT_MODEL", "gemini-3.8-flash")
GEMINI_JUDGE_MODEL = os.environ.get("GEMINI_JUDGE_MODEL", "gemini-3.8-flash")
GEMINI_FRONTIER_MODEL = os.environ.get("GEMINI_FRONTIER_MODEL", "gemini-3.8-pro")
GEMINI_TRANSCRIBE_MODEL = os.environ.get("GEMINI_TRANSCRIBE_MODEL", "gemini-3.8-flash")

# Meta Model API (fallback or when explicitly requested)
META_API_KEY = os.environ.get("META_MODEL_API_KEY", "")
META_BASE_URL = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")

# OpenAI API (optional)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Active model names depending on provider
if LLM_PROVIDER == "gemini":
    EXTRACT_MODEL = GEMINI_EXTRACT_MODEL
    JUDGE_MODEL = GEMINI_JUDGE_MODEL
    FRONTIER_MODEL = GEMINI_FRONTIER_MODEL
    TRANSCRIBE_MODEL = GEMINI_TRANSCRIBE_MODEL
else:
    EXTRACT_MODEL = os.environ.get("SAYDO_EXTRACT_MODEL", "muse-spark-1.3")
    JUDGE_MODEL = os.environ.get("SAYDO_JUDGE_MODEL", "muse-spark-1.3")
    FRONTIER_MODEL = os.environ.get("SAYDO_FRONTIER_MODEL", "muse-wonder-1.0")
    TRANSCRIBE_MODEL = os.environ.get("SAYDO_TRANSCRIBE_MODEL", "muse-voice-transcribe-1.0")

# Optional: fine-tuned Llama student served on Baseten
STUDENT_URL = os.environ.get("SAYDO_STUDENT_URL", "")
STUDENT_KEY = os.environ.get("SAYDO_STUDENT_KEY", "")
STUDENT_MODEL = os.environ.get("SAYDO_STUDENT_MODEL", "saydo-student")

# Companies left out of the published universe.
EXCLUDE = {t.strip().upper() for t in os.environ.get("SAYDO_EXCLUDE", "ETERNAL").split(",") if t.strip()}
CONCURRENCY = int(os.environ.get("SAYDO_CONCURRENCY", "8"))

for d in (CACHE, FINANCIALS, OUT):
    os.makedirs(d, exist_ok=True)
