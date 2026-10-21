# Synthetic CommLab handout — v1

Provenance: authored for this repository as synthetic demonstration material, 2026-10-20. It is not an institutional handout or experimental measurement.

## BPSK and energy conventions

Uncoded coherent BPSK maps bits to real symbols -1 and +1. There is one bit per symbol, so bit energy Eb equals symbol energy Es, both normalized to 1. Eb/N0 is an energy-to-noise-density ratio. The sweep uses Eb/N0 in dB, with gamma_b = 10^(Eb/N0_dB / 10). Do not substitute linear Eb/N0 directly for its dB value.

## AWGN reference

For AWGN BPSK, the received real signal is y = x + n. The noise n has mean zero and variance N0/2 = 1/(2 gamma_b). The coherent receiver decides bit 1 when y >= 0. The theoretical probability of bit error is Pb = Q(sqrt(2 gamma_b)) = 0.5 erfc(sqrt(gamma_b)). Q is the upper-tail standard normal probability. At 0 dB, Pb is approximately 0.0786496.

## Flat Rayleigh reference

For Rayleigh BPSK, y = h x + n with independent h ~ CN(0,1) for each symbol. The average channel power E[|h|^2] equals 1. Both real and imaginary parts of h have variance 1/2. The complex additive noise has variance N0/2 per real component. With perfect receiver channel state information, decide using Re(conj(h) y) >= 0. The average theoretical BER is Pb = 0.5 (1 - sqrt(gamma_b/(1+gamma_b))). At 0 dB, Pb is approximately 0.146447. This model is flat fading and independent across symbols; it is not a Doppler-correlated block-fading model.

## Sampling and interpretation

Use a fixed bit count at each Eb/N0 point and record both error counts and total bits. Zero observed errors is not proof of zero BER. Report exact binomial confidence intervals. When multiple experiment parameters change, the difference does not isolate a single causal effect. Finite-sample variation can make neighboring measured points nonmonotonic.

## Reproducibility

The demonstration uses seed 42, Eb/N0 points 0, 2, 4, 6, 8 dB and 100000 bits per point. Repeating a seed is only meaningful with the same implementation, RNG, batch size, dependency versions, and supported runtime environment.
