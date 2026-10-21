"""Run real baseline and RAG-only model calls, and a real tool workflow.

Opt-in: LLM_MODEL must be configured. Outputs need independent human scoring.
"""
import json
import os
import tempfile
import time
from pathlib import Path
import httpx
from commlab.assembly import Services
from commlab.local_worker import tick
from commlab.retrieval.api import RetrievalRequest

ROOT = Path(__file__).resolve().parents[2]
model = os.getenv("LLM_MODEL")
if not model:
    raise SystemExit("Set LLM_MODEL and OLLAMA_URL to evaluate a real provider; no mocked scores are produced.")
url = os.getenv("OLLAMA_URL", "http://localhost:11434")
cases = json.loads((ROOT/"eval/cases.json").read_text())["cases"]
outputs = []
with tempfile.TemporaryDirectory() as temp:
    services = Services(f"sqlite:///{temp}/models.db", f"{temp}/artifacts")
    services.create_dev_schema()
    w = services.workspaces.create("model eval")["id"]
    source = services.knowledge.upload(w, "handout.md", (ROOT/"samples/synthetic-bpsk-lab.md").read_bytes(), "model-eval")
    services.knowledge.ingest(w, source["id"])
    for case in cases:
        if case["split"] != "heldout" or "query" not in case:
            continue
        evidence = services.retrieval.search(w, RetrievalRequest(query=case["query"]))
        for mode in ["basic_llm", "rag_only"]:
            started = time.perf_counter()
            prompt = {"question": case["query"]}
            if mode == "rag_only":
                prompt["untrusted_evidence"] = evidence.model_dump()
            response = httpx.post(url+"/api/chat", timeout=60, json={"model":model,"stream":False,
                "messages":[{"role":"system","content":"Answer the communication question. Cite only supplied evidence IDs. State uncertainty and missing evidence. Never claim tools were executed."},
                            {"role":"user","content":json.dumps(prompt)}],
                "options":{"temperature":0,"num_predict":1200,"num_ctx":8192}})
            response.raise_for_status()
            outputs.append({"case":case["id"],"mode":mode,"response":response.json(),"seconds":time.perf_counter()-started})
        inv = services.investigations.create(w,case["query"],"model-eval")
        started = time.perf_counter()
        for _ in range(15):
            tick(services)
            state = services.investigations.inspect(w,inv["id"])
            if state["status"] in ["finished","failed","review"]:
                break
        outputs.append({"case":case["id"],"mode":"tool_workflow","response":state,"seconds":time.perf_counter()-started})
    services.engine.dispose()
(ROOT/"eval/model-outputs.json").write_text(json.dumps({"model":model,"outputs":outputs,
    "scoring":"Pending human review using eval/rubric.md; no model-judge scores."},indent=2),encoding="utf-8")
