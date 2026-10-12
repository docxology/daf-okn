#!/usr/bin/env python3
"""Tests for project root resolution and standard output directories."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from daf_okn.core import project_paths
from daf_okn.core.project_paths import (
    project_output_dirs,
    project_root_context,
    resolve_project_root,
)


def _expected_default_root() -> Path:
    """The repo root implied by the project_paths module location."""
    return Path(project_paths.__file__).resolve().parent.parent.parent.parent


def test_resolve_project_root_defaults_to_repo_root() -> None:
    """Without an override or module hint the resolver walks up from src/."""
    assert resolve_project_root("daf_okn") == _expected_default_root()
    assert resolve_project_root("no-such-module-name") == _expected_default_root()


def test_resolve_project_root_uses_module_attribute(monkeypatch) -> None:
    """A package exposing ``project_root`` routes resolution to that path."""
    fake = types.ModuleType("fake_okn_package")
    fake.project_root = "/tmp/fake-okn-root"
    monkeypatch.setitem(sys.modules, "fake_okn_package", fake)
    assert resolve_project_root("fake_okn_package") == Path("/tmp/fake-okn-root")


def test_resolve_project_root_ignores_module_without_attribute(monkeypatch) -> None:
    """A package without ``project_root`` falls through to the default root."""
    bare = types.ModuleType("fake_bare_package")
    monkeypatch.setitem(sys.modules, "fake_bare_package", bare)
    assert resolve_project_root("fake_bare_package") == _expected_default_root()


def test_project_root_context_routes_and_restores(tmp_path: Path, monkeypatch) -> None:
    """Inside the context every lookup returns the temporary root; it restores."""
    fake = types.ModuleType("fake_okn_package_ctx")
    fake.project_root = "/tmp/other-root"
    monkeypatch.setitem(sys.modules, "fake_okn_package_ctx", fake)

    before = resolve_project_root("daf_okn")
    with project_root_context(tmp_path) as routed:
        assert routed == tmp_path.resolve()
        assert resolve_project_root("daf_okn") == tmp_path.resolve()
        assert resolve_project_root("anything-else") == tmp_path.resolve()
        # the explicit override wins even when a module hint is registered
        assert resolve_project_root("fake_okn_package_ctx") == tmp_path.resolve()
    after = resolve_project_root("daf_okn")
    assert before == after == _expected_default_root()


def test_project_output_dirs_explicit_and_default_roots(tmp_path: Path) -> None:
    """Output directories hang off the given root; default root used otherwise."""
    dirs = project_output_dirs(tmp_path)
    assert set(dirs) == {"output", "figures", "data", "reports", "web"}
    assert dirs["output"] == tmp_path / "output"
    assert dirs["figures"] == tmp_path / "output" / "figures"
    assert dirs["data"] == tmp_path / "output" / "data"
    assert dirs["reports"] == tmp_path / "output" / "reports"
    assert dirs["web"] == tmp_path / "output" / "web"

    default_dirs = project_output_dirs()
    assert default_dirs["output"] == _expected_default_root() / "output"
