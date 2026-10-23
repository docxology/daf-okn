#!/usr/bin/env python3
"""Tests for the cognitive knowledge-base adapter port."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from daf_okn.core.cognitive_adapter import (
    _build_index,
    _redirect_target,
    _resolve_node_id,
    _resolve_target_path,
    build_cognitive_graph,
    export_cognitive_kb,
    extract_wiki_links,
    frontmatter_aliases,
    normalise_title,
    parse_frontmatter,
    parse_semantic_relations,
    vault_root,
)
from daf_okn.core.graph import GraphDocument
from daf_okn.core.invariants import validate_graph

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "cognitive"

EXPECTED_UNRESOLVED = [
    {
        "source": "mathematics/free_energy_principle",
        "target": "cognitive/missing_concept",
        "origin": "wikilink",
    }
]


def _edge_tuples(document: GraphDocument, origin: str | None = None) -> list[tuple[str, str, str]]:
    edges = document.edges
    if origin is not None:
        edges = [edge for edge in edges if edge.origin == origin]
    return [(edge.source, edge.target, edge.relation) for edge in edges]


def test_parse_semantic_relations_handles_all_dialects() -> None:
    """Wiki strings, triple-nested lists and the parent subkey all parse."""
    links = [
        {
            "type": "implements",
            "links": [["mathematics/bayesian_networks"]],
        },
        {
            "type": "relates_to",
            "links": [[["cognitive/pattern_separation"]]],
        },
        {
            "type": "part_of",
            "links": ["[[mathematics/bayesian_networks|Bayesian Networks]]"],
        },
        {
            "type": "relates",
            "links": ["[[mathematics/free_energy_principle]]"],
            "parent": ["[[mathematics/free_energy_principle]]"],
        },
        "not-a-dict-entry",
    ]
    pairs = parse_semantic_relations(links)
    assert ("implements", "mathematics/bayesian_networks") in pairs
    assert ("relates_to", "cognitive/pattern_separation") in pairs
    assert ("part_of", "mathematics/bayesian_networks") in pairs
    assert ("relates", "mathematics/free_energy_principle") in pairs
    assert ("has_parent", "mathematics/free_energy_principle") in pairs
    assert all(isinstance(pair[0], str) and isinstance(pair[1], str) for pair in pairs)
    assert ("not-a-dict-entry", "") not in pairs


def test_parse_semantic_relations_tolerates_none_and_defaults() -> None:
    """None values and entries without a type degrade gracefully."""
    assert parse_semantic_relations(None) == []
    assert parse_semantic_relations("not-a-list") == []
    pairs = parse_semantic_relations([{"links": ["[[some/target]]"]}])
    assert pairs == [("relates_to", "some/target")]


def test_extract_wiki_links_strips_code_and_matrices() -> None:
    """Fenced/inline code and matrix literals never yield link targets."""
    text = (
        "Legit [[mathematics/markov_blanket|Markov Blanket]] and "
        "[[mathematics/bayesian_networks#section|Bayesian]].\n"
        "Matrix single-row [[1, 2]] and multi-row [[1, 2], [3, 4]].\n"
        "```math\nA = [[1, 2], [3, 4]]\n```\n"
        "Inline `[[fake_inline_target]]` is ignored.\n"
        "~~~\n[[fake_fence_target]]\n~~~\n"
    )
    assert extract_wiki_links(text) == [
        "mathematics/markov_blanket",
        "mathematics/bayesian_networks",
    ]
    assert extract_wiki_links("") == []


def test_parse_frontmatter_splits_yaml_and_body() -> None:
    """Leading --- fences split cleanly; missing fences return the raw text."""
    frontmatter, body = parse_frontmatter("---\ntitle: A\ntype: concept\n---\nBody text.")
    assert frontmatter == {"title": "A", "type": "concept"}
    assert body.strip() == "Body text."
    no_fence_frontmatter, no_fence_body = parse_frontmatter("No fences here.")
    assert no_fence_frontmatter == {}
    assert no_fence_body == "No fences here."


def test_build_graph_node_ids_titles_and_folder_docs() -> None:
    """Node ids are vault-relative sans .md; folder docs and titles normalise."""
    document = build_cognitive_graph(FIXTURE_ROOT)
    ids = {node.id for node in document.nodes}
    assert "mathematics/markov_blanket" in ids
    assert "README" in ids
    assert not any(".md" in node_id or "\\" in node_id for node_id in ids)

    by_id = {node.id: node for node in document.nodes}
    assert by_id["README"].node_type == "overview"
    assert by_id["agents/overview"].node_type == "overview"
    assert by_id["systems/overview"].node_type == "overview"
    markov = by_id["mathematics/markov_blanket"]
    assert len(document.nodes) == 17
    assert markov.title == "Markov Blanket"
    assert markov.node_type == "concept"
    assert markov.attributes["status"] == "stable"
    assert markov.attributes["tags"] == ["mathematics", "graphical_models"]
    assert len(document.nodes) == 17
    assert document.name == "cognitive-kb"


def test_build_graph_default_collapses_redirects() -> None:
    """Default mode removes redirect nodes and rewrites incident edges."""
    document = build_cognitive_graph(FIXTURE_ROOT)
    by_id = {node.id: node for node in document.nodes}
    assert "cognitive/alias_redirect" not in by_id
    assert len(by_id) == 17
    redirects_to = [edge for edge in document.edges if edge.relation == "redirects_to"]
    assert redirects_to == []
    # The redirect body's own wikilink becomes a self-loop artifact and drops.
    assert (
        "mathematics/free_energy_principle",
        "mathematics/free_energy_principle",
    ) not in [(edge.source, edge.target) for edge in document.edges]
    counts = document.metadata["counts"]
    assert counts["nodes"] == 17
    assert counts["documents"] == 11
    assert counts["concepts"] == 6
    assert counts["edges"] == 27
    assert counts["redirect_edges"] == 0
    assert counts["semantic_edges"] == 7
    assert counts["wikilink_edges"] == 8


def test_build_graph_keep_redirects_keeps_node_and_edge() -> None:
    """collapse_redirects=False keeps the redirect node, flag and edge."""
    document = build_cognitive_graph(FIXTURE_ROOT, collapse_redirects=False)
    by_id = {node.id: node for node in document.nodes}
    assert "cognitive/alias_redirect" in by_id
    assert by_id["cognitive/alias_redirect"].node_type == "redirect"
    assert by_id["cognitive/alias_redirect"].attributes["redirect"] == (
        "mathematics/free_energy_principle"
    )
    assert (
        "cognitive/alias_redirect",
        "mathematics/free_energy_principle",
        "redirects_to",
    ) in _edge_tuples(document, origin="redirect")
    assert len(document.nodes) == 18
    assert len(document.edges) == 29
    assert document.metadata["counts"]["redirect_edges"] == 1


def test_build_graph_relations_and_origins() -> None:
    """Explicit semantic relations keep their types; body links are untyped."""
    document = build_cognitive_graph(FIXTURE_ROOT)
    explicit = set(_edge_tuples(document, origin="explicit"))
    assert (
        "concept:mathematics/markov_blanket",
        "concept:mathematics/free_energy_principle",
        "implements",
    ) in explicit
    assert (
        "concept:mathematics/markov_blanket",
        "concept:mathematics/bayesian_networks",
        "extends",
    ) in explicit
    assert (
        "concept:mathematics/markov_blanket",
        "concept:cognitive/pattern_separation",
        "relates_to",
    ) in explicit
    assert (
        "concept:mathematics/markov_blanket",
        "concept:mathematics/bayesian_networks",
        "concept/part_of",
    ) in explicit
    assert (
        "mathematics/markov_blanket",
        "mathematics/free_energy_principle",
        "has_parent",
    ) in explicit

    wikilinks = _edge_tuples(document, origin="wikilink")
    assert ("README", "mathematics/markov_blanket", "related") in wikilinks
    assert (
        "mathematics/free_energy_principle",
        "mathematics/markov_blanket",
        "related",
    ) in wikilinks
    assert (
        "cognitive/pattern_separation",
        "mathematics/markov_blanket",
        "related",
    ) in wikilinks
    assert all(
        origin in {"explicit", "wikilink", "entity_model"}
        for origin in {edge.origin for edge in document.edges}
    )


def test_build_graph_duplicate_stem_resolves_alphabetically() -> None:
    """Ambiguous stems resolve to the first alphabetical match."""
    document = build_cognitive_graph(FIXTURE_ROOT)
    assert (
        "cognitive/pattern_separation",
        "agents/overview",
        "related",
    ) in _edge_tuples(document, origin="wikilink")
    assert not any(edge.target == "systems/overview" for edge in document.edges)


def test_build_graph_records_unresolved_targets() -> None:
    """Unresolvable targets are recorded, not dropped, in both modes."""
    collapsed = build_cognitive_graph(FIXTURE_ROOT)
    assert collapsed.metadata["unresolved_targets"] == EXPECTED_UNRESOLVED
    kept = build_cognitive_graph(FIXTURE_ROOT, collapse_redirects=False)
    assert kept.metadata["unresolved_targets"] == EXPECTED_UNRESOLVED


def test_build_graph_no_matrix_literal_edges() -> None:
    """Matrix literals never become edges in either position."""
    document = build_cognitive_graph(FIXTURE_ROOT)
    forbidden = {
        "1, 2",
        "[1, 2]",
        "[3, 4]",
        "3, 4",
        "fake_inline_target",
        "fake_fence_target",
    }
    for edge in document.edges:
        assert edge.source not in forbidden
        assert edge.target not in forbidden
    assert document.metadata["counts"]["files"] == 12


def test_build_graph_no_wikilinks_option() -> None:
    """include_wikilinks=False keeps only explicit semantic edges."""
    document = build_cognitive_graph(FIXTURE_ROOT, include_wikilinks=False)
    origins = {edge.origin for edge in document.edges}
    assert origins == {"explicit", "entity_model"}
    assert document.metadata["counts"]["wikilink_edges"] == 0
    assert document.metadata["counts"]["semantic_edges"] == 7


def test_build_graph_missing_root_raises(tmp_path: Path) -> None:
    """A missing knowledge-base root is a hard error."""
    with pytest.raises(FileNotFoundError):
        build_cognitive_graph(tmp_path / "does-not-exist")


def test_export_cognitive_kb_round_trips(tmp_path: Path) -> None:
    """The export wrapper writes JSON that load_json restores faithfully."""
    repo_root = tmp_path / "repo" / "knowledge_base"
    repo_root.mkdir(parents=True)
    shutil.copytree(FIXTURE_ROOT, repo_root, dirs_exist_ok=True)
    out_path = tmp_path / "out" / "cognitive_kg.json"

    document = export_cognitive_kb(tmp_path / "repo", out_path)
    assert out_path.is_file()
    assert document.name == "cognitive-kb"
    assert document.metadata["vault_name"] == "knowledge_base"
    assert "source_root" not in document.metadata  # no absolute local paths in exports

    restored = GraphDocument.load_json(out_path)
    assert restored.name == document.name
    assert len(restored.nodes) == len(document.nodes) == 17
    assert len(restored.edges) == len(document.edges) == 27
    assert restored.metadata["counts"] == document.metadata["counts"]


def _write(path: Path, text: str) -> Path:
    """Create a markdown (or other) file inside a temporary vault."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_frontmatter_tolerates_unparsable_and_non_dict_yaml() -> None:
    """Broken YAML keeps the raw text; non-mapping YAML keeps only the body."""
    broken = "---\ntitle: 'unclosed\n---\nBody."
    assert parse_frontmatter(broken) == ({}, broken)

    non_dict = "---\n- one\n- two\n---\nBody."
    frontmatter, body = parse_frontmatter(non_dict)
    assert frontmatter == {}
    assert body == "Body."

    unclosed = "---\ntitle: A\nBody without a closing fence."
    assert parse_frontmatter(unclosed) == ({}, unclosed)


