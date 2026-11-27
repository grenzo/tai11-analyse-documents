"""Mesure de référence « avant » : passe les 20 questions au prototype (phase 0).

Utilise le moteur du prototype tel quel (DataQueryEngine, réglages du bloc
Groq commenté dans app.py : top_k=10, max_attempts=3) avec un fournisseur
Groq instrumenté :
- compte les appels, tokens d'entrée/sortie et latences ;
- met en cache chaque réponse LLM sur disque (même modèle + mêmes messages +
  mêmes paramètres => pas de nouvel appel) ;
- respecte les quotas gratuits (8 000 tokens/min) par une fenêtre glissante ;
- reprend après interruption (les questions déjà traitées sont sautées).

La clé est lue en mémoire (variable GROQ_API_KEY ou .streamlit/secrets.toml)
et n'est jamais affichée ni écrite.

Usage (racine du dépôt, serveur d'embeddings sur 127.0.0.1:8081) :
    python -X utf8 docs/audit/scripts/run_baseline.py [--model openai/gpt-oss-20b] [--only B01,B02]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import tomllib
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from llm.groq_provider import GroqProvider  # noqa: E402
from query_engine import DataQueryEngine  # noqa: E402

QUESTIONS = Path("docs/audit/baseline_questions.json")
RESULTS = Path("docs/audit/data/baseline_results.jsonl")
CACHE_DIR = Path("docs/audit/runs/llm_cache")
TPM_BUDGET = 7_500  # marge sous la limite gratuite de 8 000 tokens/min


def load_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    secrets = Path(".streamlit/secrets.toml")
    if not key and secrets.exists():
        key = tomllib.loads(secrets.read_text(encoding="utf-8")).get("GROQ_API_KEY", "")
    if not key:
        raise SystemExit("Clé Groq absente : définir GROQ_API_KEY ou .streamlit/secrets.toml")
    return key


class InstrumentedGroq(GroqProvider):
    """Même requête que GroqProvider.chat, avec mesures, cache et limitation de débit."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model)
        self.client.max_retries = 8  # le SDK respecte retry-after sur les 429
        self.window: deque[tuple[float, int]] = deque()
        self.reset()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        self.calls: list[dict[str, object]] = []

    def _throttle(self, estimated_tokens: int) -> None:
        while True:
            now = time.monotonic()
            while self.window and now - self.window[0][0] > 60:
                self.window.popleft()
            used = sum(tokens for _, tokens in self.window)
            if used + estimated_tokens <= TPM_BUDGET or not self.window:
                return
            time.sleep(max(1.0, 60 - (now - self.window[0][0]) + 0.5))

    def chat(self, messages, response_format=None, max_completion_tokens=1024):  # type: ignore[override]
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": max_completion_tokens,
            "include_reasoning": False,
            "reasoning_effort": "low",
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        digest = hashlib.sha256(json.dumps(kwargs, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        cached = CACHE_DIR / f"{digest}.json"
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        if cached.exists():
            entry = json.loads(cached.read_text(encoding="utf-8"))
            self.calls.append({**entry["usage"], "cached": True, "latency_s": 0.0, "prompt_chars": prompt_chars})
            return entry["content"]
        estimated = prompt_chars // 3 + max_completion_tokens // 4
        self._throttle(estimated)
        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            self.calls.append({"error": f"{type(exc).__name__}: {str(exc)[:300]}", "prompt_chars": prompt_chars,
                               "latency_s": round(time.monotonic() - start, 2)})
            raise
        latency = time.monotonic() - start
        usage = response.usage
        record = {
            "model_returned": response.model,
            "system_fingerprint": getattr(response, "system_fingerprint", None),
            "tokens_in": getattr(usage, "prompt_tokens", None),
            "tokens_out": getattr(usage, "completion_tokens", None),
        }
        self.window.append((time.monotonic(), (record["tokens_in"] or 0) + (record["tokens_out"] or 0)))
        content = response.choices[0].message.content or ""
        cached.write_text(json.dumps({"usage": record, "content": content}, ensure_ascii=False), encoding="utf-8")
        self.calls.append({**record, "cached": False, "latency_s": round(latency, 2), "prompt_chars": prompt_chars})
        return content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    done = set()
    if RESULTS.exists():
        done = {json.loads(line)["id"] for line in RESULTS.read_text(encoding="utf-8").splitlines() if line.strip()}

    llm = InstrumentedGroq(load_key(), args.model)
    engine = DataQueryEngine(llm=llm, db_path=Path("cti_defi_sections.sqlite"),
                             schema_path=Path("semantic_schema.txt"), top_k=10, max_attempts=3)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    for q in questions:
        if q["id"] in done:
            print(f"{q['id']} déjà traité, ignoré")
            continue
        llm.reset()
        start = time.monotonic()
        record: dict[str, object] = {"id": q["id"], "question": q["question"], "model": args.model,
                                     "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        try:
            result = engine.ask(q["question"])
            record.update(status="ok", answer=result["answer"], sql=result["sql"],
                          columns=result["columns"], rows=[list(r) for r in (result["rows"] or [])[:50]],
                          families=result["families"])
        except Exception as exc:
            record.update(status="error", error=f"{type(exc).__name__}: {str(exc)[:1500]}")
        record["latency_s"] = round(time.monotonic() - start, 1)
        live = [c for c in llm.calls if not c.get("cached")]
        record["llm_calls"] = len(llm.calls)
        record["tokens_in"] = sum(int(c.get("tokens_in") or 0) for c in llm.calls)
        record["tokens_out"] = sum(int(c.get("tokens_out") or 0) for c in llm.calls)
        record["max_prompt_chars"] = max((int(c.get("prompt_chars") or 0) for c in llm.calls), default=0)
        record["live_llm_latency_s"] = round(sum(float(c.get("latency_s") or 0) for c in live), 1)
        record["call_log"] = llm.calls
        with RESULTS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{q['id']} {record['status']:5s} {record['latency_s']:>6}s appels={record['llm_calls']} "
              f"tokens={record['tokens_in']}/{record['tokens_out']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
