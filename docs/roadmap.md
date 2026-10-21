# Roadmap and interview discussion

## Evidence-based next steps

| Extension | Existing boundary | New engineering and evidence required |
|---|---|---|
| QPSK | Shared Monte Carlo structure, versioned spec/result, central registry | Correct symbol mapping and Eb/Es handling, independent BER tests, forms and theory applicability |
| Receive diversity | Channel/receiver assumptions and verification rules | MRC/selection combining primitives, antenna-normalization conventions, diversity reference checks |
| OFDM through another simulator | Simulator adapter and bounded worker jobs | Frequency-selective channel/spec, CP/FFT conventions, synchronization assumptions, new result/plot contracts and independent validation |
| Team workspaces | Workspace authorization boundary | Users, memberships, roles, token lifecycle, audit events, migrations and multi-tenant access tests |
| Stale-result detection | Source version IDs and implementation fingerprints | Explicit source-to-plan dependency graph, immutable provenance snapshots, invalidation policy and UI warnings |
| Budget-aware selection | Persisted plans, usage and simulation limits | Expected-information/cost model, calibration, stopping policy and evaluation against fixed-budget baselines |
| DSP/networking | Capability registry and structured artifacts | Domain schemas, meaningful tools, verification rules, evaluation corpora and specialized plots |
| Service extraction | Worker process boundaries and public module APIs | Profiling showing resource/scaling or security need, network contracts, distributed tracing and deployment ownership |

Near-term priorities are real PostgreSQL/Redis execution in CI, live-provider quality evaluation, independently reviewed scientific/evidence cases, team authorization and operational hardening. The current small synthetic set does not justify a reranker, a second agent, Kubernetes, a vector database service or broad domain coverage.

## Interview explanation

“I built a workspace where an assistant can retrieve a lab's assumptions, propose a typed experiment, request review, execute a supported simulator, and explain actual saved results with exact source references. The engineering contribution is the reliable bridge between language, evidence and numerical tools.

“I chose a modular monolith because the boundaries are capabilities rather than deployment units. Each module owns its tables and exposes a small API; direct calls handle ordinary work, while a transactional outbox and separate workers handle resource-heavy work.

“The hardest reliability issue is not running NumPy. It is preventing duplicate queue delivery or a stale worker from publishing conflicting results. I use idempotency keys, atomic claims and lease-fenced publication. A worker may execute more than once, but only the valid owner can publish.

“Scientific validity is separate from fluent prose. The simulator records units, assumptions, counts and runtime versions. Verification uses uncertainty-aware deterministic rules, including a positive upper bound for zero observed errors. A detected discrepancy is not automatically a diagnosed cause.

“The first extension adds a sample-adequacy verification rule without changing the simulator or UI. The change-impact table also admits where QPSK or DSP would require legitimate schema and frontend changes.

“I distinguish executed local tests from unverified infrastructure and live-model evaluation. That makes the portfolio defensible rather than a mock demo with invented metrics.”

Trade-offs to discuss: owner tokens versus real identity, exact filtered pgvector scans versus approximate indexes, extractive provenance versus fluent grounded synthesis, JSON snapshots versus specialized read models, and native development convenience versus container isolation.
