import platform
import time
import math
from collections.abc import Callable
from typing import Literal, Protocol
import numpy as np
import scipy
from pydantic import Field, model_validator
from scipy.special import erfc
from scipy.stats import beta
from commlab.common import Contract, DomainError

IMPLEMENTATION = "numpy-bpsk/1.0.0"
ASSUMPTIONS = [
    "Uncoded coherent BPSK; Eb = Es = 1; Eb/N0 in dB.",
    "AWGN: real noise variance N0/2.",
    "Rayleigh: independent CN(0,1) per symbol, E[|h|^2]=1.",
    "Rayleigh: perfect receiver CSI; decision Re(conj(h)*y) >= 0.",
    "Complex AWGN: each component has variance N0/2.",
    "Fixed sample count per SNR; no optional stopping.",
]


class ExperimentSpec(Contract):
    schema_version: Literal[1] = 1
    capability: Literal["bpsk.ber"] = "bpsk.ber"
    channel: Literal["awgn", "rayleigh"] = "awgn"
    ebn0_db: list[float] = Field(default_factory=lambda: [0, 2, 4, 6, 8], min_length=1, max_length=21)
    bits_per_point: int = Field(default=100_000, ge=1000, le=2_000_000)
    seed: int = Field(default=42, ge=0, le=2**32-1)
    receiver: Literal["coherent_perfect_csi"] = "coherent_perfect_csi"
    bit_energy: Literal[1.0] = 1.0
    noise_convention: Literal["N0/2_per_real_component"] = "N0/2_per_real_component"

    @model_validator(mode="after")
    def limits(self):
        if any(not np.isfinite(x) or x < -10 or x > 25 for x in self.ebn0_db):
            raise ValueError("Eb/N0 must be finite and between -10 and 25 dB.")
        if sorted(set(self.ebn0_db)) != self.ebn0_db:
            raise ValueError("Eb/N0 points must be unique and increasing.")
        if self.bits_per_point * len(self.ebn0_db) > 10_000_000:
            raise ValueError("Maximum work is 10 million bits per run.")
        return self


class Point(Contract):
    ebn0_db: float = Field(allow_inf_nan=False)
    errors: int = Field(ge=0)
    bits: int = Field(gt=0)
    ber: float = Field(ge=0, le=1, allow_inf_nan=False)
    theory: float = Field(ge=0, le=1, allow_inf_nan=False)
    ci_low: float = Field(ge=0, le=1, allow_inf_nan=False)
    ci_high: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def counts_and_bounds(self):
        if self.errors > self.bits or not math.isclose(self.ber, self.errors/self.bits, rel_tol=1e-12, abs_tol=1e-15):
            raise ValueError("BER must equal errors/bits, with 0 <= errors <= bits.")
        if not self.ci_low <= self.ber <= self.ci_high:
            raise ValueError("Confidence bounds must contain the measured BER.")
        return self


class SimulationResult(Contract):
    schema_version: Literal[1] = 1
    implementation: str
    spec: ExperimentSpec
    points: list[Point]
    assumptions: list[str]
    runtime: dict[str, str]
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    confidence: Literal[0.95] = 0.95

    @model_validator(mode="after")
    def matches_spec(self):
        if [p.ebn0_db for p in self.points] != self.spec.ebn0_db:
            raise ValueError("Result points must match the configured Eb/N0 sweep.")
        if any(p.bits != self.spec.bits_per_point for p in self.points):
            raise ValueError("Each result point must contain the configured bit count.")
        return self


def theory(channel: str, ebn0_db: float) -> float:
    """Analytic formulas, independent of Monte Carlo implementation."""
    gamma = 10 ** (ebn0_db / 10)
    if channel == "awgn":
        return float(0.5 * erfc(np.sqrt(gamma)))
    if channel == "rayleigh":
        return float(0.5 * (1 - np.sqrt(gamma / (1 + gamma))))
    raise DomainError("unsupported_channel", channel)


def interval(errors: int, bits: int, alpha: float = 0.05):
    """Two-sided exact Clopper-Pearson interval; valid for zero errors."""
    return (0.0 if errors == 0 else float(beta.ppf(alpha/2, errors, bits-errors+1)),
            1.0 if errors == bits else float(beta.ppf(1-alpha/2, errors+1, bits-errors)))


def runtime():
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(), "rng": "PCG64", "batch_bits": "65536"}


class Simulator(Protocol):
    def execute(self, spec: ExperimentSpec, progress: Callable[[float], None]) -> SimulationResult: ...


class NumpyBPSK:
    def execute(self, spec, progress):
        start = time.monotonic()
        rng = np.random.Generator(np.random.PCG64(spec.seed))
        points = []
        for index, snr in enumerate(spec.ebn0_db):
            errors = done = 0
            sigma = np.sqrt(1 / (2 * 10 ** (snr / 10)))
            while done < spec.bits_per_point:
                if time.monotonic() - start > 120:
                    raise DomainError("execution_timeout", "Simulation exceeded 120 seconds.")
                n = min(65_536, spec.bits_per_point - done)
                bits = rng.integers(0, 2, size=n)
                symbols = 2.0 * bits - 1.0
                if spec.channel == "awgn":
                    statistic = symbols + sigma * rng.standard_normal(n)
                else:
                    h = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
                    noise = sigma * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
                    statistic = np.real(np.conj(h) * (h * symbols + noise))
                errors += int(np.count_nonzero((statistic >= 0) != bits))
                done += n
                progress((index + done / spec.bits_per_point) / len(spec.ebn0_db))
            lo, hi = interval(errors, done)
            points.append(Point(ebn0_db=snr, errors=errors, bits=done, ber=errors/done,
                                theory=theory(spec.channel, snr), ci_low=lo, ci_high=hi))
        return SimulationResult(implementation=IMPLEMENTATION, spec=spec, points=points,
                                assumptions=ASSUMPTIONS, runtime=runtime(), elapsed_seconds=time.monotonic()-start)


class Capability:
    def __init__(self, backend: Simulator):
        self.backend = backend

    def describe(self):
        return {"id": "bpsk.ber", "implementation_version": IMPLEMENTATION,
                "input_schema": ExperimentSpec.model_json_schema(),
                "output_schema": SimulationResult.model_json_schema(),
                "assumptions": ASSUMPTIONS, "verification_checks": ["theory", "sample_adequacy"],
                "limits": {"total_bits": 10_000_000, "seconds": 120, "batch_bits": 65_536},
                "ui": {"title": "BPSK · BER sweep", "plot": "ber", "x_unit": "dB", "y_unit": "errors/bit"}}


def registry():
    return {"bpsk.ber": Capability(NumpyBPSK())}
