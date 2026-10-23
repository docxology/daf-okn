"""Current document/topic reports and byte-preserved historical summaries."""

import json
from pathlib import Path

import pytest

from daf_okn.core.join_report import markdown_report


def joined_row(page="https://example.org/page/a"):
    """A concrete current result with two distinct resource identifiers."""
    return {
        "page": page,
        "concept": "https://example.org/concept/a",
        "label": "Topic | label\ncontinued",
        "wikidata": "http://www.wikidata.org/entity/Q1",
        "external": "http://purl.obolibrary.org/obo/TEST_1",
        "externalLabel": "External | label",
        "source": "https://example.org/source.md",
    }


def test_current_summary_distinguishes_document_and_concept_counts_and_links():
    """Two supporting documents must not be counted as two distinct topics."""
    rows = [joined_row(), joined_row("https://example.org/page/b")]
    rendered = markdown_report(rows, "2026-10-23T12:00:00+00:00")
    assert "| Matched documents | 2 |" in rendered
    assert "| Matched concepts | 1 |" in rendered
    assert "| Matched concept pages |" not in rendered
    assert "| Document | Concept | Wikidata join key | External term | Source |" in rendered
    assert "https://example.org/page/a" in rendered
    assert "https://example.org/page/b" in rendered
    assert "https://example.org/concept/a" in rendered
    assert "https://example.org/source.md" in rendered
    assert "Topic \\| label continued" in rendered
    assert "External \\| label" in rendered


@pytest.mark.parametrize("page", [None, "", 12])
def test_current_summary_rejects_incomplete_document_rows(page):
    """Mixed or malformed projections must not silently become legacy reports."""
    with pytest.raises(ValueError, match="document"):
        markdown_report([joined_row(), joined_row(page)], "2026-10-23")
    legacy = joined_row()
    del legacy["page"]
    with pytest.raises(ValueError, match="document"):
        markdown_report([joined_row(), legacy], "2026-10-23")


def test_historical_summary_retains_original_captured_bytes():
    """Schema-2 result hashes bind the original combined-role Markdown format."""
    directory = Path(__file__).parents[1] / "fixtures/legacy_join_report"
    result = json.loads((directory / "join-results.json").read_text())
    rendered = markdown_report(result["rows"], result["provenance"]["observed_at"])
    assert rendered.encode() == (directory / "join-results.md").read_bytes()


def test_empty_historical_summary_remains_available():
    """An empty renderer input retains the original table contract."""
    assert "| Matched concept pages | 0 |" in markdown_report([], "2026-10-23")
