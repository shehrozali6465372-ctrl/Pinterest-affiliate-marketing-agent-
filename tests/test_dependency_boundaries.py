"""Keep test-only tooling out of the production runtime dependency set."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _requirement_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or value.startswith("-"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)", value)
        assert match is not None, f"invalid requirement line in {path.name}: {value!r}"
        names.add(match.group(1).lower().replace("_", "-"))
    return names


def test_runtime_requirements_exclude_test_and_audit_tooling():
    runtime = _requirement_names(ROOT / "requirements.txt")

    assert "pytest" not in runtime
    assert "bandit" not in runtime
    assert "pip-audit" not in runtime


def test_development_requirements_include_pytest():
    development = _requirement_names(ROOT / "requirements-dev.txt")

    assert "pytest" in development
