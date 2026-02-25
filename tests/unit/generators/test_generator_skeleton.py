import importlib.util
from pathlib import Path


def _load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    if loader is None:
        raise RuntimeError(f"No loader for {path}")
    loader.exec_module(module)
    return module


def test_generator_minimal_runs(tmp_path):
    # Skeleton test: ensure a generator module can import and expose a 'generate' function
    repo_root = Path(__file__).resolve().parents[4]
    gen_py = repo_root / "topology-tools" / "scripts" / "generators" / "generate-terraform-proxmox.py"
    if not gen_py.exists():
        # If generator not present, mark test as skipped
        import pytest

        pytest.skip("generate-terraform-proxmox.py not present")

    mod = _load_module_from_path(gen_py, "gen_module")
    assert hasattr(mod, "generate") or hasattr(mod, "main")
