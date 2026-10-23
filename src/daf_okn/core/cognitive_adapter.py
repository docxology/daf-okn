#!/usr/bin/env python3
r"""Generic Obsidian-vault adapter, built for the Active Inference Institute
``cognitive`` knowledge base, producing the shared :mod:`daf_okn.core.graph` model.

Any directory of markdown pages with YAML frontmatter and ``[[wiki links]]`` can
be read: each page is a document node, ``[[links]]`` are document references,
and declared topic-bearing pages have distinct concept nodes. The ``cognitive``
knowledge base (https://github.com/ActiveInferenceInstitute/cognitive) is the
reference case, and its ``semantic_relations`` frontmatter dialect (typed edges)
is understood in addition to plain Obsidian links.

Provenance: the parsing rules are re-implemented here from the upstream
``cognitive`` repository — the wiki-target resolution order of
``code/scripts/verify_links.py`` and the frontmatter / ``semantic_relations``
markdown dialect of ``knowledge_base/*.md``. No code is imported from the
upstream repository; this module only reads a markdown vault.

Dialect notes carried over verbatim from the source repository:

* Every file has a document node at its vault-relative POSIX path without
  ``.md``. Declared topics add ``concept:<path>`` nodes; the document links to
  its topic with schema:about and dcterms:subject. Untyped documents remain
  documents unless they carry explicit reviewed topic mappings.
* YAML frontmatter sits between leading ``---`` fences and carries ``title``,
  ``type``, ``status``, ``created``, ``updated``, ``tags`` and — on redirect
  nodes — ``redirect``. Wiki-linkish titles ``[[target|display]]`` are
  normalised to the plain display text.
* ``semantic_relations`` entries are ``{type: str, links: [...]}`` maps whose
  links may be wiki-link strings or (accidentally) nested YAML lists — the
  ``- - - target`` form parses as ``[[['target']]]`` and is flattened
  recursively to scalar strings. Unquoted ``[[target|display]]`` entries are
  flow-parsed by YAML into nested lists whose scalar keeps the ``target|display``
  body, so pipes/fragments are stripped after flattening as well. Non-standard
  extra subkeys such as ``parent:`` map to the ``has_parent`` relation; other
  unknown subkeys are ignored.
* Relation types are uncontrolled lowercase snake-case strings observed as
  ``organizes``, ``documents``, ``implements``, ``extends``, ``foundation``,
  ``foundation_for``, ``relates``, ``relates_to``, ``part_of`` and
  ``provides``; direction is source file → target.
* Body wiki-links become untyped edges with ``origin='wikilink'`` after
  stripping fenced and inline code; matrix literals matching
  ``^[\d,\s\[\]\.]+$`` are never treated as links.
* Folder documents (``README.md``, ``AGENTS.md``, ``index.md``) are nodes
  too and fall back to the ``overview`` / ``index`` node types.
* Redirect nodes (``type: redirect`` with ``redirect: '[[target]]'``) emit
  ``redirects_to`` edges; with ``collapse_redirects=True`` they are removed
  and incident edges are rewritten through the redirect target.
* Targets resolve sibling-dir relative first, then repo-root relative, then
  via ``.md`` suffix, then as relative path without suffix, then via the
  alphabetical stem index, and finally via frontmatter ``aliases:`` (as
  Obsidian does, so ``[[plasticity]]`` opens the page that lists "plasticity"
  as an alias; alias matching ignores case, ``_`` and ``-``). Repeated names —
  stems or aliases claimed by several pages — always resolve to the
  alphabetically first path, whatever order the filesystem lists files in.
  Unresolvable targets are recorded in ``metadata['unresolved_targets']``
  instead of being silently dropped.
"""

from __future__ import annotations

import os
import posixpath
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from daf_okn.core.graph import EdgeRecord, GraphDocument, NodeRecord

__all__ = [
    "MATRIX_LITERAL_PATTERN",
    "WIKI_LINK_PATTERN",
    "build_cognitive_graph",
    "default_graph_name",
    "export_cognitive_kb",
    "extract_wiki_links",
    "frontmatter_aliases",
    "normalise_title",
    "parse_frontmatter",
    "parse_semantic_relations",
    "vault_root",
    "separate_document_topics",
]

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~")
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")
MATRIX_LITERAL_PATTERN = re.compile(r"^[\d,\s\[\]\.]+$")

IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "Output",
    "output",
    "outputs",
    "venv",
}

