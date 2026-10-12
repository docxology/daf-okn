"""Tests for the OKN registry/query client.

Pure parse helpers are exercised with inline fixture strings; the
:class:`OKNRegistry` methods run against a stub ``requests.Session``-alike
that records calls and returns canned responses. No test performs real
network I/O.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from daf_okn.core.registry import (
    DEFAULT_TIMEOUT,
    EMBEDDINGS_QUERY,
    FEDERATION_SPARQL,
    KGS_YAML_URL,
    NAMED_GRAPH_TEMPLATE,
    PER_GRAPH_SPARQL_TEMPLATE,
    TPF_TEMPLATE,
    VOID_SPARQL,
    OKNRegistry,
    RegistryError,
    local_name,
    named_graph_iri,
    parse_kgs_yaml,
    parse_sparql_json,
)

SPARQL_QUERY = "SELECT * WHERE { ?s ?p ?o } LIMIT 2"

SPARQL_JSON = json.dumps(
    {
        "head": {"vars": ["s", "p", "o"]},
        "results": {
            "bindings": [
                {
                    "s": {
                        "type": "uri",
                        "value": "https://purl.org/okn/frink/kg/biohealth",
                    },
                    "p": {
                        "type": "uri",
                        "value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    },
                    "o": {
                        "type": "uri",
                        "value": "https://purl.org/okn/frink/kg/void#Graph",
                    },
                },
                {
                    "s": {
                        "type": "uri",
                        "value": "https://purl.org/okn/frink/kg/biohealth",
                    },
                    "p": {
                        "type": "uri",
                        "value": "http://www.w3.org/2000/01/rdf-schema#label",
                    },
                    "o": {
                        "type": "literal",
                        "value": "Bio-Health KG",
                        "xml:lang": "en",
                    },
                },
            ]
        },
    }
)

KGS_YAML = """\
kgs:
  - shortname: biohealth
    title: Bio-Health KG
    description: Dynamically-updated open knowledge network for health.
    sparql: https://apps.okn.us/biohealth/sparql
    tpf: https://apps.okn.us/ldf/biohealth
    frink-options:
      lakefs-repo: biohealth
      documentation-path: biohealth
  - shortname: okn-void
    title: OKN VoID graph descriptions
    description: Collected VoID metadata for all OKN graphs.
    sparql: https://apps.okn.us/okn-void/sparql
    tpf: https://apps.okn.us/ldf/okn-void
