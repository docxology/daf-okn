"""Pure Markdown rendering for captured OKN cross-graph join results."""

from typing import TypedDict


class JoinedRow(TypedDict):
    """Named string values projected by the cross-graph SELECT query."""

    concept: str
    label: str
    wikidata: str
    external: str
    externalLabel: str
    source: str


def markdown_report(rows: list[JoinedRow], observed_at: str) -> str:
    """Render joined rows and their observation time as a Markdown report.

    Args:
        rows: Joined SELECT values, retained in their query order.
        observed_at: Observation timestamp; its first ten characters give the date.

    Returns:
        The complete report with escaped table labels and a trailing newline.

    Raises:
        ValueError: If document-valued results contain missing or malformed page IDs.
    """
    document_mode = any("page" in row for row in rows)
    documents: list[str] = []
    if document_mode:
        for row in rows:
            page = row.get("page")
            if not isinstance(page, str) or not page:
                raise ValueError("document results require a nonempty document page IRI")
            documents.append(page)
    lines = [
        "---",
        "title: Captured OKN cross-graph join results",
        "type: reference",
        "status: stable",
        f"updated: {observed_at[:10]}",
        "---",
        "",
        "# Captured OKN cross-graph join results",
        "",
        f"Observed at {observed_at}. Local cognitive-kb was joined with live OKN",
        "identifier-mappings and Ubergraph responses, then replayed offline.",
        "",
        "| Measurement | Value |",
        "|---|---|",
        f"| Joined rows | {len(rows)} |",
        *(
            [
                f"| Matched documents | {len(set(documents))} |",
                f"| Matched concepts | {len({row['concept'] for row in rows})} |",
            ]
            if document_mode
            else [f"| Matched concept pages | {len({row['concept'] for row in rows})} |"]
        ),
        f"| Labeled external OBO terms | {len({row['external'] for row in rows})} |",
        "",
        *(
            [
                "Each document describes a separate concept through `schema:about` and",
                "`dcterms:subject`. The concept's reviewed Wikidata mapping is joined to",
                "the remote mapping graph's `skos:exactMatch` and an OBO label.",
                "Document identifiers, concept identifiers and Markdown sources remain",
                "distinct. Joining these edges adds no identity or class-instance assertion.",
                "Labels are discovery signposts, not clinical or scientific validation.",
                "Unmatched documents are omitted.",
            ]
            if document_mode
            else [
                "The first edge is the local query's selected mapping from a concept",
                "to Wikidata. The second is the mapping graph's `skos:exactMatch` to an",
                "OBO identifier. Joining these edges does not establish identity between",
                "the page and the ontology class. Labels are discovery signposts, not",
                "clinical or scientific validation. Unmatched pages are omitted.",
            ]
        ),
        "",
        *(
            [
                "| Document | Concept | Wikidata join key | External term | Source |",
                "|---|---|---|---|---|",
            ]
            if document_mode
            else ["| Source page | Wikidata join key | External term |", "|---|---|---|"]
        ),
    ]
    for index, row in enumerate(rows):
        label = row["label"].replace("|", "\\|").replace("\n", " ")
        external_label = row["externalLabel"].replace("|", "\\|").replace("\n", " ")
        key = row["wikidata"].rsplit("/", 1)[-1]
        if document_mode:
            lines.append(
                f"| [Document]({documents[index]}) | [{label}]({row['concept']}) "
                f"| [{key}]({row['wikidata']}) | [{external_label}]({row['external']}) "
                f"| [Markdown]({row['source']}) |"
            )
        else:
            lines.append(
                f"| [{label}]({row['source']}) | [{key}]({row['wikidata']}) "
                f"| [{external_label}]({row['external']}) |"
            )
    return "\n".join(lines) + "\n"