def test_normalise_title_handles_none_and_pipeless_wikilinks() -> None:
    """None titles empty out; pipeless wiki titles keep the raw target."""
    assert normalise_title(None) == ""
    assert normalise_title("[[plain-target]]") == "plain-target"
    assert normalise_title("[[target|Display Name]]") == "Display Name"
    assert normalise_title("  Plain Title  ") == "Plain Title"


def test_parse_semantic_relations_skips_empty_scalars() -> None:
    """Non-string and empty link scalars never yield relation pairs."""
    pairs = parse_semantic_relations(
        [
            {"type": "relates", "links": [None, "", 42, "[[real/target|Real]]"]},
        ]
    )
    assert pairs == [("relates", "real/target")]


def test_extract_wiki_links_skips_targets_that_reduce_to_empty() -> None:
    """Display-only and fragment-only wiki links produce no targets."""
    text = "[[|display]] then [[#section]] then [[real/target]]"
    assert extract_wiki_links(text) == ["real/target"]


def test_build_graph_skips_non_markdown_files(tmp_path: Path) -> None:
    """Only markdown files become nodes; suffixed targets stay unresolved."""
    vault = tmp_path / "kb"
    _write(
        vault / "solo.md",
        "# Solo\n\nSee [[other/notes.txt]] and [[figures/diagram.png]].\n",
    )
    _write(vault / "other" / "notes.txt", "plain text")
    _write(vault / "figures" / "diagram.png", "binary-ish")

    document = build_cognitive_graph(vault)

    assert document.metadata["counts"]["files"] == 1
    assert [node.id for node in document.nodes] == ["solo"]
    assert document.edges == []
    unresolved = {
        (item["target"], item["origin"]) for item in document.metadata["unresolved_targets"]
    }
    assert unresolved == {
        ("other/notes.txt", "wikilink"),
        ("figures/diagram.png", "wikilink"),
    }


