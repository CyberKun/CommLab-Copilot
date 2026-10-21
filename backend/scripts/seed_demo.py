"""Create an actual local demo, with source ingestion and measured simulation results."""
import json
from pathlib import Path
from commlab.assembly import Services
from commlab.local_worker import tick
from commlab.simulation.api import ExperimentSpec

root = Path(__file__).resolve().parents[2]
services = Services()
if services.engine.dialect.name == "sqlite":
    services.create_dev_schema()
workspace = services.workspaces.create("BPSK · AWGN vs Rayleigh")
services.knowledge.upload(workspace["id"], "synthetic-bpsk-lab.md",
                          (root/"samples/synthetic-bpsk-lab.md").read_bytes(), "seed-demo")
for channel in ["awgn", "rayleigh"]:
    services.experiments.submit(workspace["id"], ExperimentSpec(channel=channel), "demo-"+channel, "seed-demo")
for _ in range(2):
    tick(services)
inv = services.investigations.create(workspace["id"], "What assumptions does Rayleigh BPSK use?", "seed-demo")
for _ in range(3):
    tick(services)
target = Path("data/demo-credential.json")
target.write_text(json.dumps(workspace, indent=2), encoding="utf-8")
print(f"Created actual runs and source. Import credential from {target.resolve()}; keep it private.")
