"""Freeze the installed application/test dependency closure, excluding unrelated tools."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import tomllib

root = Path(__file__).resolve().parents[1]
project = tomllib.loads((root/"pyproject.toml").read_text())["project"]
queue = list(project["dependencies"]) + project["optional-dependencies"]["test"]
seen, locked = set(), {}
while queue:
    req = Requirement(queue.pop())
    name = canonicalize_name(req.name)
    key = (name, tuple(sorted(req.extras)))
    if key in seen:
        continue
    seen.add(key)
    dist = distribution(req.name)
    locked[name] = dist.version
    for dep in dist.requires or []:
        parsed = Requirement(dep)
        if parsed.marker is None or any(parsed.marker.evaluate({"extra": x}) for x in (req.extras or {""})):
            queue.append(dep)
(root/"requirements.lock").write_text("# Python 3.12; resolved application + test dependencies.\n" +
    "\n".join(f"{name}=={version}" for name,version in sorted(locked.items()))+"\n",encoding="utf-8")
print(f"Locked {len(locked)} packages.")