def test_redirect_node_without_target_is_kept_unmapped(tmp_path: Path) -> None:
    """A redirect node without a redirect target emits no edges or unresolved."""
    vault = tmp_path / "kb"
    _write(vault / "alias.md", "---\ntitle: Alias\ntype: redirect\n---\nNo target given.\n")

    document = build_cognitive_graph(vault)

    assert [node.id for node in document.nodes] == ["alias"]
    assert document.edges == []
    assert document.metadata["unresolved_targets"] == []
    assert document.metadata["counts"]["redirect_edges"] == 0


def test_unresolvable_redirect_recorded_as_unresolved(tmp_path: Path) -> None:
    """A redirect pointing at a missing page is recorded with origin redirect."""
    vault = tmp_path / "kb"
    _write(
        vault / "alias.md",
        "---\ntitle: Alias\ntype: redirect\nredirect: '[[ghost]]'\n---\n",
    )

    kept = build_cognitive_graph(vault, collapse_redirects=False)
    assert kept.metadata["unresolved_targets"] == [
        {"source": "alias", "target": "ghost", "origin": "redirect"}
    ]
    assert kept.metadata["counts"]["redirect_edges"] == 0
    assert [node.id for node in kept.nodes] == ["alias"]

    collapsed = build_cognitive_graph(vault)
    assert collapsed.metadata["unresolved_targets"][0]["origin"] == "redirect"
    assert [node.id for node in collapsed.nodes] == ["alias"]


