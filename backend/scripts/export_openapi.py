import json
from pathlib import Path
from commlab.http import create_app

target = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(create_app().openapi(), indent=2), encoding="utf-8")
print(target)
