# Change impact and extension guide

The objective is localized, understandable change. The current registry is intentionally small. A genuinely new scientific input or output legitimately touches contracts and UI boundaries.

| Change | Owning modules and integration points | Contract / migration impact | Required tests | Should remain untouched |
|---|---|---|---|---|
| Add QPSK | Simulation primitives/registry, verification theory; configuration form; assembly only if adapter changes | Extend/version ExperimentSpec; bit/symbol energy and mapping assumptions. Usually no table migration if JSON and existing query columns suffice | Gray mapping, Eb/Es convention, AWGN/Rayleigh theory, backend contract, UI form | Knowledge, retrieval, workspaces, artifact storage, job transport |
| New channel model | Simulation channel primitive, capability metadata, applicable verification rules, form choices | Channel schema and assumptions; add query metadata if needed | Channel normalization, CSI, analytical/independent reference, resource bounds | Ingestion, retrieval strategy, authorization, outbox |
| Verification rule | Verification rule and assembly registration | Finding stays stable for existing severity/output shape; no migration | Known-positive/negative and uncertainty cases | Simulator, ingestion, queue, artifact store, frontend for ordinary findings |
| Replace LLM | Investigations provider adapter plus assembly/env configuration | LLMProvider/Decision remain stable if tools and usage fit; no migration | Structured decisions, errors, budget/usage accounting, live evaluation | Simulation, verification, source parsing, run schema, plots |
| Local to object storage | Artifacts BlobStore adapter plus assembly | ArtifactRef can remain stable; migrate existing blob keys/content operationally, add locator fields only if necessary | Isolation, atomic uploads, retries/checksums, interrupted upload, downloads | Numerical engine, retrieval ranking, agent plan logic |
| Retrieval strategy | Retrieval strategy implementation and assembly | Existing request/result can remain stable; new index/model may require reindex/migration | Relevance/abstention, source-version and workspace isolation, latency | Simulation, experiments, job state machine, storage adapter |
| DSP domain adapter | New domain capability and result contracts, registry, verification and forms/plots; investigator capability context | New discriminated spec/result union; possible query read-model columns/migration | Numerical reference, resource limits, contract, cross-domain authorization, end-to-end workflow | Artifact persistence, workspace access, ingestion transport, outbox mechanics |
| New visualization | Frontend chart component/registry; Experiments private renderer if export needed | Reuse result shape when sufficient; new output contract otherwise; nullable artifact field or generic artifact collection may need migration | Units/axes, zero/negative values, uncertainty, export integrity, UI selection | LLM provider, reference retrieval, numerical backend unless output is missing |

## Implemented small extension

`SampleAdequacyRule` implements the public `Rule.check(SimulationResult) → list[Finding]` protocol. The application registers it alongside `TheoryRule`. The simulator remains unchanged; the existing findings UI renders its warning automatically. `test_public_verification_extension` verifies the extension against a genuine zero-error simulation and positive confidence upper bound.

This exercises a real replacement boundary without creating a plugin marketplace. For another finding:

```python
from commlab.verification.api import Finding

class MyRule:
    def check(self, result):
        # Derive conditions only from validated numerical output.
        return [Finding(rule="my_rule", version="1", severity="info",
                        message="A precisely defined, tested finding.")]
# assembly.py: Verifier([TheoryRule(), SampleAdequacyRule(), MyRule()])
```

Do not add a new service, HTTP hop or event topic for this change.

## Add a simulation capability

1. Define scientifically explicit typed inputs and outputs; keep persisted v1 readers.
2. Implement a backend through the Simulator boundary, preserving progress/cancellation callbacks and bounded work.
3. Register its identifier/version, schemas, assumptions, checks, resource limits and UI metadata in the central registry.
4. Add independent numerical/analytic tests and negative validation cases.
5. Extend the spec/result union and query fields only when needed. Do not scatter capability ID checks through transport or worker code.
6. Reuse the BER form/plot for compatible data. Introduce a dedicated component for a qualitatively different visualization.
7. Update the agent's supported-capability context and evaluation cases. The current BPSK-specific prompt/form are identified extension points, not a claim of fully generic domain loading.

Queue execution already resolves the backend from the registry. Capability declarations describe current schemas and limits; a future DSP domain requires real schema and UI work.