def test_duplicate_wikilinks_collapse_to_one_edge(tmp_path: Path) -> None:
    """Repeated identical links in one body collapse to a single edge."""
    vault = tmp_path / "kb"
    _write(vault / "a.md", "# A\n\nLinks [[b]] twice: [[b]].\n")
    _write(vault / "b.md", "# B")

    document = build_cognitive_graph(vault)

    assert [(edge.source, edge.target, edge.relation, edge.origin) for edge in document.edges] == [
        ("a", "b", "related", "wikilink")
    ]
    assert document.metadata["counts"]["wikilink_edges"] == 1
    assert document.metadata["counts"]["edges"] == 1


def test_resolver_prefers_sibling_dir_over_root_stem(tmp_path: Path) -> None:
    """Sibling-directory candidates win over the alphabetical stem index."""
    vault = tmp_path / "kb"
    _write(vault / "systems" / "overview.md", "# Systems")
    _write(vault / "agents" / "overview.md", "# Agents")
    index = _build_index(vault)

    resolved = _resolve_target_path(vault, vault / "agents" / "note.md", "overview", index)

    assert resolved == vault / "agents" / "overview.md"


def test_resolver_skips_duplicate_root_candidates(tmp_path: Path) -> None:
    """Root-level sources deduplicate their candidate paths before matching."""
    vault = tmp_path / "kb"
    _write(vault / "a.md", "# A\n\n[[b]]\n")
    _write(vault / "b.md", "# B")
    index = _build_index(vault)

    resolved = _resolve_target_path(vault, vault / "a.md", "b", index)

    assert resolved == vault / "b.md"


