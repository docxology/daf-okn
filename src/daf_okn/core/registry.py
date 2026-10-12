"""Client for the Open Knowledge Network (OKN) registry and query services.

Endpoint and payload facts come from ``docs/okn/api-notes.md`` (§1–§7, §11,
live-verified 2026-09-25):

* per-graph SPARQL: ``https://apps.okn.us/{shortname}/sparql`` (§2.1) —
  standard SPARQL 1.1 JSON results (``head.vars`` / ``results.bindings``)
* cross-OKN federation SPARQL: ``https://apps.okn.us/federation/sparql``
  (§2.2), scoped with named-graph IRIs ``https://purl.org/okn/frink/kg/{shortname}``
* VoID statistics SPARQL: ``https://apps.okn.us/okn-void/sparql`` (§2.3)
* per-graph TPF: ``https://apps.okn.us/ldf/{shortname}`` with ``subject`` /
  ``predicate`` / ``object`` query arguments (§3); the documented example
  requests ``Accept: application/trig``
* embeddings JSON API: ``POST https://apps.okn.us/embeddings/query`` with a
  body whose ``feature`` is a discriminated union on ``type`` (``text`` or
  ``node``) and where only one of ``include_graphs`` / ``exclude_graphs`` may
  be set (§5.2)
* registry metadata: ``kgs.yaml`` (§7) — a YAML mapping with a top-level
  ``kgs:`` list of graph entries (``shortname``, ``title``, ``description``,
  ``sparql``, ``tpf``, ``stats``, ``funding``, ``contact``, ``frink-options``)

The module performs no I/O at import time: network access happens only inside
:class:`OKNRegistry` methods, through an injected :class:`requests.Session`
(created lazily when omitted) with a per-request ``timeout``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml

__all__ = [
    "DEFAULT_TIMEOUT",
    "EMBEDDINGS_QUERY",
    "FEDERATION_SPARQL",
    "KGS_YAML_URL",
    "NAMED_GRAPH_TEMPLATE",
    "OKNRegistry",
    "PER_GRAPH_SPARQL_TEMPLATE",
    "RegistryError",
    "TPF_TEMPLATE",
    "VOID_SPARQL",
    "local_name",
    "named_graph_iri",
    "parse_kgs_yaml",
    "parse_sparql_json",
]

#: Cross-OKN federation SPARQL endpoint (api-notes §2.2).
FEDERATION_SPARQL = "https://apps.okn.us/federation/sparql"

#: VoID statistics SPARQL endpoint (api-notes §2.3).
VOID_SPARQL = "https://apps.okn.us/okn-void/sparql"

#: Raw ``kgs.yaml`` registry metadata file (api-notes §7).
KGS_YAML_URL = (
    "https://raw.githubusercontent.com/frink-okn/okn-registry/main/docs/registry/kgs.yaml"
)

#: Per-graph SPARQL endpoint pattern (api-notes §2.1).
PER_GRAPH_SPARQL_TEMPLATE = "https://apps.okn.us/{shortname}/sparql"

#: Per-graph TPF endpoint pattern (api-notes §3).
TPF_TEMPLATE = "https://apps.okn.us/ldf/{shortname}"

#: Embeddings JSON API route, POST-only (api-notes §5.2).
EMBEDDINGS_QUERY = "https://apps.okn.us/embeddings/query"

#: Federation named-graph IRI pattern (api-notes §2.2).
NAMED_GRAPH_TEMPLATE = "https://purl.org/okn/frink/kg/{shortname}"

#: ``Accept`` header value for SPARQL JSON results (api-notes §2.1).
SPARQL_JSON_ACCEPT = "application/sparql-results+json"

#: Default ``Accept`` for TPF fragments — the documented example uses Trig (api-notes §3).
TRIG_ACCEPT = "application/trig"

#: Default per-request timeout in seconds.
DEFAULT_TIMEOUT = 30.0

#: Documented embeddings feature types — the ``feature`` discriminated union (api-notes §5.2).
FEATURE_TYPES = ("text", "node")


class RegistryError(Exception):
    """Raised when an OKN endpoint fails (HTTP >= 400) or returns malformed data.

    Attributes:
        message: Human-readable description of the failure.
        status: HTTP status code when the error came from an HTTP response,
            ``None`` for malformed-payload errors.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def local_name(iri: str) -> str:
    """Return the local part of an IRI (text after the last ``#`` or ``/``).

    Args:
        iri: Full IRI, e.g. ``http://www.w3.org/1999/02/22-rdf-syntax-ns#type``.

    Returns:
        The trailing local name; an IRI without either separator is returned
        unchanged, and a trailing separator yields the empty string.
    """
    cut = max(iri.rfind("#"), iri.rfind("/"))
    if cut == -1:
        return iri
    return iri[cut + 1 :]