FILE_LIKE_SUFFIXES = {
    ".bib",
    ".csv",
    ".css",
    ".gif",
    ".htm",
    ".html",
    ".ipynb",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".md",
    ".markdown",
    ".mp3",
    ".mp4",
    ".npy",
    ".npz",
    ".pdf",
    ".png",
    ".py",
    ".rst",
    ".sh",
    ".svg",
    ".tex",
    ".toml",
    ".ts",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

DOCUMENT_NODE_TYPES = {
    "readme.md": "overview",
    "agents.md": "overview",
    "index.md": "index",
}

DEFAULT_RELATION = "relates_to"
PARENT_RELATION = "has_parent"
REDIRECT_RELATION = "redirects_to"
WIKILINK_RELATION = "related"
GRAPH_NAME = "cognitive-kb"

ENTITY_MODEL = "document-concept-v1"
DOCUMENT_TYPES = frozenset(
    {
        "overview",
        "index",
        "redirect",
        "citation_redirect",
        "citation",
        "agents",
        "glossary",
        "reference",
        "guide",
        "implementation",
        "implementation_guide",
        "documentation",
        "catalog",
        "resource",
        "roadmap",
        "verification",
        "learning_path",
        "agent_config",
        "matrix_spec",
        "example",
        "visualization",
        "meta",
    }
)
TOPIC_TYPES = frozenset(
    {
        "concept",
        "mathematical_concept",
        "biological_concept",
        "cognitive_concept",
        "knowledge_base",
        "biology",
        "mathematics",
        "philosophy",
        "systems",
        "system",
        "ontology",
        "article",
        "application",
        "integration",
        "research",
        "state_space",
    }
)
CONCEPT_ATTRIBUTES = frozenset({"aliases", "definition", "scope_note", "external_mappings"})
CONCEPT_RELATIONS = {
    "implements": (
        "Source method or design concept implements the target specification or theory concept; "
        "no execution or real-world instance is asserted."
    ),
    "extends": "Source concept extends the target concept's formulation or scope.",
    "foundation_for": "Source topic provides a conceptual foundation for the target topic.",
    "foundational_for": "Source topic provides a conceptual foundation for the target topic.",
    "foundation": "Source topic has the target topic as its conceptual foundation.",
    "mathematical_basis": "Source topic has the target topic as its mathematical basis.",
    "provides": (
        "Source concept supplies a conceptual capability or component used by the target concept."
    ),
    "applies_to": "Source method or theory concept is described as applicable to the target topic.",
    "foundational_to": "Source topic provides a conceptual foundation for the target topic.",
    "underpins": "Source topic provides a conceptual basis for the target topic.",
    "foundational_theory": "Source topic draws on the target foundational theory.",
    "builds_on": "Source topic builds conceptually on the target topic.",
    "grounded_in": "Source topic is conceptually grounded in the target topic.",
    "implemented_by": (
        "Source specification or theory concept is implemented conceptually by the target method "
        "or design; no executable instance is asserted."
    ),
    "generalizes": "Source topic generalizes the target topic; no SKOS hierarchy is inferred.",
    "specializes": "Source topic specializes the target topic; no SKOS hierarchy is inferred.",
    "formalized_by": "Source topic uses the target topic as a formalization.",
    "integrates": "Source topic integrates the target topic into its conceptual formulation.",
    "influences": (
        "Source author asserts that the source topic influences the target topic; "
        "causation is not independently verified."
    ),
    "supports": "Source author asserts conceptual support from source topic to target topic.",
    "specifies": "Source topic supplies a specification for the target topic.",
    "uses": "Source topic uses the target method or conceptual resource.",
    "used_by": "Source topic is used by the target method or conceptual resource.",
    "applied_in": "Source topic is presented as applied in the target topic.",
    "applications": "Source topic lists the target topic as an application.",
    "examples": "Source topic lists the target topic as a conceptual example, not an OWL instance.",
    "includes": "Source topic includes the target topic in its conceptual scope.",
    "operates_on": "Source method concept operates on the target conceptual structure.",
    "connects": "Source topic provides a conceptual connection to the target topic.",
    "contrasts_with": "Source topic is contrasted with the target topic by the source author.",
    "prerequisite_for": "Source topic is a conceptual prerequisite for the target topic.",
    "prerequisite": "Source topic requires the target topic as a conceptual prerequisite.",
    "emerges_from": (
        "Source topic is described as emerging from the target topic; "
        "no instance-level causation is asserted."
    ),
    "analyzes": "Source method concept analyzes the target topic.",
    "part_of": "Source topic is a conceptual part of the target topic, not document containment.",
    "component_of": (
        "Source topic is a conceptual component of the target topic, not document containment."
    ),
}
DOCUMENT_RELATION_MEANINGS = {
    "documents": "Source document documents material presented in the target document.",
    "documented_by": "Source document names the target document as its documentation.",
    "documented_in": "Source document names the target document as its documentation location.",
    "defines": "Source document lists the target document under its definitions.",
    "guides": "Source document lists the target document as guidance material.",
    "maps": "Source document cross-references the target document in a source-authored map.",
    "aggregates": "Source document aggregates or indexes the target document.",
    "explains": "Source document offers an explanation of material in the target document.",
    "demonstrates": "Source document offers an example of material in the target document.",
    "visualizes": "Source document offers a visualization of material in the target document.",
}
_RELATED_RELATIONS = frozenset({"relates", "related", "relates_to", "related_to"})
_PART_RELATIONS = frozenset({"part_of", "component_of"})
_DOCUMENT_RELATIONS = (
    frozenset(
        {
            "organizes",
            "has_parent",
            "redirects_to",
            "cites",
            "cited_by",
            "documents",
        }
    )
    | DOCUMENT_RELATION_MEANINGS.keys()
)


def separate_document_topics(document: GraphDocument) -> GraphDocument:
    """Separate vault documents and their topics without changing source records.

    Page IDs retain their original spelling; topic IDs use ``concept:<page-id>``.
    Unknown or mixed-scope assertions remain explicit document assertions and
    are listed for curation. SPARQL-imported RDF retains its own term identities.
    """
    if (
        document.metadata.get("source") == "sparql"
        or document.metadata.get("entity_model") == ENTITY_MODEL
    ):
        return document
    nodes: list[NodeRecord] = []
    topics: dict[str, str] = {}
    ids = {node.id for node in document.nodes}
    for node in document.nodes:
        if re.match(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://|urn:|_:)", node.id) or node.node_type in {
            "literal",
            "bnode",
            "uri",
        }:
            nodes.append(node)
            continue
        attrs = dict(node.attributes)
        role = attrs.get("entity_role")
        if role is not None:
            raise ValueError(f"unversioned entity role on node {node.id!r}: {role!r}")
        is_topic = (
            node.node_type in TOPIC_TYPES
            and "citations" not in node.id.split("/")[:-1]
            and node.id.rsplit("/", 1)[-1].lower() not in {"readme", "agents", "catalog", "index"}
        )
        if attrs.get("external_mappings") and not is_topic:
            raise ValueError(f"non-concept node {node.id!r} cannot carry SKOS mappings")
        concept_attrs = (
            {key: attrs.pop(key) for key in CONCEPT_ATTRIBUTES if key in attrs} if is_topic else {}
        )
        attrs["entity_role"] = "document"
        nodes.append(NodeRecord(node.id, node.title, node.node_type, attrs))
        if is_topic:
            concept_id = "concept:" + node.id
            if concept_id in ids:
                raise ValueError(f"topic ID collides with a source node: {concept_id!r}")
            topics[node.id] = concept_id
            concept_attrs["entity_role"] = "concept"
            nodes.append(NodeRecord(concept_id, node.title, "topic_concept", concept_attrs))
    edges: list[EdgeRecord] = []
    residual: list[dict[str, str]] = []
    for page, topic in topics.items():
        edges.extend(
            EdgeRecord(page, topic, relation, "entity_model")
            for relation in ("schema:about", "dcterms:subject")
        )
    for edge in document.edges:
        source, target, relation = edge.source, edge.target, edge.relation
        slug = re.sub(r"[^a-z0-9]+", "_", relation.strip().lower()).strip("_")
        if edge.origin not in {"wikilink", "redirect"}:
            conceptual = (
                slug in _RELATED_RELATIONS | _PART_RELATIONS
                or slug in CONCEPT_RELATIONS
                or relation.startswith("skos:")
                or relation.startswith("http://www.w3.org/2004/02/skos/core#")
            )
            if conceptual and source in topics and target in topics:
                source, target = topics[source], topics[target]
                if slug in _PART_RELATIONS:
                    relation = "concept/" + slug
            elif slug in DOCUMENT_RELATION_MEANINGS:
                relation = "document/" + slug
            elif slug not in _DOCUMENT_RELATIONS and slug not in _PART_RELATIONS:
                residual.append({"source": source, "target": target, "relation": relation})
                relation = "document/" + slug
        edges.append(EdgeRecord(source, target, relation, edge.origin))
    metadata = dict(document.metadata, entity_model=ENTITY_MODEL, document_assertions=residual)
    counts = dict(
        metadata.get("counts", {}),
        nodes=len(nodes),
        edges=len(edges),
        documents=sum(n.attributes.get("entity_role") == "document" for n in nodes),
        concepts=len(topics),
    )
    metadata["counts"] = counts
    return GraphDocument(document.name, nodes, edges, metadata)


def _normalise_key(value: str) -> str:
    """Normalise a path key the way the upstream resolver does."""
    return value.replace("\\", "/").strip().lower()


def _node_id_for_path(root_dir: Path, path: Path) -> str:
    """Return the canonical node id for ``path``.

    Node ids are vault-relative POSIX paths sans ``.md`` with spaces
    collapsed to underscores so every id is a valid IRI path fragment
    (e.g. ``systems/Social-Ecological Systems`` →
    ``systems/Social-Ecological_Systems``). Resolution and node building
    both route through this helper, so targets always match ids.
    """

    rel_path = path.relative_to(root_dir).with_suffix("").as_posix()
    return rel_path.replace(" ", "_")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split leading YAML frontmatter off a markdown document.

    Returns ``(metadata, body)``. Documents without a leading ``---`` fence
    return an empty mapping and the untouched text; unparsable YAML blocks
    are reported as empty metadata with the raw text preserved as body so
    that nothing is silently dropped.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        block = "\n".join(lines[1:index])
        body = "\n".join(lines[index + 1 :])
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError:
            return {}, text
        if not isinstance(data, dict):
            return {}, body
        return data, body
    return {}, text


def _extract_wiki_target(inner: str) -> str:
    """Extract the raw target of a wiki-link body (``target|display#frag``)."""
    target = inner.split("|", 1)[0].split("#", 1)[0]
    return target.strip()


def normalise_title(value: Any) -> str:
    """Normalise a frontmatter title; ``[[target|display]]`` → ``display``."""
    if value is None:
        return ""
    text = str(value).strip()
    match = WIKI_LINK_PATTERN.fullmatch(text)
    if not match:
        return text
    inner = match.group(1)
    if "|" in inner:
        return inner.split("|", 1)[1].strip()
    return _extract_wiki_target(inner)


def _flatten_scalars(value: Any) -> list[Any]:
    """Flatten arbitrarily nested lists/tuples to their scalar leaves."""
    if isinstance(value, (list, tuple)):
        flattened: list[Any] = []
        for item in value:
            flattened.extend(_flatten_scalars(item))
        return flattened
    return [value]


def _coerce_link_scalar(value: Any) -> str:
    """Coerce a scalar link entry to a raw target string.

    Handles both quoted wiki-link strings (``[[target|display]]``) and the
    plain scalars YAML produces when it flow-parses an unquoted
    ``[[target|display]]`` entry: the outer brackets are consumed by the
    flow-sequence syntax, leaving ``target|display`` as the scalar, so the
    ``|display`` and ``#fragment`` parts are stripped after flattening too.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    match = WIKI_LINK_PATTERN.fullmatch(text)
    inner = match.group(1) if match else text
    return _extract_wiki_target(inner)


def parse_semantic_relations(links: Any) -> list[tuple[str, str]]:
    """Parse a ``semantic_relations`` frontmatter value.

    ``links`` is the raw YAML value of the ``semantic_relations`` key: a list
    of ``{type: str, links: [...]}`` entries (or ``None``). Returns
    ``(relation, raw_target)`` pairs where the raw target is the unresolved
    target string (wiki-link syntax stripped). Nested YAML lists — including
    the triple-nested ``- - - target`` dialect that parses as
    ``[[['target']]]`` — are flattened recursively to scalar strings.
    Non-standard entry subkeys such as ``parent:`` map to the
    ``has_parent`` relation; other unknown subkeys are ignored.
    """
    pairs: list[tuple[str, str]] = []
    if not isinstance(links, list):
        return pairs
    for entry in links:
        if not isinstance(entry, dict):
            continue
        relation = str(entry.get("type") or DEFAULT_RELATION).strip() or DEFAULT_RELATION
        for scalar in _flatten_scalars(entry.get("links")):
            target = _coerce_link_scalar(scalar)
            if target:
                pairs.append((relation, target))
        for scalar in _flatten_scalars(entry.get("parent")):
            target = _coerce_link_scalar(scalar)
            if target:
                pairs.append((PARENT_RELATION, target))
    return pairs


def extract_wiki_links(text: str) -> list[str]:
    r"""Extract raw wiki-link targets from markdown body text.

    Fenced code blocks (```/~~~) and inline code spans are stripped first;
    candidate links whose full ``[[...]]`` text is a numeric matrix literal
    (``^[\d,\s\[\]\.]+$``) are excluded. Targets are returned in document
    order with the ``|display`` and ``#fragment`` parts removed; duplicates
    are preserved (edge building de-duplicates later).
    """
    if not text:
        return []
    without_blocks = CODE_BLOCK_PATTERN.sub("", text)
    cleaned = INLINE_CODE_PATTERN.sub("", without_blocks)
    targets: list[str] = []
    for match in WIKI_LINK_PATTERN.finditer(cleaned):
        if MATRIX_LITERAL_PATTERN.match(match.group(0)):
            continue
        target = _extract_wiki_target(match.group(1))
        if target:
            targets.append(target)
    return targets


@dataclass(frozen=True)
class _LinkIndex:
    """Resolution index over the markdown vault (port of upstream ``LinkIndex``)."""

    markdown_by_stem: dict[str, list[Path]]
    markdown_by_rel_no_suffix: dict[str, Path]
    all_files_by_rel: frozenset[str]
    markdown_by_alias: dict[str, Path]


def _iter_files(root_dir: Path):
    """Yield every non-ignored file below ``root_dir`` in deterministic order."""
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRECTORIES)
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def _alias_key(value: str) -> str:
    """Normalise a name so ``Free Energy``, ``free_energy`` and ``free-energy`` agree."""
    return " ".join(_normalise_key(value).replace("_", " ").replace("-", " ").split())


def frontmatter_aliases(frontmatter: dict[str, Any]) -> list[str]:
    """Return the ``aliases:`` (or Obsidian's singular ``alias:``) of a page, as strings."""
    names: list[str] = []
    for key in ("aliases", "alias"):
        value = frontmatter.get(key)
        for leaf in _flatten_scalars(value if value is not None else []):
            if isinstance(leaf, (str, int, float)) and str(leaf).strip():
                names.append(str(leaf).strip())
    return names


def _read_frontmatter(path: Path) -> dict[str, Any]:
    """Frontmatter of ``path``; unreadable files yield an empty mapping."""
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8"))[0]
    except (OSError, UnicodeDecodeError):
        return {}


def _build_index(root_dir: Path) -> _LinkIndex:
    """Build the stem / relative-path / alias indexes used for target resolution.

    Every index is filled from pages sorted by lower-cased relative path, so a name
    claimed by several pages resolves to the alphabetically first one.
    """
    markdown: list[Path] = []
    all_files_by_rel: set[str] = set()

    for path in _iter_files(root_dir):
        rel_path = path.relative_to(root_dir)
        all_files_by_rel.add(_normalise_key(rel_path.as_posix()))
        if path.suffix.lower() == ".md":
            markdown.append(rel_path)
    markdown.sort(key=lambda item: _normalise_key(item.as_posix()))

    markdown_by_stem: dict[str, list[Path]] = {}
    markdown_by_rel_no_suffix: dict[str, Path] = {}
    markdown_by_alias: dict[str, Path] = {}
    for rel_path in markdown:
        markdown_by_stem.setdefault(_normalise_key(rel_path.stem), []).append(rel_path)
        markdown_by_rel_no_suffix.setdefault(
            _normalise_key(rel_path.with_suffix("").as_posix()), rel_path
        )
        for alias in frontmatter_aliases(_read_frontmatter(root_dir / rel_path)):
            markdown_by_alias.setdefault(_alias_key(alias), rel_path)

    return _LinkIndex(
        markdown_by_stem=markdown_by_stem,
        markdown_by_rel_no_suffix=markdown_by_rel_no_suffix,
        all_files_by_rel=frozenset(all_files_by_rel),
        markdown_by_alias=markdown_by_alias,
    )


def _has_file_suffix(target: str) -> bool:
    """Return True when the target carries an explicit file-like suffix."""
    return Path(target).suffix.lower() in FILE_LIKE_SUFFIXES


def _candidate_paths(root_dir: Path, source_path: Path, target: str) -> list[Path]:
    """Filesystem candidates for a wiki target (sibling-dir first, then root).

    Candidates that would lexically escape ``root_dir`` (``../``-bearing
    targets pointing outside the vault) are dropped: only in-vault files can
    become knowledge nodes.
    """
    current_dir = source_path.parent
    target = target.replace("\\", "/")

    base_candidates = [
        current_dir / target,
        root_dir / target,
    ]

    candidates: list[Path] = []
    for base in base_candidates:
        candidates.append(base)
        candidates.append(base / "README.md")
        candidates.append(base / "index.md")
        if not _has_file_suffix(target):
            candidates.append(base.with_suffix(".md"))
    return [
        candidate
        for candidate in candidates
        if Path(os.path.normpath(candidate)).is_relative_to(root_dir)
    ]


def _normalised_relative_candidate(
    root_dir: Path,
    source_path: Path,
    target: str,
    index: _LinkIndex,
) -> Path | None:
    """Resolve a ``./``/``../``-bearing target against the source directory.

    Relative wiki targets are normalised against the source file's directory
    (``posixpath.normpath`` of the source-relative directory joined with the
    target); ``..`` segments that would escape the vault root are clamped to
    the root. When the normalised, vault-absolute path exists in the index it
    wins immediately; otherwise ``None`` falls through to the standard ladder.
    """
    posix_target = target.replace("\\", "/")
    if "./" not in posix_target and not posix_target.startswith(".."):
        return None
    try:
        rel_dir = source_path.parent.relative_to(root_dir).as_posix()
    except ValueError:
        rel_dir = "."
    joined = posixpath.normpath(posixpath.join(rel_dir, posix_target))
    while joined.startswith("../"):
        joined = joined[3:]
    if not joined or joined == ".":
        return None
    norm_key = _normalise_key(joined)
    if norm_key in index.all_files_by_rel:
        return root_dir / joined
    if norm_key + ".md" in index.all_files_by_rel:
        return root_dir / (joined + ".md")
    if norm_key in index.markdown_by_rel_no_suffix:
        return index.markdown_by_rel_no_suffix[norm_key]
    return None


def _resolve_target_path(
    root_dir: Path,
    source_path: Path,
    target: str,
    index: _LinkIndex,
) -> Path | None:
    """Resolve a wiki target to a file path, or ``None`` (upstream order).

    ``./``/``../``-bearing targets are first normalised against the source
    directory (see :func:`_normalised_relative_candidate`). Remaining order:
    sibling-dir relative → repo-root relative (each also tried with a
    ``README.md`` / ``index.md`` child and a ``.md`` suffix) → exact
    repository-relative path → relative path without suffix → stem index
    (first match alphabetically on duplicate stems) → frontmatter ``aliases:``
    (first match alphabetically on duplicate aliases).
    """
    relative = _normalised_relative_candidate(root_dir, source_path, target, index)
    if relative is not None:
        return relative

    seen: set[str] = set()
    for candidate in _candidate_paths(root_dir, source_path, target):
        key = _normalise_key(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate

    rel_key = _normalise_key(target)
    if rel_key in index.all_files_by_rel:
        return root_dir / target

    if rel_key in index.markdown_by_rel_no_suffix:
        return index.markdown_by_rel_no_suffix[rel_key]

    if _has_file_suffix(target):
        return None

    stem_key = _normalise_key(Path(target).stem)
    matches = index.markdown_by_stem.get(stem_key, [])
    if matches:
        return root_dir / matches[0]
    aliased = index.markdown_by_alias.get(_alias_key(target))
    return root_dir / aliased if aliased is not None else None


def _resolve_node_id(
    root_dir: Path,
    source_path: Path,
    target: str,
    index: _LinkIndex,
) -> str | None:
    """Resolve a wiki target to a node id (vault-relative path sans ``.md``).

    Only markdown files become knowledge nodes, so a resolution that lands
    on any other file type is treated as unresolvable.
    """
    resolved = _resolve_target_path(root_dir, source_path, target, index)
    if resolved is None:
        return None
    if resolved.suffix.lower() != ".md":
        return None
    try:
        return _node_id_for_path(root_dir, resolved)
    except ValueError:
        return None


def _redirect_target(frontmatter: dict[str, Any]) -> str:
    """Extract the raw redirect target from a ``type: redirect`` node."""
    value = frontmatter.get("redirect")
    if value is None:
        return ""
    text = str(value).strip()
    match = WIKI_LINK_PATTERN.fullmatch(text)
    if match:
        return _extract_wiki_target(match.group(1))
    return text


def _coerce_attribute_value(value: Any) -> Any:
    """Coerce frontmatter scalars (YAML dates) to JSON-serialisable values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_coerce_attribute_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _coerce_attribute_value(item) for key, item in value.items()}
    return value


def _node_record_for(path: Path, root_dir: Path, frontmatter: dict[str, Any]) -> NodeRecord:
    """Build a :class:`NodeRecord` for one markdown file."""
    node_id = _node_id_for_path(root_dir, path)
    node_type = str(frontmatter.get("type") or "").strip()
    if not node_type:
        node_type = DOCUMENT_NODE_TYPES.get(
            path.name.lower(), "concept" if frontmatter.get("external_mappings") else "document"
        )

    attributes: dict[str, Any] = {}
    for key in ("status", "created", "updated", "modified", "processing_priority"):
        value = frontmatter.get(key)
        if value is not None:
            attributes[key] = _coerce_attribute_value(value)
    for key in ("tags", "authors"):
        value = frontmatter.get(key)
        if value is not None:
            attributes[key] = [
                _coerce_attribute_value(item)
                for item in (value if isinstance(value, list) else [value])
            ]
    aliases = frontmatter_aliases(frontmatter)
    if aliases:
        attributes["aliases"] = aliases
    for key in (
        "description",
        "complexity",
        "year",
        "journal",
        "doi",
        "wikidata",
        "definition",
        "scope_note",
        "source",
        "license",
    ):
        value = frontmatter.get(key)
        if value is not None and str(value).strip():
            attributes[key] = _coerce_attribute_value(value)

    if "external_mappings" in frontmatter:
        attributes["external_mappings"] = _coerce_attribute_value(frontmatter["external_mappings"])

    title = normalise_title(frontmatter.get("title")) or node_id
    redirect = _redirect_target(frontmatter)
    if redirect:
        attributes["redirect"] = redirect
    return NodeRecord(id=node_id, title=title, node_type=node_type, attributes=attributes)


def build_cognitive_graph(
    kb_root: Path,
    *,
    collapse_redirects: bool = True,
    include_wikilinks: bool = True,
    name: str = GRAPH_NAME,
) -> GraphDocument:
    """Parse an Obsidian-style markdown vault into a :class:`GraphDocument`.

    ``kb_root`` is the markdown vault root (for the ``cognitive`` repository,
    its ``knowledge_base/`` directory); ``name`` becomes the graph name
    (default ``cognitive-kb``). Every ``.md`` file becomes a node with
    id = vault-relative POSIX path sans ``.md``. Topic records have distinct
    ``concept:<path>`` IDs and explicit about/subject edges. ``semantic_relations``
    frontmatter edges use ``origin='explicit'``, body wiki-links use
    ``origin='wikilink'`` (untyped ``related`` relation), and redirect nodes
    emit ``redirects_to`` edges. With ``collapse_redirects=True`` redirect
    nodes are removed and incident edges rewritten through their target.
    Relative (``./``/``../``) targets are normalised against the source
    file's directory before node-id lookup. Self-loop edges are dropped in
    both redirect modes and their source node ids recorded under
    ``metadata['self_loop_edges']`` (counted in ``metadata['counts']``).
    Unresolvable targets are recorded under
    ``metadata['unresolved_targets']`` as ``{source, target, origin}``
    entries rather than dropped. Unknown or mixed-role semantic assertions stay
    document-valued and are listed in ``metadata['document_assertions']``.
    """
    root = Path(kb_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"knowledge base root does not exist: {root}")

    index = _build_index(root)
    nodes: list[NodeRecord] = []
    edges: list[EdgeRecord] = []
    unresolved: list[dict[str, str]] = []
    redirect_map: dict[str, str] = {}
    file_count = 0

    for path in _iter_files(root):
        if path.suffix.lower() != ".md":
            continue
        file_count += 1
        frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        record = _node_record_for(path, root, frontmatter)
        source_id = record.id
        nodes.append(record)

        def _add_link(
            target: str,
            relation: str,
            origin: str,
            _path: Path = path,
            _source: str = source_id,
        ) -> None:
            resolved = _resolve_node_id(root, _path, target, index)
            if resolved is None:
                unresolved.append({"source": _source, "target": target, "origin": origin})
                return
            edges.append(
                EdgeRecord(source=_source, target=resolved, relation=relation, origin=origin)
            )

        for relation, target in parse_semantic_relations(frontmatter.get("semantic_relations")):
            _add_link(target, relation, "explicit")

        if include_wikilinks:
            for target in extract_wiki_links(body):
                _add_link(target, WIKILINK_RELATION, "wikilink")

        if record.node_type == "redirect":
            redirect_target = _redirect_target(frontmatter)
            if redirect_target:
                resolved = _resolve_node_id(root, path, redirect_target, index)
                if resolved is not None:
                    redirect_map[source_id] = resolved
                    if not collapse_redirects:
                        edges.append(
                            EdgeRecord(
                                source=source_id,
                                target=resolved,
                                relation=REDIRECT_RELATION,
                                origin="redirect",
                            )
                        )
                else:
                    unresolved.append(
                        {
                            "source": source_id,
                            "target": redirect_target,
                            "origin": "redirect",
                        }
                    )

    removed: set[str] = set()
    if collapse_redirects and redirect_map:
        removed = set(redirect_map)
        rewritten: list[EdgeRecord] = []
        for edge in edges:
            source = redirect_map.get(edge.source, edge.source)
            target = redirect_map.get(edge.target, edge.target)
            if source == target and (edge.source in removed or edge.target in removed):
                continue
            rewritten.append(
                EdgeRecord(
                    source=source,
                    target=target,
                    relation=edge.relation,
                    origin=edge.origin,
                )
            )
        edges = rewritten
    if removed:
        nodes = [node for node in nodes if node.id not in removed]

    deduped: list[EdgeRecord] = []
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        key = (edge.source, edge.target, edge.relation, edge.origin)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    edges = deduped
    self_loop_nodes: set[str] = set()
    kept_edges: list[EdgeRecord] = []
    for edge in edges:
        if edge.source == edge.target:
            self_loop_nodes.add(edge.source)
            continue
        kept_edges.append(edge)
    edges = kept_edges

    counts = {
        "nodes": len(nodes),
        "edges": len(edges),
        "files": file_count,
        "semantic_edges": sum(1 for edge in edges if edge.origin == "explicit"),
        "wikilink_edges": sum(1 for edge in edges if edge.origin == "wikilink"),
        "redirect_edges": sum(1 for edge in edges if edge.origin == "redirect"),
        "unresolved_targets": len(unresolved),
        "self_loop_edges": len(self_loop_nodes),
    }
    metadata = {
        "counts": counts,
        "unresolved_targets": unresolved,
        "self_loop_edges": sorted(self_loop_nodes),
        "vault_name": root.name,
    }
    return separate_document_topics(
        GraphDocument(name=name, nodes=nodes, edges=edges, metadata=metadata)
    )


def vault_root(path: Path) -> Path:
    """Return the vault directory for ``path``.

    A ``cognitive`` repository checkout (it has a ``knowledge_base/`` directory) maps to
    that directory; any other directory is itself the vault.
    """
    path = Path(path)
    nested = path / "knowledge_base"
    return nested if nested.is_dir() else path


def default_graph_name(path: Path) -> str:
    """Name for the graph read from ``path``.

    A ``cognitive`` checkout (it has a ``knowledge_base/`` directory) is ``cognitive-kb``;
    any other vault is named after its directory, as a registry-style slug.
    """
    path = Path(path)
    if (path / "knowledge_base").is_dir():
        return GRAPH_NAME
    slug = re.sub(r"[^a-z0-9]+", "-", path.resolve().name.lower()).strip("-")
    return slug or "vault"


def export_cognitive_kb(repo_root: Path, out_path: Path, **opts: Any) -> GraphDocument:
    """Export the knowledge base at ``repo_root`` to JSON.

    ``repo_root`` is a ``cognitive`` repository root (its ``knowledge_base/``
    directory is parsed) or any markdown vault directory; ``out_path`` receives
    ``GraphDocument.save_json``. Remaining keyword options (``collapse_redirects``,
    ``include_wikilinks``, ``name``) pass through to :func:`build_cognitive_graph`.
    """
    document = build_cognitive_graph(vault_root(Path(repo_root)), **opts)
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save_json(destination)
    return document
