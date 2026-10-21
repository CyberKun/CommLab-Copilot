"""Deterministic evaluation. No LLM judge; actual timings and outputs only."""
import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
import numpy as np
from pydantic import ValidationError
from commlab.assembly import Services
from commlab.simulation.api import ExperimentSpec, NumpyBPSK, runtime, interval
from commlab.verification.api import TheoryRule, SampleAdequacyRule, Verifier
from commlab.retrieval.api import RetrievalRequest
from commlab.local_worker import tick

ROOT = Path(__file__).resolve().parents[2]


def evaluate(split):
    cases = [c for c in json.loads((ROOT/"eval/cases.json").read_text())["cases"] if c["split"] == split]
    reports = []
    with tempfile.TemporaryDirectory() as temp:
        services = Services(f"sqlite:///{temp}/evaluation.db", f"{temp}/artifacts")
        services.create_dev_schema()
        w = services.workspaces.create("evaluation")["id"]
        source = services.knowledge.upload(w, "synthetic-bpsk-lab.md", (ROOT/"samples/synthetic-bpsk-lab.md").read_bytes(), "evaluation")
        services.knowledge.ingest(w, source["id"])
        for case in cases:
            start = time.perf_counter()
            detail = {}
            kind = case["kind"]
            if kind in ["reference", "absent"]:
                result = services.retrieval.search(w, RetrievalRequest(query=case["query"], limit=3))
                texts = [c.text for c in result.evidence]
                passed = any(case["expected_text"] in t for t in texts) if kind == "reference" else result.insufficient_evidence
                support = all(services.knowledge.chunk(w, c.id).text == c.text for c in result.evidence)
                detail = {"retrieved_ids": [c.id for c in result.evidence], "citation_exact_text_support": support,
                          "retrieval_hit_at_3": passed if kind == "reference" else None}
            elif kind == "unsupported":
                inv = services.investigations.create(w, case["query"], "evaluation")
                tick(services)
                state = services.investigations.inspect(w, inv["id"])
                passed = not state["plans"] and state["status"] == "finished" and bool(state["answer"]["unresolved_questions"])
            elif kind == "simulation":
                spec = ExperimentSpec(channel=case["channel"], seed=case["seed"], ebn0_db=[0,4,8], bits_per_point=100_000)
                result = NumpyBPSK().execute(spec, lambda _: None)
                findings = Verifier([TheoryRule()]).check(result)
                repeated = NumpyBPSK().execute(spec, lambda _: None)
                passed = result.points == repeated.points and all(f["severity"] == "info" for f in findings)
                detail = {"exact_repeat": result.points == repeated.points, "false_alarm": any(f["severity"] == "warning" for f in findings),
                          "points": [p.model_dump() for p in result.points]}
            elif kind == "normalization_fault":
                # Evaluation-only independently injected bug. NOT an available production capability.
                result = NumpyBPSK().execute(ExperimentSpec(ebn0_db=[0], bits_per_point=100_000, seed=case["seed"]), lambda _: None)
                rng = np.random.default_rng(case["seed"])
                symbols = 2*rng.integers(0,2,100_000)-1
                wrong = symbols + rng.normal(0, 1, 100_000)  # WRONG: N0, instead of N0/2, at 0 dB.
                p = result.points[0]
                p.errors = int(np.count_nonzero((wrong>=0) != (symbols>=0)))
                p.ber = p.errors/p.bits
                p.ci_low, p.ci_high = interval(p.errors,p.bits)
                findings = Verifier([TheoryRule()]).check(result)
                passed = findings[0]["severity"] == "warning"
                detail = {"fault_detected": passed, "diagnosis_scope": "Detects inconsistency; does not uniquely identify its cause."}
            elif kind == "insufficient_sample":
                result = NumpyBPSK().execute(ExperimentSpec(ebn0_db=[25],bits_per_point=1000),lambda _:None)
                findings = Verifier([SampleAdequacyRule()]).check(result)
                passed = bool(findings) and result.points[0].ci_high > 0
                detail = {"upper_95": result.points[0].ci_high, "errors":result.points[0].errors}
            elif kind == "multiple_changes":
                a = services.experiments.submit(w, ExperimentSpec(), "a", "eval")
                b = services.experiments.submit(w, ExperimentSpec(channel="rayleigh", seed=99), "b", "eval")
                comparison = services.experiments.compare(w,a.id,b.id)
                passed = len(comparison["changes"]) == 2 and "does not isolate" in comparison["interpretation"]
            elif kind == "conflicting_sources":
                conflict = services.knowledge.upload(w, "synthetic-conflicting-note.md", (ROOT/"samples/synthetic-conflicting-note.md").read_bytes(), "evaluation")
                services.knowledge.ingest(w, conflict["id"])
                result = services.retrieval.search(w, RetrievalRequest(query=case["query"],limit=5))
                versions = {c.source.version_id for c in result.evidence}
                passed = source["id"] in versions and conflict["id"] in versions
                detail = {"both_sources_retrieved": passed, "automatic_conflict_resolution": False}
            elif kind == "invalid_spec":
                try:
                    ExperimentSpec.model_validate(case["spec"])
                    passed = False
                except ValidationError:
                    passed = True
            reports.append({"id":case["id"],"kind":kind,"passed":passed,"seconds":time.perf_counter()-start,**detail})
        services.engine.dispose()
    refs = [r for r in reports if r["kind"]=="reference"]
    simulations = [r for r in reports if r["kind"]=="simulation"]
    return {"schema_version":1, "split":split,"mode":"offline_rules_and_lexical_hash","runtime":runtime(),
        "cases": reports, "metrics": {
            "passed":sum(r["passed"] for r in reports), "total":len(reports),
            "retrieval_hit_at_3":statistics.mean(r["retrieval_hit_at_3"] for r in refs) if refs else None,
            "citation_exact_text_support":all(r["citation_exact_text_support"] for r in refs),
            "reproducibility_exact":all(r["exact_repeat"] for r in simulations),
            "false_alarm_rate":statistics.mean(r["false_alarm"] for r in simulations) if simulations else None,
            "case_latency_median_seconds":statistics.median(r["seconds"] for r in reports),
            "model_cost_usd":None, "diagnosis_accuracy":None},
        "limits":["Tiny synthetic set; not a benchmark of real handouts.",
                  "Citation metric checks exact stored text, not semantic entailment.",
                  "Fault detection does not establish root-cause diagnosis accuracy.",
                  "No LLM baseline or RAG-only LLM scores without a live provider."],
        "model_comparison":{"basic_llm":"not_run_provider_unavailable","rag_only_llm":"not_run_provider_unavailable",
                            "complete_tool_workflow":"deterministic offline mode tested; live LLM comparison pending"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["calibration","heldout"], default="heldout")
    args = parser.parse_args()
    result = evaluate(args.split)
    path = ROOT / "eval" / f"results-{args.split}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2))
    print(path)