def test_resolver_falls_back_to_relative_indexes(tmp_path: Path) -> None:
    """Exact rel-path, rel-path-sans-suffix, and suffix-miss fallbacks fire."""
    vault = tmp_path / "kb"
    _write(vault / "systems" / "overview.md", "# Systems")
    root = vault.resolve()
    index = _build_index(root)
    source = root / "other" / "note.md"

    # exact repository-relative fallback for a normalised suffixed target
    assert _resolve_target_path(root, source, " systems/overview.md ", index) == (
        root / " systems/overview.md "
    )
    # relative path without suffix fallback returns the indexed markdown path
    assert _resolve_target_path(root, source, " systems/overview ", index) == Path(
        "systems/overview.md"
    )
    # a suffixed target with no exact match is unresolvable even though the
    # bare stem ("overview") exists in the stem index — the suffix check wins
    assert _resolve_target_path(root, source, "notes/overview.md", index) is None


def test_resolve_node_id_rejects_relative_and_non_markdown_hits(tmp_path: Path) -> None:
    """Non-markdown files and out-of-root hits are not knowledge nodes."""
    vault = tmp_path / "kb"
    _write(vault / "systems" / "overview.md", "# Systems")
    _write(vault / "figures" / "diagram.png", "png")
    root = vault.resolve()
    index = _build_index(root)
    source = root / "other" / "note.md"

    # the rel-path-sans-suffix fallback yields a path outside the root
    assert _resolve_node_id(root, source, " systems/overview ", index) is None
    # a resolved non-markdown file is not a knowledge node
    assert _resolve_node_id(root, source, "figures/diagram.png", index) is None


def test_redirect_target_accepts_plain_and_wiki_forms() -> None:
    """Redirect values may be wiki links, plain text, or absent."""
    assert _redirect_target({"redirect": "[[mathematics/markov_blanket|MB]]"}) == (
        "mathematics/markov_blanket"
    )
    assert _redirect_target({"redirect": "plain-target"}) == "plain-target"
    assert _redirect_target({}) == ""


def test_resolver_normalises_relative_targets_against_source_dir(
    tmp_path: Path,
) -> None:
    """'../'-bearing targets resolve against the source directory, then clamp."""
    _write(tmp_path / "relative_links" / "nested_page.md", "# nested")
    _write(tmp_path / "AGENTS.md", "# root agents")
    _write(tmp_path / "cognitive" / "README.md", "# cognitive")
    index = _build_index(tmp_path)
    source = tmp_path / "relative_links" / "nested_page.md"

    assert _resolve_target_path(tmp_path, source, "../AGENTS", index) == (tmp_path / "AGENTS.md")
    # One '..' too many is clamped to the vault root instead of escaping it.
    assert _resolve_target_path(tmp_path, source, "../../cognitive/README", index) == (
        tmp_path / "cognitive" / "README.md"
    )
    # A target that normalises to nothing yields no candidate.
    assert _resolve_target_path(tmp_path, source, "..", index) is None


