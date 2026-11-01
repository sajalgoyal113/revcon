"""Modal: scale the Say-Do pipeline, fine-tune the Llama student, and serve the API.

Setup (once):
  pip install modal && modal setup
  modal secret create saydo-meta META_MODEL_API_KEY=... META_BASE_URL=https://api.meta.ai/v1
  modal secret create saydo-hf HF_TOKEN=...      # Llama 3.1 licence accepted on huggingface.co
  modal volume create saydo-data
  modal volume put saydo-data data/transcripts /transcripts        # 14 MB of public transcripts
  modal volume put saydo-data data/financials /financials
  modal volume put saydo-data data/out /out                        # after a local run (needed by finetune)

Run:
  modal run deploy/modal_app.py::pipeline          # fan-out extract + judge across containers, then build
  modal run deploy/modal_app.py::finetune          # LoRA SFT Llama-3.1-8B on Muse-verified extractions (H100)
  modal deploy deploy/modal_app.py                 # /leaderboard, /company, /analyze web endpoints

Cost guardrails: extraction/judging are CPU containers waiting on the Meta API (cents).
The fine-tune is the only GPU job: ~1 h on one H100 for ~700 chunks x 2 epochs. Check current
Modal GPU pricing before running; budget well under the $100 credit.
"""
import os

import modal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vol = modal.Volume.from_name("saydo-data", create_if_missing=True)
meta_secret = modal.Secret.from_name("saydo-meta")

cpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("openai>=1.40", "requests", "beautifulsoup4", "numpy", "fastapi[standard]")
    .env({"SAYDO_DATA": "/data"})
    .add_local_dir(os.path.join(ROOT, "saydo"), remote_path="/root/saydo")
)
gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.5.1", "transformers==4.46.3", "peft==0.13.2", "accelerate==1.1.1",
                 "datasets==3.1.0", "huggingface_hub")
    .env({"SAYDO_DATA": "/data", "HF_HOME": "/data/hf"})
)
app = modal.App("saydo")


def _calls(tickers=None):
    from saydo import transcripts
    return transcripts.load_calls(tickers)


@app.function(image=cpu_image, volumes={"/data": vol}, secrets=[meta_secret], timeout=1800,
              max_containers=12, retries=1)
def extract_one(call_id: str):
    from saydo import extract
    t = call_id.split(":")[0]
    call = next(c for c in _calls([t])[t] if c.id == call_id)
    res = extract.extract_call(call)
    vol.commit()  # persist the LLM cache
    return res


@app.function(image=cpu_image, volumes={"/data": vol}, secrets=[meta_secret], timeout=3600,
              max_containers=12, retries=1)
def judge_one(call_id: str, promises: list):
    from saydo import judge
    t = call_id.split(":")[0]
    call = next(c for c in _calls([t])[t] if c.id == call_id)
    ev = judge.judge_call(call, promises)
    vol.commit()
    return ev


@app.function(image=cpu_image, volumes={"/data": vol}, secrets=[meta_secret], timeout=7200)
def pipeline():
    import json
    from datetime import date
    from saydo import config, pipeline as P
    vol.reload()
    calls = _calls()
    ids = [c.id for cs in calls.values() for c in cs]
    results = {r["call_id"]: r for r in extract_one.map(ids, return_exceptions=False)}
    json.dump(results, open(os.path.join(config.OUT, "promises.json"), "w"), indent=1)
    from saydo import judge
    promises = [p for r in results.values() for p in r["promises"]]
    jobs = [(c.id, judge.open_promises(promises, t, c.date)) for t, cs in calls.items() for c in cs]
    jobs = [j for j in jobs if j[1]]   # ship only each call's open promises, not the whole ledger
    evidence = []
    for ev in judge_one.map([j[0] for j in jobs], [j[1] for j in jobs]):
        evidence.extend(ev)
    json.dump(evidence, open(os.path.join(config.OUT, "evidence.json"), "w"), indent=1)
    P.stage_build(calls, None, date.today())
    vol.commit()
    return json.load(open(os.path.join(config.OUT, "stats.json")))


# ----------------------------------------------------------------- Llama student fine-tune
BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


