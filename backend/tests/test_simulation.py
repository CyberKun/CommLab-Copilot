import pytest
from pydantic import ValidationError
from commlab.simulation.api import ExperimentSpec, NumpyBPSK, SimulationResult, interval, theory
from commlab.verification.api import Verifier, TheoryRule, SampleAdequacyRule


def test_known_theory_values():
    assert theory("awgn", 0) == pytest.approx(0.07864960352514257)
    assert theory("rayleigh", 0) == pytest.approx(0.1464466094067262)
    assert interval(0, 1000)[1] > 0


@pytest.mark.parametrize("channel", ["awgn", "rayleigh"])
def test_simulator_contract_and_theory(channel):
    spec = ExperimentSpec(channel=channel, bits_per_point=200_000, ebn0_db=[0, 4, 8])
    progress = []
    result = NumpyBPSK().execute(spec, progress.append)
    SimulationResult.model_validate_json(result.model_dump_json())
    assert progress[-1] == 1
    assert all(p.bits == spec.bits_per_point for p in result.points)
    assert all(f["severity"] != "warning" for f in Verifier([TheoryRule()]).check(result))
    repeated = NumpyBPSK().execute(spec, lambda _: None)
    assert result.points == repeated.points


@pytest.mark.parametrize("params", [
    {"ebn0_db": [float("nan")]}, {"ebn0_db": [2, 0]}, {"bits_per_point": 0},
    {"receiver": "noncoherent"}, {"bit_energy": 2}, {"channel": "rician"},
    {"ebn0_db": list(range(10)), "bits_per_point": 2_000_000},
])
def test_invalid_specs(params):
    with pytest.raises(ValidationError):
        ExperimentSpec(**params)


def test_public_verification_extension():
    result = NumpyBPSK().execute(ExperimentSpec(ebn0_db=[25], bits_per_point=1000), lambda _: None)
    findings = Verifier([SampleAdequacyRule()]).check(result)
    assert findings[0]["rule"] == "sample_adequacy"
    assert result.points[0].ci_high > 0


def test_result_contract_rejects_inconsistent_counts():
    result = NumpyBPSK().execute(ExperimentSpec(ebn0_db=[0], bits_per_point=1000), lambda _: None).model_dump()
    result["points"][0]["errors"] = 1001
    with pytest.raises(ValidationError, match="BER must equal"):
        SimulationResult.model_validate(result)


def test_result_contract_rejects_missing_sweep_points():
    result = NumpyBPSK().execute(ExperimentSpec(ebn0_db=[0], bits_per_point=1000), lambda _: None).model_dump()
    result["points"] = []
    with pytest.raises(ValidationError, match="configured Eb/N0"):
        SimulationResult.model_validate(result)