def test_build_graph_resolves_relative_targets_and_drops_self_loops() -> None:
    """Relative targets become canonical ids; self-loops drop and are counted."""
    for collapse in (True, False):
        document = build_cognitive_graph(FIXTURE_ROOT, collapse_redirects=collapse)
        tuples = _edge_tuples(document)
        assert ("relative_links/nested_page", "AGENTS", "organizes") in tuples
        assert ("relative_links/nested_page", "AGENTS", "has_parent") in tuples
        assert ("relative_links/nested_page", "AGENTS", "related") in tuples
        assert ("relative_links/nested_page", "cognitive/README", "related") in tuples
        endpoints = {endpoint for edge in document.edges for endpoint in (edge.source, edge.target)}
        assert not any("../" in endpoint or "./" in endpoint for endpoint in endpoints)
        assert document.metadata["self_loop_edges"] == ["relative_links/nested_page"]
        assert document.metadata["counts"]["self_loop_edges"] == 1
        assert ("relative_links/nested_page", "relative_links/nested_page") not in [
            (edge.source, edge.target) for edge in document.edges
        ]
        assert validate_graph(document) == []


def test_spaced_file_names_slug_into_node_ids() -> None:
    """Spaces in vault paths collapse to underscores in ids and edge endpoints."""
    for collapse in (True, False):
        document = build_cognitive_graph(FIXTURE_ROOT, collapse_redirects=collapse)
        assert "spaced_folder/social_ecological_systems" in {node.id for node in document.nodes}
        for edge in document.edges:
            assert " " not in edge.source
            assert " " not in edge.target
        assert any(
            edge.source == "spaced_folder/social_ecological_systems"
            or edge.target == "spaced_folder/social_ecological_systems"
            for edge in document.edges
        )
        assert validate_graph(document) == []


# ---------------------------------------------------------------------------
# Generic Obsidian vaults: aliases, deterministic repeated names, metadata
# ---------------------------------------------------------------------------


def _vault(tmp_path: Path, pages: dict[str, str]) -> Path:
    """Write ``pages`` ({relative path: markdown}) into a small real vault."""
    root = tmp_path / "vault"
    for rel, text in pages.items():
        _write(root / rel, text)
    return root


def _links(document: GraphDocument) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in document.edges}


def test_alias_links_resolve_through_frontmatter_aliases(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        {
            "a/plasticity_model.md": (
                "---\ntitle: Plasticity\naliases: [Neural Plasticity, synaptic-change]\n---\nbody"
            ),
            "b/source.md": (
                "---\ntitle: Source\n---\n"
                "See [[neural plasticity]], [[Synaptic Change|change]] "
                "and [[Neural_Plasticity#top]]."
            ),
        },
    )
    document = build_cognitive_graph(root)
    assert _links(document) == {("b/source", "a/plasticity_model")}
    assert document.metadata["counts"]["unresolved_targets"] == 0
    node = {n.id: n for n in document.nodes}["a/plasticity_model"]
    assert node.attributes["aliases"] == ["Neural Plasticity", "synaptic-change"]


def test_alias_accepts_scalar_and_singular_forms(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        {
            "one.md": "---\naliases: Uno\n---\n",
            "two.md": "---\nalias:\n  - Dos\n---\n",
            "src.md": "[[Uno]] [[dos]]",
        },
    )
    assert _links(build_cognitive_graph(root)) == {("src", "one"), ("src", "two")}
    assert frontmatter_aliases({"aliases": ["x", 3, None, "  "], "alias": "y"}) == ["x", "3", "y"]
    assert frontmatter_aliases({}) == []


