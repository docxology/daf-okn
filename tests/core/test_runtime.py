#!/usr/bin/env python3
"""Tests for shared runtime helpers (project root, logging, figure data)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from daf_okn.core import project_paths
from daf_okn.core._runtime import get_logger, project_root, save_figure_data


def _expected_default_root() -> Path:
    """The repo root implied by the project_paths module location."""
    return Path(project_paths.__file__).resolve().parent.parent.parent.parent


def test_project_root_returns_default_repo_root() -> None:
    """``project_root`` resolves to the repository root that contains src/."""
    assert project_root("src") == _expected_default_root()


def test_get_logger_returns_named_logger() -> None:
    """``get_logger`` returns a standard library logger for the given name."""
    logger = get_logger("daf_okn.tests.test_runtime")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "daf_okn.tests.test_runtime"
    assert get_logger("daf_okn.tests.test_runtime") is logger


def test_get_logger_defaults_to_module_name() -> None:
    """Without a name the helper logs under its own module path."""
    assert get_logger().name == "daf_okn.core._runtime"


def test_save_figure_data_writes_json_below_output_dir(tmp_path: Path) -> None:
    """Figure data lands in ``<output_dir>/data/<name>.json`` as valid JSON."""
    data = {"name": "demo", "count": 3, "ratio": 0.5}
    path = save_figure_data(data, "demo", tmp_path)
    assert path == tmp_path / "data" / "demo.json"
    assert json.loads(path.read_text(encoding="utf-8")) == data


def test_save_figure_data_stringifies_unserialisable_values(tmp_path: Path) -> None:
    """``default=str`` keeps non-JSON values from raising."""
    marker = tmp_path / "raw.bin"
    path = save_figure_data({"marker": marker}, "raw", tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"marker": str(marker)}


def test_save_figure_data_creates_nested_output_dir(tmp_path: Path) -> None:
    """Missing parents in ``output_dir`` are created on demand."""
    out_dir = tmp_path / "deep" / "nested"
    path = save_figure_data({"ok": True}, "flag", out_dir)
    assert path == out_dir / "data" / "flag.json"
    assert path.is_file()
