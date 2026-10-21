import ast
from pathlib import Path

MODULES = {"artifacts", "experiments", "investigations", "knowledge", "retrieval", "simulation", "verification", "workspaces"}
ALLOWED = {
    "artifacts": set(), "workspaces": set(), "simulation": set(),
    "experiments": {"simulation"}, "verification": {"simulation"},
    "knowledge": set(), "retrieval": {"knowledge"},
    "investigations": {"retrieval", "simulation", "knowledge", "verification"},
}


def test_modules_only_import_public_interfaces_and_declared_dependencies():
    root = Path(__file__).resolve().parents[1] / "commlab"
    for module in MODULES:
        for file in (root / module).glob("*.py"):
            for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
                imports = [node.module] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names] if isinstance(node, ast.Import) else []
                for name in imports:
                    parts = (name or "").split(".")
                    if len(parts) >= 2 and parts[0] == "commlab" and parts[1] in MODULES and parts[1] != module:
                        assert parts[1] in ALLOWED[module], (file, name)
                        assert len(parts) == 3 and parts[2] == "api", (file, name)
                        if isinstance(node, ast.ImportFrom):
                            forbidden = {"Run", "Investigation", "Artifact", "Workspace", "SourceVersion", "Chunk", "Base"}
                            assert not any(n.name in forbidden or n.name.startswith("_") for n in node.names), (file, name)