def test_file_names_win_over_aliases(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        {
            "z_other.md": "---\naliases: [target]\n---\n",
            "target.md": "---\ntitle: Real\n---\n",
            "src.md": "[[target]]",
        },
    )
    assert _links(build_cognitive_graph(root)) == {("src", "target")}


def test_repeated_names_resolve_alphabetically(tmp_path: Path) -> None:
    """Stems and aliases claimed by several pages go to the alphabetically first path."""
    root = _vault(
        tmp_path,
        {
            "zeta/dup.md": "---\ntitle: Z\n---\n",
            "alpha/dup.md": "---\ntitle: A\n---\n",
            "mid/x.md": "---\naliases: [Shared Name]\n---\n",
            "beta/y.md": "---\naliases: [shared name]\n---\n",
            "root_src.md": "[[dup]] [[shared_name]]",
        },
    )
    assert _links(build_cognitive_graph(root)) == {
        ("root_src", "alpha/dup"),
        ("root_src", "beta/y"),
    }


def test_alias_resolution_is_independent_of_file_creation_order(tmp_path: Path) -> None:
    pages = {
        "q/one.md": "---\naliases: [Same]\n---\n",
        "a/two.md": "---\naliases: [Same]\n---\n",
        "src.md": "[[Same]]",
    }
    first = build_cognitive_graph(_vault(tmp_path / "x", pages))
    second = build_cognitive_graph(_vault(tmp_path / "y", dict(reversed(list(pages.items())))))
    assert _links(first) == _links(second) == {("src", "a/two")}
    assert first.to_dict()["edges"] == second.to_dict()["edges"]


def test_unresolvable_alias_is_recorded_not_dropped(tmp_path: Path) -> None:
    root = _vault(tmp_path, {"a.md": "---\naliases: [Known]\n---\n[[Unknown]]"})
    document = build_cognitive_graph(root)
    assert document.edges == []
    assert document.metadata["unresolved_targets"] == [
        {"source": "a", "target": "Unknown", "origin": "wikilink"}
    ]


def test_index_alias_map_ignores_unreadable_and_unfenced_files(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        {
            "good.md": "---\naliases: [Fine]\n---\n",
            "plain.md": "no frontmatter at all",
            "bad_yaml.md": "---\naliases: [unclosed\n---\n",
        },
    )
    (root / "binary.md").write_bytes(b"\xff\xfe\x00bad utf8")
    index = _build_index(root)
    assert set(index.markdown_by_alias) == {"fine"}
    assert len(index.markdown_by_stem) == 4


def test_generic_vault_has_no_cognitive_specific_requirements(tmp_path: Path) -> None:
    """A plain Obsidian vault (no semantic_relations, no knowledge_base/) exports fine."""
    root = _vault(
        tmp_path,
        {
            "Home.md": "# Home\n[[Projects/Alpha]] and [[Beta]]",
            "Projects/Alpha.md": "[[Home]]",
            "Beta.md": "",
        },
    )
    assert vault_root(root) == root
    document = build_cognitive_graph(root, name="my-notes")
    assert document.name == "my-notes"
    assert _links(document) == {
        ("Home", "Projects/Alpha"),
        ("Home", "Beta"),
        ("Projects/Alpha", "Home"),
    }
    assert {n.node_type for n in document.nodes} == {"document"}
    assert validate_graph(document) == []


def test_vault_root_prefers_knowledge_base_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "knowledge_base").mkdir()
    assert vault_root(tmp_path) == tmp_path / "knowledge_base"
    out = tmp_path / "out.json"
    _write(tmp_path / "knowledge_base" / "p.md", "---\ntitle: P\n---\n")
    document = export_cognitive_kb(tmp_path, out, name="renamed")
    assert document.name == "renamed"
    assert GraphDocument.load_json(out).name == "renamed"