def named_graph_iri(shortname: str) -> str:
    """Return the federation named-graph IRI for ``shortname`` (api-notes §2.2).

    Args:
        shortname: Registry shortname, e.g. ``ubergraph``.

    Returns:
        The IRI used in ``FROM <...>`` clauses against the federation endpoint.
    """
    return NAMED_GRAPH_TEMPLATE.format(shortname=shortname)


def parse_sparql_json(payload: Any) -> list[dict[str, Any]]:
    """Extract and validate the ``results.bindings`` of a SPARQL JSON result.

    Args:
        payload: Parsed SPARQL JSON (``head.vars`` / ``results.bindings``);
            each binding maps a variable name to a term object with at least a
            ``value`` key.

    Returns:
        The raw binding rows (one dict per result row).

    Raises:
        RegistryError: If the payload is not a SPARQL JSON results document.
    """
    if not isinstance(payload, dict):
        raise RegistryError("malformed SPARQL JSON: top-level payload is not an object")
    results = payload.get("results")
    if not isinstance(results, dict):
        raise RegistryError("malformed SPARQL JSON: missing 'results' object")
    bindings = results.get("bindings")
    if not isinstance(bindings, list):
        raise RegistryError("malformed SPARQL JSON: 'results.bindings' is not a list")
    for row in bindings:
        if not isinstance(row, dict):
            raise RegistryError("malformed SPARQL JSON: binding row is not an object")
        for name, term in row.items():
            if not isinstance(term, dict) or "value" not in term:
                raise RegistryError(
                    f"malformed SPARQL JSON: term for variable {name!r} has no 'value'"
                )
    return bindings


