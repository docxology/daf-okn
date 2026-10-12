"""Release-hygiene tests: one version everywhere, and nothing machine-specific is shipped."""

from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib
import yaml

import daf_okn

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {
    ".git",
    ".venv",
    "output",
    ".ruff_cache",
    ".pytest_cache",
    ".benchmarks",
    "__pycache__",
    "daf_okn.egg-info",
}


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_version_is_consistent_across_every_metadata_file() -> None:
    version = _pyproject()["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert daf_okn.__version__ == version
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["version"] == version
    codemeta = json.loads((ROOT / "codemeta.json").read_text(encoding="utf-8"))
    assert codemeta["version"] == version
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert zenodo["version"] == version
    config = yaml.safe_load((ROOT / "manuscript" / "config.yaml").read_text(encoding="utf-8"))
    assert str(config["paper"]["version"]) == version


def test_changelog_documents_the_current_version() -> None:
    version = _pyproject()["project"]["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[{re.escape(version)}\]", changelog, re.MULTILINE)


def test_license_metadata_agrees() -> None:
    assert _pyproject()["project"]["license"]["text"] == "MIT"
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["license"] == "MIT"


def test_shipped_files_contain_no_machine_specific_or_third_party_private_details() -> None:
    # Patterns are assembled from pieces so this file does not trip its own scan.
    forbidden = [
        "/" + "Volumes",
        "/" + "Users/",
        "external" + "_drive",
        "@" + "gmail",
        "kebede" + "y",
        "morshed" + "m",
    ]
    hits: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        parts = path.relative_to(ROOT).parts
        # Virtual environments (including ones set aside as .venv.*) are local, not shipped.
        if not path.is_file() or SKIP_DIRS & set(parts) or parts[0].startswith(".venv"):
            continue
        if path.name in {"uv.lock", ".coverage"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits.extend(f"{path.relative_to(ROOT)}: {token}" for token in forbidden if token in text)
    assert hits == []


def test_no_private_drafts_directory_is_shipped() -> None:
    assert not (ROOT / "drafts").exists()
