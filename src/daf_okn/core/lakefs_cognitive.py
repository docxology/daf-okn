"""Stage the validated canonical Cognitive KB object for OKN review."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
import yaml

from . import rdf_submission

ENDPOINT = "https://repository.okn.us/api/v1"
REPOSITORY = "cognitive-kb"
BRANCH = "develop"
OBJECT = "cognitive-kb.nq"
MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
COMMIT_ID = re.compile(r"[0-9a-f]{64}")


class LakeFSError(ValueError):
    """A LakeFS handoff could not be verified."""


def _credentials(config: Path) -> tuple[str, str]:
    try:
        document = yaml.safe_load(rdf_submission.read_bounded(config, 16 * 1024))
        endpoint = document["server"]["endpoint_url"]
        credentials = document["credentials"]
        access = credentials["access_key_id"]
        secret = credentials["secret_access_key"]
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        raise LakeFSError("could not read a valid lakectl configuration") from None
    if endpoint not in (ENDPOINT, ENDPOINT + "/"):
        raise LakeFSError("lakectl configuration must use https://repository.okn.us/api/v1")
    if (
        any(
            not isinstance(value, str)
            or not value
            or not value.isascii()
            or not value.isprintable()
            for value in (access, secret)
        )
        or ":" in access
    ):
        raise LakeFSError("lakectl configuration has invalid credentials")
    return access, secret


def _commit_id(value: Any) -> str:
    if not isinstance(value, str) or not COMMIT_ID.fullmatch(value):
        raise LakeFSError("expected a full lakeFS commit ID")
    return value


@dataclass(frozen=True)
class _Payload:
    content: bytes
    sha256: str
    source_commit: str
    source_dirty: bool

    @classmethod
    def from_bundle(cls, bundle: Path) -> _Payload:
        manifest_path = bundle / "bundle.json"
        manifest_bytes = rdf_submission.read_bounded(
            manifest_path, rdf_submission.MAX_MANIFEST_BYTES
        )
        errors = rdf_submission.verify(bundle)
        if errors:
            raise LakeFSError("bundle verification failed: " + "; ".join(errors))
        manifest = rdf_submission.json_object(manifest_bytes)
        if (
            rdf_submission.read_bounded(manifest_path, rdf_submission.MAX_MANIFEST_BYTES)
            != manifest_bytes
        ):
            raise LakeFSError("bundle manifest changed during verification")
        content = rdf_submission.read_bounded(bundle / OBJECT, MAX_OBJECT_BYTES)
        digest = hashlib.sha256(content).hexdigest()
        if digest != manifest["files"][OBJECT]:
            raise LakeFSError("bundle changed while reading the canonical N-Quads")
        return cls(content, digest, manifest["source_commit"], manifest["source_dirty"])

    def receipt(self, state: str, commit: str, **fields: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "state": state,
            "repository": REPOSITORY,
            "object": OBJECT,
            "lakefs_commit": commit,
            "sha256": self.sha256,
            "size_bytes": len(self.content),
            "bundle_source_commit": self.source_commit,
            **fields,
        }


class _LakeFS:
    def __init__(self, session: requests.Session):
        self.session = session

    def request(
        self,
        method: str,
        path: str,
        *,
        expected: int = 200,
        missing_ok: bool = False,
        limit: int = MAX_RESPONSE_BYTES,
        **options: Any,
    ) -> bytes | None:
        try:
            with self.session.request(
                method,
                f"{ENDPOINT}/repositories/{REPOSITORY}/{path}",
                timeout=(8, 30),
                stream=True,
                allow_redirects=False,
                **options,
            ) as response:
                if response.status_code == 404 and missing_ok:
                    return None
                if response.status_code != expected:
                    raise LakeFSError(
                        f"lakeFS {method} {path} returned HTTP {response.status_code}"
                    )
                data = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    data.extend(chunk)
                    if len(data) > limit:
                        raise LakeFSError(
                            f"lakeFS {method} {path} exceeded the expected byte limit"
                        )
                return bytes(data)
        except requests.RequestException:
            raise LakeFSError(f"lakeFS {method} {path} failed during transfer") from None

    def json(self, method: str, path: str, **options: Any) -> dict[str, Any]:
        data = self.request(method, path, **options)
        try:
            return rdf_submission.json_object(data or b"")
        except ValueError:
            raise LakeFSError(f"lakeFS {method} {path} returned invalid JSON") from None

    def head(self, branch: str) -> str:
        return _commit_id(self.json("GET", f"branches/{branch}").get("commit_id"))

    def diff(self, path: str, **params: str) -> list[Any]:
        diff = self.json("GET", path, params={"amount": 2, **params})
        pagination = diff.get("pagination")
        results = diff.get("results")
        if (
            not isinstance(pagination, dict)
            or pagination.get("has_more") is not False
            or not isinstance(results, list)
        ):
            raise LakeFSError(f"lakeFS {path} has incomplete diff results")
        return results

    def clean(self, branch: str) -> None:
        if self.diff(f"branches/{branch}/diff"):
            raise LakeFSError(f"lakeFS {branch} has uncommitted changes")

    def object_hash(self, ref: str, limit: int) -> str | None:
        data = self.request(
            "GET",
            f"refs/{ref}/objects",
            params={"path": OBJECT, "presign": "false"},
            missing_ok=True,
            limit=limit,
        )
        return None if data is None else hashlib.sha256(data).hexdigest()

    def exact_change(
        self, record: dict[str, Any], payload: _Payload, *, parent: str | None = None
    ) -> tuple[str, str]:
        commit = _commit_id(record.get("id"))
        parents = record.get("parents")
        if not isinstance(parents, list) or len(parents) != 1:
            raise LakeFSError("expected a single-parent lakeFS commit")
        actual_parent = _commit_id(parents[0])
        if parent is not None and actual_parent != parent:
            raise LakeFSError("lakeFS commit parent does not match the observed branch head")
        rows = self.diff(f"refs/{actual_parent}/diff/{commit}", type="two_dot")
        if (
            len(rows) != 1
            or not isinstance(rows[0], dict)
            or rows[0].get("path") != OBJECT
            or rows[0].get("path_type") != "object"
            or rows[0].get("type") not in ("added", "changed")
        ):
            raise LakeFSError("lakeFS commit does not change exactly the canonical object")
        if self.object_hash(commit, len(payload.content)) != payload.sha256:
            raise LakeFSError("committed lakeFS bytes do not match the canonical object")
        return commit, actual_parent

    def stage(self, payload: _Payload, base: str, *, replace: bool) -> dict[str, Any]:
        branch = f"cognitive-upload-{uuid4().hex}"
        try:
            self.request("POST", "branches", expected=201, json={"name": branch, "source": base})
            if self.head(branch) != base:
                raise LakeFSError("lakeFS recovery branch does not point to the observed base")
            self.clean(branch)
            self.request(
                "POST",
                f"branches/{branch}/objects",
                expected=201,
                params={"path": OBJECT},
                headers={"If-None-Match": "*"} if not replace else {},
                files={"content": (OBJECT, payload.content, "application/n-quads")},
            )
            isolated = self.json(
                "POST",
                f"branches/{branch}/commits",
                expected=201,
                json={
                    "message": "Stage canonical Cognitive KB N-Quads",
                    "metadata": {
                        "source_commit": payload.source_commit,
                        "object_sha256": payload.sha256,
                    },
                },
            )
            isolated_commit, _ = self.exact_change(isolated, payload, parent=base)
            self.clean(BRANCH)
            if self.head(BRANCH) != base:
                raise LakeFSError("lakeFS develop advanced during staging")
            picked = self.json(
                "POST",
                f"branches/{BRANCH}/cherry-pick",
                expected=201,
                json={"ref": isolated_commit},
            )
            commit, parent = self.exact_change(picked, payload, parent=base)
            return payload.receipt(
                "staged",
                commit,
                branch=BRANCH,
                parent=parent,
                staging_branch=branch,
                staging_commit=isolated_commit,
            )
        except LakeFSError as error:
            raise LakeFSError(f"{error}. Inspect develop and recovery branch {branch}") from None


def run(
    bundle: Path,
    config: Path,
    *,
    stage: bool = False,
    commit: str | None = None,
    expected_develop: str | None = None,
) -> dict[str, Any]:
    """Preflight, stage, or verify the exact canonical N-Quads in lakeFS."""
    if (stage and commit is not None) or (expected_develop is not None and not stage):
        raise LakeFSError("select one operation; --expected-develop requires --stage")
    if commit is not None:
        _commit_id(commit)
    if expected_develop is not None:
        _commit_id(expected_develop)
    payload = _Payload.from_bundle(bundle)
    if stage and payload.source_dirty:
        raise LakeFSError("staging requires a bundle from a clean source checkout")
    with requests.Session() as session:
        session.trust_env = False
        session.auth = _credentials(config)
        client = _LakeFS(session)
        if commit is not None:
            if client.object_hash(commit, len(payload.content)) != payload.sha256:
                raise LakeFSError("lakeFS commit does not contain the canonical object bytes")
            return payload.receipt("verified", commit)
        client.clean(BRANCH)
        base = client.head(BRANCH)
        current = client.object_hash(base, MAX_OBJECT_BYTES)
        if client.head(BRANCH) != base:
            raise LakeFSError("lakeFS develop advanced during preflight")
        if current == payload.sha256:
            return payload.receipt("already_present", base, branch=BRANCH)
        if not stage:
            state = "ready" if current is None else "replacement_required"
            return payload.receipt(state, base, branch=BRANCH)
        if expected_develop is not None and base != expected_develop:
            raise LakeFSError("lakeFS develop does not match --expected-develop")
        if current is not None and expected_develop is None:
            raise LakeFSError(
                "replacing the object requires --expected-develop for the reviewed base"
            )
        return client.stage(payload, base, replace=current is not None)
