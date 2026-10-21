"""Exercise real hosted APIs with synthetic data; save credentials only in ignored data/.

Run from backend: python scripts/smoke_hosted.py https://commlab-copilot.vercel.app
Creates a demo workspace and a second workspace for isolation checks.
"""
import json
import sys
import time
from pathlib import Path
import httpx


def main():
    base = sys.argv[1].rstrip("/")
    started = time.monotonic()
    with httpx.Client(base_url=base, timeout=90) as client:
        def call(method, path, **kwargs):
            r = client.request(method, path, **kwargs)
            r.raise_for_status()
            return r.json()

        assert call("GET", "/health")["status"] == "ok"
        workspace = call("POST", "/api/workspaces", json={"name": "Hosted demonstration"})
        Path("data").mkdir(exist_ok=True)
        Path("data/hosted-demo-credential.json").write_text(json.dumps(workspace), encoding="utf-8")
        prefix = f"/api/workspaces/{workspace['id']}"
        headers = {"Authorization": f"Bearer {workspace['token']}"}

        def scoped(method, path, **kwargs):
            return call(method, prefix + path, headers=headers, **kwargs)

        def wait(path, terminal, limit=240):
            deadline = time.monotonic() + limit
            while time.monotonic() < deadline:
                value = scoped("GET", path)
                if value["status"] in terminal:
                    return value
                time.sleep(3)
            raise TimeoutError(f"Timed out waiting for {path}")

        content = (Path(__file__).resolve().parents[2] / "samples/synthetic-bpsk-lab.md").read_bytes()
        source = scoped("POST", "/sources", files={"file": ("synthetic-bpsk-lab.md", content, "text/markdown")})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            sources = scoped("GET", "/sources")
            source = next(s for s in sources if s["id"] == source["id"])
            if source["status"] in {"ready", "failed"}:
                break
            time.sleep(3)
        assert source["status"] == "ready", source
        evidence = scoped("POST", "/search", json={"query": "BPSK perfect receiver channel knowledge"})
        assert evidence["evidence"]
        chunk = evidence["evidence"][0]
        assert scoped("GET", f"/evidence/{chunk['id']}")["text"] == chunk["text"]
        print("Source ingestion, hybrid retrieval and exact citation: passed", flush=True)

        investigation = scoped("POST", "/investigations", json={"question": "Compare BPSK over AWGN and Rayleigh using this handout. Check consistency with theory."})
        path = f"/investigations/{investigation['id']}"
        review = wait(path, {"review", "failed", "finished"})
        assert review["status"] == "review" and len(review["plans"]) == 2, review
        specs = [{**p, "ebn0_db": [0, 4, 8], "bits_per_point": 100000, "seed": 42} for p in review["plans"]]
        scoped("POST", path + "/approve", json={"specs": specs})
        done = wait(path, {"finished", "failed"})
        assert done["status"] == "finished", done
        runs = [scoped("GET", f"/runs/{ident}") for ident in done["run_ids"]]
        assert len(runs) == 2 and all(r["status"] == "succeeded" for r in runs)
        comparison = scoped("POST", "/compare", json={"left": runs[0]["id"], "right": runs[1]["id"]})
        for run in runs:
            result = scoped("GET", f"/artifacts/{run['artifact_id']}")
            assert result["points"] == run["result"]["points"]
            plot = client.get(prefix + f"/artifacts/{run['plot_artifact_id']}", headers=headers)
            assert plot.status_code == 200 and b"<svg" in plot.content
        print("Reviewed plan, two queued simulations, comparison and JSON/SVG downloads: passed", flush=True)
        other = call("POST", "/api/workspaces", json={"name": "Isolation verification"})
        denied = client.get(f"/api/workspaces/{other['id']}/artifacts/{runs[0]['artifact_id']}",
                            headers={"Authorization": f"Bearer {other['token']}"})
        assert denied.status_code == 404
        assert client.get(prefix + "/runs").status_code == 404
        report = {"base_url": base, "workspace_id": workspace["id"], "investigation_id": done["id"],
                  "run_ids": done["run_ids"], "source_id": source["id"], "checks": ["ingestion", "retrieval", "citation", "review", "simulation", "comparison", "artifacts", "isolation"],
                  "elapsed_seconds": round(time.monotonic()-started, 2),
                  "runs": [{"id": r["id"], "channel": r["spec"]["channel"], "points": r["result"]["points"]} for r in runs]}
        Path("data/hosted-smoke-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"All hosted checks passed in {report['elapsed_seconds']} seconds. Private workspace credential saved in data/.", flush=True)


if __name__ == "__main__":
    main()