@app.function(image=gpu_image, gpu="H100", volumes={"/data": vol}, timeout=4 * 3600,
              secrets=[modal.Secret.from_name("saydo-hf")])
def finetune(epochs: int = 2, max_len: int = 10240, lr: float = 1e-4, rank: int = 16):
    """LoRA SFT: loss only on the assistant (JSON) tokens. Writes /data/student/{adapter,merged}."""
    import json
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq, Trainer,
                              TrainingArguments)
    vol.reload()
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=os.environ["HF_TOKEN"])
    tok.pad_token = tok.eos_token

    def encode(row):
        msgs = row["messages"]
        prompt = tok.apply_chat_template(msgs[:2], tokenize=False, add_generation_prompt=True)
        full = prompt + msgs[2]["content"] + tok.eos_token
        p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
        ids = tok(full, add_special_tokens=False)["input_ids"]
        labels = [-100] * len(p_ids) + ids[len(p_ids):]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}

    rows = [json.loads(l) for l in open("/data/out/sft_train.jsonl")]
    ds = Dataset.from_list(rows).map(encode, remove_columns=["messages", "call_id", "chunk"])
    ds = ds.filter(lambda r: len(r["input_ids"]) <= max_len)   # never train on truncated JSON targets
    print(f"training on {len(ds)} chunks")
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16,
                                                 attn_implementation="sdpa", token=os.environ["HF_TOKEN"])
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                             "gate_proj", "up_proj", "down_proj"]))
    args = TrainingArguments(output_dir="/data/student/ckpt", num_train_epochs=epochs, learning_rate=lr,
                             per_device_train_batch_size=1, gradient_accumulation_steps=8, bf16=True,
                             lr_scheduler_type="cosine", warmup_ratio=0.05, logging_steps=5,
                             save_strategy="no", report_to=[])
    Trainer(model=model, args=args, train_dataset=ds,
            data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100)).train()
    model.save_pretrained("/data/student/adapter")
    merged = model.merge_and_unload()
    merged.save_pretrained("/data/student/merged", safe_serialization=True)
    tok.save_pretrained("/data/student/merged")
    vol.commit()
    return "saved /data/student/merged"


@app.function(image=gpu_image, volumes={"/data": vol}, secrets=[modal.Secret.from_name("saydo-hf")], timeout=3600)
def push_student(repo_id: str):
    """Upload the merged student to a PRIVATE Hugging Face repo so Baseten can serve it."""
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repo_id, private=True, exist_ok=True)
    api.upload_folder(folder_path="/data/student/merged", repo_id=repo_id)
    return f"pushed to {repo_id} (private)"


# ------------------------------------------------------------------------------- web API
@app.function(image=cpu_image, volumes={"/data": vol}, secrets=[meta_secret], timeout=600)
@modal.asgi_app(requires_proxy_auth=True)
def api():
    import json
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from saydo import config

    web = FastAPI(title="Say-Do API")

    def _load(n):
        return json.load(open(os.path.join(config.OUT, n)))

    @web.get("/leaderboard")
    def leaderboard():
        s = _load("scores.json")
        return {"asof": s["asof"], "base_rate": s["base_rate"],
                "companies": [{k: c[k] for k in ("ticker", "score", "grade", "ci80", "n", "ghost_rate",
                                                 "goalpost_moves", "revenue_delivery_ratio")} for c in s["companies"]]}

    @web.get("/company/{ticker}")
    def company(ticker: str):
        s = {c["ticker"]: c for c in _load("scores.json")["companies"]}
        if ticker.upper() not in s:
            raise HTTPException(404, "unknown ticker")
        ledger = [p for p in _load("resolved.json") if p["ticker"] == ticker.upper()]
        return {"score": s[ticker.upper()], "ledger": ledger}

    class Call(BaseModel):
        ticker: str
        text: str
        call_date: str | None = None

    @web.post("/analyze")
    def analyze(c: Call):
        from datetime import date
        from saydo import live
        d = date.fromisoformat(c.call_date) if c.call_date else None
        r = live.analyze(c.ticker, c.text, d)
        r.pop("open_from_before", None)
        return r

    return web