"""

TPF_BODY = (
    "@prefix hydra: <http://www.w3.org/ns/hydra/core#> .\n"
    "@prefix void: <http://rdfs.org/ns/void#> .\n"
    "<https://apps.okn.us/ldf/spoke-okn> hydra:next <...page-2> .\n"
)


class StubResponse:
    """Minimal stand-in for ``requests.Response``.

    When ``json_data`` is left as ``None`` the ``json()`` call raises
    ``ValueError``, mirroring how ``requests`` behaves on a non-JSON body
    (``requests.exceptions.JSONDecodeError`` subclasses ``ValueError``).
    """

    def __init__(
        self,
        status_code: int = 200,
        json_data: object | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self) -> object:
        if self._json_data is None:
            raise ValueError("no JSON payload configured")
        return self._json_data


class StubSession:
    """Minimal stand-in for ``requests.Session`` that records every call.

    Responses are consumed in order; an unexpected extra call raises
    ``AssertionError`` so tests fail loudly instead of silently passing.
    """

    def __init__(self, responses: list[StubResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> StubResponse:
        self.calls.append(
            {
                "method": "GET",
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self._next()

    def post(
        self,
        url: str,
        json: object | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> StubResponse:
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self._next()

    def _next(self) -> StubResponse:
        if not self.responses:
            raise AssertionError("unexpected additional HTTP call")
        return self.responses.pop(0)


def make_registry(*responses: StubResponse) -> tuple[OKNRegistry, StubSession]:
    """Build an ``OKNRegistry`` wired to a stub session with canned responses."""
    session = StubSession(list(responses))
    return OKNRegistry(session=session, timeout=5.0), session


class TestConstants:
    """The endpoint constants match the documented OKN URLs."""

    def test_federation_sparql(self) -> None:
        assert FEDERATION_SPARQL == "https://apps.okn.us/federation/sparql"

    def test_void_sparql(self) -> None:
        assert VOID_SPARQL == "https://apps.okn.us/okn-void/sparql"

    def test_kgs_yaml_url(self) -> None:
        assert KGS_YAML_URL == (
            "https://raw.githubusercontent.com/frink-okn/okn-registry/main/docs/registry/kgs.yaml"
        )

    def test_per_graph_sparql_template(self) -> None:
        assert PER_GRAPH_SPARQL_TEMPLATE.format(shortname="biohealth") == (
            "https://apps.okn.us/biohealth/sparql"
        )

    def test_tpf_template(self) -> None:
        assert TPF_TEMPLATE.format(shortname="spoke-okn") == "https://apps.okn.us/ldf/spoke-okn"

    def test_embeddings_query(self) -> None:
        assert EMBEDDINGS_QUERY == "https://apps.okn.us/embeddings/query"

    def test_default_timeout(self) -> None:
        assert DEFAULT_TIMEOUT == 30.0


class TestNamedGraphIri:
    """The named-graph IRI helper mirrors api-notes §2.2."""

    def test_formats_shortname(self) -> None:
        assert named_graph_iri("ubergraph") == "https://purl.org/okn/frink/kg/ubergraph"

    def test_matches_template_constant(self) -> None:
        assert named_graph_iri("biohealth") == NAMED_GRAPH_TEMPLATE.format(shortname="biohealth")


class TestLocalName:
    """``local_name`` strips the namespace off an IRI."""

    @pytest.mark.parametrize(
        ("iri", "expected"),
        [
            ("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "type"),
            ("https://purl.org/okn/frink/kg/biohealth", "biohealth"),
            ("https://example.org/path/to/thing", "thing"),
            ("plainword", "plainword"),
            ("https://example.org/", ""),
        ],
    )
    def test_local_parts(self, iri: str, expected: str) -> None:
        assert local_name(iri) == expected

    def test_fragment_beats_path_separator(self) -> None:
        assert local_name("https://example.org/a/b#term") == "term"


class TestParseSparqlJson:
    """``parse_sparql_json`` validates and returns the binding rows."""

    def test_returns_bindings(self) -> None:
        payload = json.loads(SPARQL_JSON)
        assert parse_sparql_json(payload) == payload["results"]["bindings"]

    def test_empty_bindings(self) -> None:
        assert parse_sparql_json({"head": {"vars": []}, "results": {"bindings": []}}) == []

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            "not a dict",
            {"head": {"vars": ["s"]}},
            {"results": []},
            {"results": {}},
            {"results": {"bindings": "nope"}},
            {"results": {"bindings": [42]}},
            {"results": {"bindings": [{"s": {"type": "uri"}}]}},
        ],
    )
    def test_malformed_payloads_raise(self, payload: object) -> None:
        with pytest.raises(RegistryError):
            parse_sparql_json(payload)

    def test_ask_style_payload_raises(self) -> None:
        # ASK results are legal SPARQL JSON but carry no bindings to parse.
        with pytest.raises(RegistryError, match="missing 'results'"):
            parse_sparql_json({"head": {"vars": []}, "boolean": True})


class TestParseKgsYaml:
    """``parse_kgs_yaml`` validates the registry metadata mapping."""

    def test_parses_graph_entries(self) -> None:
        parsed = parse_kgs_yaml(KGS_YAML)
        assert isinstance(parsed, dict)
        assert [entry["shortname"] for entry in parsed["kgs"]] == [
            "biohealth",
            "okn-void",
        ]
        biohealth = parsed["kgs"][0]
        assert biohealth["title"] == "Bio-Health KG"
        assert biohealth["sparql"] == "https://apps.okn.us/biohealth/sparql"
        assert biohealth["frink-options"]["lakefs-repo"] == "biohealth"

    def test_malformed_yaml_raises(self) -> None:
        with pytest.raises(RegistryError, match="malformed kgs.yaml"):
            parse_kgs_yaml("kgs: [biohealth, okn-void")

    def test_top_level_list_raises(self) -> None:
        with pytest.raises(RegistryError, match="not a mapping"):
            parse_kgs_yaml("- biohealth\n- okn-void\n")

    def test_missing_kgs_key_raises(self) -> None:
        with pytest.raises(RegistryError, match="missing 'kgs'"):
            parse_kgs_yaml("title: not a registry\n")

    def test_non_mapping_entry_raises(self) -> None:
        with pytest.raises(RegistryError, match="entry is not a mapping"):
            parse_kgs_yaml("kgs:\n  - 1\n  - 2\n")


class TestOKNRegistrySparql:
    """``sparql`` targets the right endpoint and enforces the error contract."""

    def test_per_graph_request(self) -> None:
        registry, session = make_registry(StubResponse(json_data=json.loads(SPARQL_JSON)))
        payload = registry.sparql(SPARQL_QUERY, shortname="spoke-okn")
        assert payload["head"]["vars"] == ["s", "p", "o"]
        call = session.calls[0]
        assert call["method"] == "GET"
        assert call["url"] == "https://apps.okn.us/spoke-okn/sparql"
        assert call["params"] == {"query": SPARQL_QUERY}
        assert call["headers"] == {"Accept": "application/sparql-results+json"}
        assert call["timeout"] == 5.0

    def test_federation_target(self) -> None:
        registry, session = make_registry(StubResponse(json_data=json.loads(SPARQL_JSON)))
        registry.sparql(SPARQL_QUERY, federation=True)
        assert session.calls[0]["url"] == FEDERATION_SPARQL

    def test_void_target(self) -> None:
        registry, session = make_registry(StubResponse(json_data=json.loads(SPARQL_JSON)))
        registry.sparql(SPARQL_QUERY, void=True)
        assert session.calls[0]["url"] == VOID_SPARQL

    def test_shortname_takes_precedence(self) -> None:
        registry, session = make_registry(StubResponse(json_data=json.loads(SPARQL_JSON)))
        registry.sparql(SPARQL_QUERY, shortname="biohealth", federation=True)
        assert session.calls[0]["url"] == "https://apps.okn.us/biohealth/sparql"

    def test_federation_and_void_conflict(self) -> None:
        registry, _ = make_registry()
        with pytest.raises(ValueError, match="mutually exclusive"):
            registry.sparql(SPARQL_QUERY, federation=True, void=True)

    def test_no_target_raises(self) -> None:
        registry, _ = make_registry()
        with pytest.raises(ValueError, match="query target"):
            registry.sparql(SPARQL_QUERY)

    @pytest.mark.parametrize("status", [400, 404, 500])
    def test_http_errors_raise(self, status: int) -> None:
        registry, _ = make_registry(StubResponse(status_code=status))
        with pytest.raises(RegistryError) as excinfo:
            registry.sparql(SPARQL_QUERY, shortname="spoke-okn")
        assert excinfo.value.status == status
        assert str(status) in str(excinfo.value)

    def test_malformed_json_raises(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=200))
        with pytest.raises(RegistryError, match="malformed JSON"):
            registry.sparql(SPARQL_QUERY, shortname="spoke-okn")

    def test_non_object_json_raises(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=200, json_data=[1, 2]))
        with pytest.raises(RegistryError, match="JSON object"):
            registry.sparql(SPARQL_QUERY, shortname="spoke-okn")


class TestOKNRegistryRows:
    """``sparql_rows`` flattens validated bindings to ``{var: value}`` rows."""

    def test_flattened_rows(self) -> None:
        registry, _ = make_registry(StubResponse(json_data=json.loads(SPARQL_JSON)))
        rows = registry.sparql_rows(SPARQL_QUERY, shortname="spoke-okn")
        assert rows == [
            {
                "s": "https://purl.org/okn/frink/kg/biohealth",
                "p": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                "o": "https://purl.org/okn/frink/kg/void#Graph",
            },
            {
                "s": "https://purl.org/okn/frink/kg/biohealth",
                "p": "http://www.w3.org/2000/01/rdf-schema#label",
                "o": "Bio-Health KG",
            },
        ]

    def test_malformed_binding_raises(self) -> None:
        payload = {"results": {"bindings": [{"s": {"type": "uri"}}]}}
        registry, _ = make_registry(StubResponse(json_data=payload))
        with pytest.raises(RegistryError, match="no 'value'"):
            registry.sparql_rows(SPARQL_QUERY, shortname="spoke-okn")


class TestOKNRegistryGraphs:
    """``list_graphs`` / ``get_graph`` fetch and index the registry metadata."""

    def test_list_graphs_from_network(self) -> None:
        registry, session = make_registry(StubResponse(text=KGS_YAML))
        graphs = registry.list_graphs()
        assert [entry["shortname"] for entry in graphs] == ["biohealth", "okn-void"]
        call = session.calls[0]
        assert call["url"] == KGS_YAML_URL
        assert call["timeout"] == 5.0

    def test_list_graphs_local_path_override(self, tmp_path: Path) -> None:
        local = tmp_path / "kgs.yaml"
        local.write_text(KGS_YAML, encoding="utf-8")
        registry, session = make_registry()  # no canned responses: any HTTP call fails
        graphs = registry.list_graphs(kgs_path=str(local))
        assert len(graphs) == 2
        assert session.calls == []

    def test_list_graphs_http_error(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=500))
        with pytest.raises(RegistryError) as excinfo:
            registry.list_graphs()
        assert excinfo.value.status == 500

    def test_list_graphs_malformed_yaml(self) -> None:
        registry, _ = make_registry(StubResponse(text="kgs: [biohealth"))
        with pytest.raises(RegistryError, match="malformed kgs.yaml"):
            registry.list_graphs()

    def test_get_graph_found(self) -> None:
        registry, _ = make_registry(StubResponse(text=KGS_YAML))
        entry = registry.get_graph("okn-void")
        assert entry["title"] == "OKN VoID graph descriptions"
        assert entry["tpf"] == "https://apps.okn.us/ldf/okn-void"

    def test_get_graph_unknown_shortname(self) -> None:
        registry, _ = make_registry(StubResponse(text=KGS_YAML))
        with pytest.raises(RegistryError, match="not found"):
            registry.get_graph("no-such-graph")


class TestOKNRegistryTpf:
    """``tpf`` sends only the provided triple-pattern arguments."""

    def test_predicate_only_fragment(self) -> None:
        registry, session = make_registry(StubResponse(text=TPF_BODY))
        body = registry.tpf(
            "spoke-okn", predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        )
        assert body.startswith("@prefix hydra:")
        call = session.calls[0]
        assert call["url"] == "https://apps.okn.us/ldf/spoke-okn"
        assert call["params"] == {"predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"}
        assert call["headers"] == {"Accept": "application/trig"}

    def test_all_three_patterns(self) -> None:
        registry, session = make_registry(StubResponse(text=TPF_BODY))
        subject = "https://purl.org/okn/frink/kg/biohealth"
        obj = "https://purl.org/okn/frink/kg/void#Graph"
        registry.tpf("spoke-okn", subject=subject, predicate="http://ex.org/p", object=obj)
        assert session.calls[0]["params"] == {
            "subject": subject,
            "predicate": "http://ex.org/p",
            "object": obj,
        }

    def test_no_patterns_returns_full_graph_pages(self) -> None:
        registry, session = make_registry(StubResponse(text=TPF_BODY))
        registry.tpf("spoke-okn")
        assert session.calls[0]["params"] == {}

    def test_custom_accept_header(self) -> None:
        registry, session = make_registry(StubResponse(text=TPF_BODY))
        registry.tpf("spoke-okn", accept="text/turtle")
        assert session.calls[0]["headers"] == {"Accept": "text/turtle"}

    def test_http_error_raises(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=404))
        with pytest.raises(RegistryError) as excinfo:
            registry.tpf("spoke-okn")
        assert excinfo.value.status == 404


class TestOKNRegistryEmbeddings:
    """``embedding_search`` POSTs the documented ``Query`` body shape."""

    def test_defaults(self) -> None:
        registry, session = make_registry(StubResponse(json_data={"results": []}))
        payload = registry.embedding_search("text", "brains")
        assert payload == {"results": []}
        call = session.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == EMBEDDINGS_QUERY
        assert call["json"] == {
            "feature": {"type": "text", "value": "brains"},
            "limit": 10,
            "offset": 0,
        }
        assert call["timeout"] == 5.0

    def test_node_feature_and_limit(self) -> None:
        registry, session = make_registry(StubResponse(json_data={"results": []}))
        registry.embedding_search("node", "https://example.org/thing", limit=3, offset=6)
        assert session.calls[0]["json"] == {
            "feature": {"type": "node", "value": "https://example.org/thing"},
            "limit": 3,
            "offset": 6,
        }

    def test_include_graphs(self) -> None:
        registry, session = make_registry(StubResponse(json_data={"results": []}))
        registry.embedding_search("text", "brains", include_graphs=["spoke-okn"])
        assert session.calls[0]["json"]["include_graphs"] == ["spoke-okn"]
        assert "exclude_graphs" not in session.calls[0]["json"]

    def test_exclude_graphs(self) -> None:
        registry, session = make_registry(StubResponse(json_data={"results": []}))
        registry.embedding_search("text", "brains", exclude_graphs=["wikidata", "ubergraph"])
        assert session.calls[0]["json"]["exclude_graphs"] == ["wikidata", "ubergraph"]
        assert "include_graphs" not in session.calls[0]["json"]

    def test_include_and_exclude_conflict(self) -> None:
        registry, _ = make_registry()
        with pytest.raises(ValueError, match="only one"):
            registry.embedding_search("text", "brains", include_graphs=["a"], exclude_graphs=["b"])

    def test_unknown_feature_type(self) -> None:
        registry, _ = make_registry()
        with pytest.raises(ValueError, match="feature_type"):
            registry.embedding_search("image", "brains")

    def test_http_error_raises(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=502))
        with pytest.raises(RegistryError) as excinfo:
            registry.embedding_search("text", "brains")
        assert excinfo.value.status == 502

    def test_malformed_json_raises(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=200))
        with pytest.raises(RegistryError, match="malformed JSON"):
            registry.embedding_search("text", "brains")

    def test_non_object_json_raises(self) -> None:
        registry, _ = make_registry(StubResponse(status_code=200, json_data=["results"]))
        with pytest.raises(RegistryError, match="JSON object"):
            registry.embedding_search("text", "brains")


class TestSessionLaziness:
    """The default ``requests.Session`` is created lazily and cached."""

    def test_default_session_created_on_first_use(self) -> None:
        registry = OKNRegistry()
        assert registry.session is None
        session = registry._session()
        assert isinstance(session, requests.Session)
        assert registry.session is session

    def test_default_timeout(self) -> None:
        assert OKNRegistry().timeout == DEFAULT_TIMEOUT

    def test_injected_session_is_reused(self) -> None:
        stub = StubSession([])
        registry = OKNRegistry(session=stub)
        assert registry._session() is stub
