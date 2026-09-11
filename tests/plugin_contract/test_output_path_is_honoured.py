"""An explicitly requested output file must be written, or the request refused.

`--diagnostics` is the compiler's master switch for writing files: without it
`_write_diagnostics` returns early and `artifact_owner("effective_json")`
resolves to "disabled". That is a defensible design. The indefensible part was
the silence - an explicit `--output-json` was accepted, ignored, and the compile
still exited 0, so a caller had a path, a zero exit status and no file.

It cost three separate debugging sessions here: the netmodel snapshot task,
`test_session_compile_fixture.py`, and the nine errors in `tests/plugin_regression`,
each asking for a file by path and getting none. These tests pin both halves of
the fix: an explicit path enables writing, and the default paths do not, because
they are present on every invocation and treating them as a request would make
the flag meaningless.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"


def _compile(workdir: Path, *extra: str) -> subprocess.CompletedProcess:
    workdir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            str(COMPILER),
            "--topology",
            "topology/topology.yaml",
            "--secrets-mode",
            "passthrough",
            "--stages",
            "discover,compile",
            *extra,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_an_explicit_diagnostics_path_is_written_without_the_flag(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-artifacts" / f"outpath-{tmp_path.name}"
    diagnostics = workdir / "diagnostics.json"

    completed = _compile(workdir, "--diagnostics-json", str(diagnostics))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert diagnostics.exists(), (
        "an explicitly requested diagnostics path was accepted and ignored; "
        "a caller with a path and a zero exit status has no way to tell"
    )


def test_the_default_paths_do_not_enable_writing(tmp_path: Path) -> None:
    """Otherwise the flag would be dead: the defaults are always present."""
    workdir = REPO_ROOT / "build" / "test-artifacts" / f"outpath-default-{tmp_path.name}"

    completed = _compile(workdir)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Diagnostics JSON:" not in completed.stdout


@pytest.mark.parametrize("option", ["--output-json", "--diagnostics-json", "--diagnostics-txt"])
def test_each_output_option_enables_writing_on_its_own(option: str, tmp_path: Path) -> None:
    """Checked at the resolution function, not by three more compiles."""
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    import argparse
    import importlib

    cli = importlib.import_module("compiler_cli")

    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--output-json", default="default/effective.json")
    parser.add_argument("--diagnostics-json", default="default/diagnostics.json")
    parser.add_argument("--diagnostics-txt", default="default/diagnostics.txt")

    defaults = parser.parse_args([])
    assert cli._diagnostics_enabled(parser, defaults) is False

    explicit = parser.parse_args([option, "somewhere/else.json"])
    assert cli._diagnostics_enabled(parser, explicit) is True


def test_the_flag_still_enables_everything_by_itself() -> None:
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    import argparse
    import importlib

    cli = importlib.import_module("compiler_cli")
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--output-json", default="default/effective.json")

    assert cli._diagnostics_enabled(parser, parser.parse_args(["--diagnostics"])) is True
