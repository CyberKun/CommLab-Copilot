# Evaluation protocol

The fixed cases are author-reviewed against the synthetic source and analytic formulas. Independent ECE/expert review is still required before describing this as an externally reviewed benchmark. Calibration and held-out IDs are disjoint. Do not adjust implementation thresholds using held-out outcomes and continue calling them held out; create a new test set if you do.

`results-*.json` records actual offline measurements, runtime versions and limitations. Each run overwrites that split's report intentionally. `evaluate_models.py` requires a configured real Ollama model and emits raw responses for all three modes; it never substitutes deterministic results for a model baseline. The live tool evaluation stops at review for execution plans. A human evaluator must approve the intended configuration, or an explicitly predefined experiment fixture must do so, before measuring tool-completed experiment answers.

For each real-model response, two reviewers should independently score:

| Metric | Rule |
|---|---|
| Retrieval relevance | Relevant chunks / retrieved chunks, plus hit@3 on predefined supporting spans |
| Citation support | Fraction of factual claims entailed by the cited source; exact text matching alone is insufficient |
| Diagnosis accuracy | Correct supported cause or correct abstention, with plausible alternatives preserved |
| False alarms | Correct simulations incorrectly flagged, using a larger independent set of seeds |
| Abstention | Missing/contradictory evidence disclosed rather than filled in |
| Reproducibility | Exact error counts within the pinned envelope; compatible confidence intervals outside it |
| Latency | Ingestion, retrieval, model, queue wait, simulation, and end-to-end times separately |
| Cost | Actual token counts times an explicitly configured price schedule; unknown is null |

Disagreements should be adjudicated and retained. Do not use only LLM judges. Do not report percentages from two scientific runs as reliable population estimates. The injected normalization fault tests inconsistency detection, not unique root-cause identification. Conflicting-source retrieval tests visibility of both claims, not reliable automatic reconciliation.
