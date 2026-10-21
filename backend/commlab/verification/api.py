from typing import Literal, Protocol
from commlab.common import Contract
from commlab.simulation.api import SimulationResult, interval, theory


class Finding(Contract):
    rule: str
    version: str = "1"
    severity: Literal["info", "warning", "error"]
    message: str
    points_db: list[float] = []


class Rule(Protocol):
    def check(self, result: SimulationResult) -> list[Finding]: ...


class TheoryRule:
    def check(self, result):
        # Familywise false alarm probability <= 1%, across all sweep points.
        bad = []
        for p in result.points:
            lo, hi = interval(p.errors, p.bits, alpha=0.01 / len(result.points))
            if not lo <= theory(result.spec.channel, p.ebn0_db) <= hi:
                bad.append(p.ebn0_db)
        return [Finding(rule="theory", severity="warning" if bad else "info", points_db=bad,
                        message="Theory falls outside 99% familywise exact intervals; investigate assumptions, implementation, or sampling." if bad
                        else "No theory inconsistency detected at a 1% familywise significance level; this does not prove correctness.")]


class SampleAdequacyRule:
    """Small extension through the public Rule interface; no simulator changes."""
    def check(self, result):
        low = [p.ebn0_db for p in result.points if p.errors < 30]
        return [Finding(rule="sample_adequacy", severity="warning", points_db=low,
                        message="Fewer than 30 observed errors at these points. Use confidence bounds; zero errors does not establish zero BER.")] if low else []


class Verifier:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def check(self, result: SimulationResult):
        return [f.model_dump() for rule in self.rules for f in rule.check(result)]