def test_extra_frontmatter_fields_become_node_attributes(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        {
            "cite.md": (
                "---\ntitle: Cite\ndescription: Short text\ncomplexity: advanced\n"
                "authors: [A. One, B. Two]\nyear: 2022\njournal: J\ndoi: 10.1/x\n"
                "wikidata: Q1\ncreated: 2024-01-02\nupdated: 2025-03-04\n"
                "modified: 2026-10-23\nprocessing_priority: high\n---\n"
            )
        },
    )
    attrs = build_cognitive_graph(root).nodes[0].attributes
    assert attrs["description"] == "Short text"
    assert attrs["authors"] == ["A. One", "B. Two"]
    assert attrs["year"] == 2022
    assert attrs["created"] == "2024-01-02"
    assert attrs["doi"] == "10.1/x" and attrs["wikidata"] == "Q1"
    assert attrs["journal"] == "J" and attrs["complexity"] == "advanced"
    assert attrs["modified"] == "2026-10-23" and attrs["processing_priority"] == "high"


def test_exported_json_contains_no_absolute_paths(tmp_path: Path) -> None:
    root = _vault(tmp_path, {"a.md": "[[b]]", "b.md": ""})
    out = tmp_path / "graph.json"
    export_cognitive_kb(root, out)
    assert str(tmp_path) not in out.read_text(encoding="utf-8")


def test_default_graph_name_distinguishes_cognitive_checkouts_from_plain_vaults(
    tmp_path: Path,
) -> None:
    from daf_okn.core.cognitive_adapter import default_graph_name

    checkout = tmp_path / "anything"
    (checkout / "knowledge_base").mkdir(parents=True)
    assert default_graph_name(checkout) == "cognitive-kb"
    assert default_graph_name(tmp_path / "Zettel Notes 2026") == "zettel-notes-2026"
    assert default_graph_name(Path("/")) == "vault"


def test_only_declared_topics_get_separate_resources_and_mappings(tmp_path):
    root = _vault(
        tmp_path,
        {
            "topic.md": (
                "---\ntype: concept\naliases: [An alias]\ndefinition: A topic definition\n"
                "created: 2026-10-23\ntags: [precise_tag]\n---\n"
            ),
            "guide.md": "---\ntype: guide\n---\n",
            "unknown.md": "---\ntype: unknown_editorial_role\n---\n",
            "plain.md": "# Untyped document\n",
            "citations/paper.md": "---\ntype: citation\n---\n",
        },
    )
    document = build_cognitive_graph(root)
    by_id = {node.id: node for node in document.nodes}
    assert {n.id for n in document.nodes if n.attributes["entity_role"] == "concept"} == {
        "concept:topic"
    }
    assert by_id["topic"].attributes["created"] == "2026-10-23"
    assert by_id["topic"].attributes["tags"] == ["precise_tag"]
    assert "definition" not in by_id["topic"].attributes
    assert by_id["concept:topic"].attributes["definition"] == "A topic definition"
    assert by_id["concept:topic"].attributes["aliases"] == ["An alias"]
    assert "created" not in by_id["concept:topic"].attributes
    assert set(_edge_tuples(document, "entity_model")) == {
        ("topic", "concept:topic", r) for r in ("schema:about", "dcterms:subject")
    }


def test_unknown_and_mixed_relations_keep_document_assertions_for_curation(tmp_path):
    root = _vault(
        tmp_path,
        {
            "a.md": (
                "---\ntype: concept\nsemantic_relations:\n- type: implements\n"
                "  links: ['[[guide]]']\n- type: unreviewed_causal_name\n  links: ['[[b]]']\n"
                "- type: documents\n  links: ['[[b]]']\n---\n"
            ),
            "b.md": "---\ntype: concept\n---\n",
            "guide.md": "---\ntype: guide\n---\n",
        },
    )
    document = build_cognitive_graph(root)
    assert set(_edge_tuples(document, "explicit")) == {
        ("a", "guide", "document/implements"),
        ("a", "b", "document/unreviewed_causal_name"),
        ("a", "b", "document/documents"),
    }
    assert document.metadata["document_assertions"] == [
        {"source": "a", "target": "guide", "relation": "implements"},
        {"source": "a", "target": "b", "relation": "unreviewed_causal_name"},
    ]
