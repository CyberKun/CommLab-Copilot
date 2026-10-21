"""Portable plot artifacts. No pyplot global figure state."""
import io
from matplotlib.figure import Figure
from matplotlib.backends.backend_svg import FigureCanvasSVG
from commlab.simulation.api import SimulationResult


def render_ber(result: SimulationResult) -> bytes:
    figure = Figure(figsize=(8, 5), layout="constrained")
    axis = figure.subplots()
    points = result.points
    axis.semilogy([p.ebn0_db for p in points], [p.theory for p in points], "--", label="Analytic theory", color="#d97706")
    nonzero = [p for p in points if p.errors]
    if nonzero:
        axis.errorbar([p.ebn0_db for p in nonzero], [p.ber for p in nonzero],
                      yerr=[[p.ber-p.ci_low for p in nonzero], [p.ci_high-p.ber for p in nonzero]],
                      fmt="o-", capsize=4, label="Measured BER (exact 95% intervals)", color="#0d9488")
    zero = [p for p in points if not p.errors]
    if zero:
        axis.scatter([p.ebn0_db for p in zero], [p.ci_high for p in zero], marker="v", color="#0d9488", label="Zero errors: 95% upper bound")
    axis.set(xlabel="Eb/N0 (dB)", ylabel="Bit error rate (errors / bit)",
             title=f"Coherent BPSK / {result.spec.channel.upper()} / seed {result.spec.seed}")
    axis.grid(True, which="both", alpha=.2)
    axis.legend(fontsize=8)
    figure.text(.5, .005, "Eb = Es = 1. Rayleigh: iid CN(0,1), perfect receiver CSI. Zero errors do not imply zero BER.", ha="center", fontsize=7)
    output = io.BytesIO()
    FigureCanvasSVG(figure).print_svg(output)
    return output.getvalue()