def parse_kgs_yaml(raw: str) -> dict[str, Any]:
    """Parse ``kgs.yaml`` registry metadata into its top-level mapping.

    The upstream file is a YAML mapping with a ``kgs:`` list of graph entries
    (api-notes §7); each entry must itself be a mapping.

    Args:
        raw: Raw YAML text of the registry metadata file.

    Returns:
        The parsed top-level mapping (read the graph list from ``["kgs"]``).

    Raises:
        RegistryError: If the YAML is unparseable or has an unexpected shape.
    """
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise RegistryError(f"malformed kgs.yaml: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RegistryError("malformed kgs.yaml: top-level document is not a mapping")
    kgs = parsed.get("kgs")
    if not isinstance(kgs, list):
        raise RegistryError("malformed kgs.yaml: missing 'kgs' list")
    for entry in kgs:
        if not isinstance(entry, dict):
            raise RegistryError("malformed kgs.yaml: graph entry is not a mapping")
    return parsed


def _sparql_url(shortname: str | None, federation: bool, void: bool) -> str:
    """Resolve the SPARQL endpoint for a query target selection.

    ``shortname`` selects the per-graph endpoint and takes precedence over the
    flags; ``federation`` and ``void`` are mutually exclusive.

    Raises:
        ValueError: If no target is selected or the flags conflict.
    """
    if federation and void:
        raise ValueError("federation and void are mutually exclusive query targets")
    if shortname is not None:
        return PER_GRAPH_SPARQL_TEMPLATE.format(shortname=shortname)
    if federation:
        return FEDERATION_SPARQL
    if void:
        return VOID_SPARQL
    raise ValueError("select a query target: shortname, federation=True, or void=True")


@dataclass
class OKNRegistry:
    """HTTP client for OKN registry metadata and query services.

    All methods route through the injected ``session`` (a default
    :class:`requests.Session` is created lazily on first use) and apply
    ``timeout`` to every request. HTTP responses with status >= 400 and
    malformed payloads raise :class:`RegistryError`.

    Attributes:
        session: Optional injected session (stubs in tests, custom auth or
            retry policies in production).
        timeout: Per-request timeout in seconds.
    """

    session: requests.Session | None = None
    timeout: float = DEFAULT_TIMEOUT

    def _session(self) -> requests.Session:
        """Return the injected session, creating the default one lazily."""
        if self.session is None:
            self.session = requests.Session()
        return self.session

    def _get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """GET ``url`` and enforce the HTTP >= 400 error contract."""
        response = self._session().get(url, params=params, headers=headers, timeout=self.timeout)
        if response.status_code >= 400:
            raise RegistryError(
                f"HTTP {response.status_code} from {url}", status=response.status_code
            )
        return response

    def _post(self, url: str, *, json_body: dict[str, Any]) -> requests.Response:
        """POST a JSON body to ``url`` and enforce the HTTP >= 400 error contract."""
        response = self._session().post(url, json=json_body, timeout=self.timeout)
        if response.status_code >= 400:
            raise RegistryError(
                f"HTTP {response.status_code} from {url}", status=response.status_code
            )
        return response

    def _parse_json_response(self, response: requests.Response, *, context: str) -> dict[str, Any]:
        """Parse a response body as a JSON object.

        Raises:
            RegistryError: If the body is not JSON or not a JSON object.
        """
        try:
            payload = response.json()
        except ValueError as exc:
            raise RegistryError(f"malformed JSON payload from {context}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RegistryError(f"malformed JSON payload from {context}: expected a JSON object")
        return payload

    def list_graphs(self, kgs_path: str | None = None) -> list[dict[str, Any]]:
        """Return the registry graph entries from ``kgs.yaml``.

        Args:
            kgs_path: Optional local path to a ``kgs.yaml`` copy; when given,
                the file is read instead of fetching :data:`KGS_YAML_URL`
                (offline use and tests).

        Returns:
            The graph metadata mappings under the top-level ``kgs`` key.
        """
        if kgs_path is not None:
            raw = Path(kgs_path).read_text(encoding="utf-8")
        else:
            raw = self._get(KGS_YAML_URL).text
        return parse_kgs_yaml(raw)["kgs"]

    def get_graph(self, shortname: str) -> dict[str, Any]:
        """Return the ``kgs.yaml`` metadata entry for ``shortname``.

        Raises:
            RegistryError: If no registry entry carries that shortname.
        """
        for entry in self.list_graphs():
            if entry.get("shortname") == shortname:
                return entry
        raise RegistryError(f"graph {shortname!r} not found in the OKN registry")

    def sparql(
        self,
        query: str,
        *,
        shortname: str | None = None,
        federation: bool = False,
        void: bool = False,
    ) -> dict[str, Any]:
        """Run a SPARQL query against a per-graph, federation, or VoID endpoint.

        The request is a GET with the ``query`` parameter and
        ``Accept: application/sparql-results+json`` (api-notes §2).

        Args:
            query: SPARQL query text.
            shortname: Graph shortname for the per-graph endpoint (§2.1);
                takes precedence over the flags when combined with them.
            federation: Use the cross-OKN federation endpoint (§2.2).
            void: Use the VoID statistics endpoint (§2.3).

        Returns:
            The parsed SPARQL JSON document. Only the envelope is validated
            here (ASK results legitimately lack ``results.bindings``); use
            :meth:`sparql_rows` for validated, flattened rows.

        Raises:
            RegistryError: On HTTP >= 400 or a non-JSON-object payload.
            ValueError: If no target is selected or the flags conflict.
        """
        url = _sparql_url(shortname, federation, void)
        response = self._get(url, params={"query": query}, headers={"Accept": SPARQL_JSON_ACCEPT})
        return self._parse_json_response(response, context=url)

    def sparql_rows(
        self,
        query: str,
        *,
        shortname: str | None = None,
        federation: bool = False,
        void: bool = False,
    ) -> list[dict[str, str]]:
        """Run :meth:`sparql` and flatten the bindings to simple rows.

        Args:
            query: SPARQL query text (see :meth:`sparql` for the target flags).

        Returns:
            One ``{variable: value}`` dict per ``results.bindings`` row.

        Raises:
            RegistryError: On HTTP >= 400 or a malformed SPARQL JSON payload.
            ValueError: If no target is selected or the flags conflict.
        """
        payload = self.sparql(query, shortname=shortname, federation=federation, void=void)
        return [
            {name: str(term["value"]) for name, term in row.items()}
            for row in parse_sparql_json(payload)
        ]

    def tpf(
        self,
        shortname: str,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        accept: str = TRIG_ACCEPT,
    ) -> str:
        """Fetch a TPF fragment page for one triple pattern (api-notes §3).

        Args:
            shortname: Graph shortname; endpoint ``https://apps.okn.us/ldf/{shortname}``.
            subject: Full IRI of the subject pattern (prefixed names are not
                part of the interface).
            predicate: Full IRI of the predicate pattern.
            object: Full IRI — or literal — of the object pattern.
            accept: Content type to request; the documented default is Trig.

        Returns:
            The raw fragment body (Trig by default, with hydra pagination).
        """
        wanted = {"subject": subject, "predicate": predicate, "object": object}
        params = {name: value for name, value in wanted.items() if value is not None}
        response = self._get(
            TPF_TEMPLATE.format(shortname=shortname),
            params=params,
            headers={"Accept": accept},
        )
        return response.text

    def embedding_search(
        self,
        feature_type: str,
        value: str,
        include_graphs: list[str] | None = None,
        exclude_graphs: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search the OKN embeddings service (api-notes §5.2).

        POSTs a ``Query`` body to :data:`EMBEDDINGS_QUERY` and returns the
        parsed response (a ``results`` array of scored nearest matches).

        Args:
            feature_type: Documented discriminated union value: ``"text"`` or
                ``"node"``.
            value: The text or node IRI to search for.
            include_graphs: Optional graph shortnames to restrict the search
                to; mutually exclusive with ``exclude_graphs``.
            exclude_graphs: Optional graph shortnames to filter out.
            limit: Maximum number of matches (service default 10).
            offset: Pagination offset (service default 0).

        Returns:
            The parsed JSON response object.

        Raises:
            RegistryError: On HTTP >= 400 or a non-JSON-object payload.
            ValueError: If ``feature_type`` is not a documented feature type
                or both graph filter lists are set.
        """
        if feature_type not in FEATURE_TYPES:
            allowed = " or ".join(repr(kind) for kind in FEATURE_TYPES)
            raise ValueError(f"feature_type must be {allowed}, got {feature_type!r}")
        if include_graphs is not None and exclude_graphs is not None:
            raise ValueError("only one of include_graphs / exclude_graphs may be set")
        body: dict[str, Any] = {
            "feature": {"type": feature_type, "value": value},
            "limit": limit,
            "offset": offset,
        }
        if include_graphs is not None:
            body["include_graphs"] = list(include_graphs)
        if exclude_graphs is not None:
            body["exclude_graphs"] = list(exclude_graphs)
        response = self._post(EMBEDDINGS_QUERY, json_body=body)
        return self._parse_json_response(response, context=EMBEDDINGS_QUERY)
