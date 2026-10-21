# Scientific contract

The implementation is original, narrow NumPy Monte Carlo code validated against independently expressed analytic formulas and fixed test cases. It is not represented as an externally certified simulator. Independent scientific review remains valuable.

## Conventions

For BPSK, one bit maps to one symbol, with x in {-1,+1}; Eb=Es=1. Define gamma=10^(Eb/N0_dB / 10), so N0=1/gamma.

- AWGN: y=x+n with real n ~ N(0,N0/2). Decide 1 iff y>=0.
- Rayleigh: y=h*x+n with independent h=(a+j*b)/sqrt(2), a,b~N(0,1), per symbol. Thus E|h|²=1.
- Complex noise n has independent real/imaginary components of variance N0/2.
- Receiver knows h exactly and decides using Re(conj(h)*y)>=0. This avoids division by a near-zero fading coefficient.
- No coding, synchronization error, channel-estimation error, Doppler correlation, block fading, antenna diversity or interference.

Theoretical AWGN BER is 0.5 erfc(sqrt(gamma)). Under the stated coherent Rayleigh assumptions, average BER is 0.5(1-sqrt(gamma/(1+gamma))). The theoretical functions do not inspect the sampled received signal or empirical error count. For a derivation of Rayleigh BER, see [the research paper on a unified derivation](https://arxiv.org/abs/2406.16548). Uploaded documents never override these validated implementation assumptions.

## Sampling and uncertainty

Every SNR point receives a fixed configured bit count. Counts are not terminated after a target number of errors, so standard fixed-sample binomial intervals apply. The result stores errors, bits, BER and exact two-sided Clopper-Pearson 95% intervals.

Zero errors yields BER estimate 0 but a positive confidence upper bound. Interactive and exported logarithmic plots render that upper bound separately. They do not replace zero with a made-up positive measured BER.

The theory rule uses a 1% familywise significance level with Bonferroni correction over sweep points. This intentionally differs from the displayed marginal 95% intervals. A warning means statistical inconsistency worth investigating, not proof of a normalization bug. The sample-adequacy rule flags fewer than 30 errors as a precision caution; it is not a hypothesis test.

Tests do not require pointwise monotonicity. Independent Monte Carlo samples can fluctuate. The comparison view reports changed configuration fields and matched-point differences; overlapping marginal intervals are descriptive, not a dedicated paired significance test.

## Reproducibility envelope

Results record specification schema version, simulator version, seed, Python/NumPy/SciPy versions, OS/platform, PCG64 RNG and fixed batch size (65,536 bits). Within the same implementation and runtime envelope, the tests require identical error counts. Wall-clock time and SVG metadata are not expected to match byte-for-byte.

Cross-platform floating point, dependency upgrades, RNG implementation changes or changes in random draw ordering can alter samples despite equal seeds. Outside the supported envelope, compare statistical agreement and explicitly label the change. No universal seed-only reproducibility claim is made.

No automatic result cache is enabled. Submission idempotency is separate from scientific caching. A full configuration/implementation/runtime fingerprint is saved as a basis for future workspace-scoped cache eligibility.

Limits are -10 to 25 dB, 1–21 unique increasing points, 1,000–2,000,000 bits per point, at most 10 million total bits, and a cooperative 120-second simulation deadline.
