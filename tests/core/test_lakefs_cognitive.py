import base64
import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from test_rdf_submission import source_repo

from daf_okn.core import lakefs_cognitive as lakefs
from daf_okn.core import rdf_submission

BASE, ISOLATED, DEVELOP, ADVANCED = (char * 64 for char in "abcd")
ACCESS, SECRET = "fixture-access-key", "fixture-secret-key"
BASIC = "Basic " + base64.b64encode(f"{ACCESS}:{SECRET}".encode()).decode()
OBJECT = "cognitive-kb.nq"
DIFF_ROW = {"path": OBJECT, "path_type": "object", "type": "added"}
API_PREFIX = "/api/v1/repositories/cognitive-kb/"


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    authorization: str | None
    if_none_match: str | None
    content_type: str
    body: bytes

    def uploaded_object(self) -> tuple[str | None, bytes]:
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + self.content_type.encode() + b"\r\n\r\n" + self.body
        )
        parts = list(message.iter_parts())
        assert len(parts) == 1
        assert parts[0].get_param("name", header="content-disposition") == "content"
        assert parts[0].get_content_type() == "application/n-quads"
        content = parts[0].get_payload(decode=True)
        assert isinstance(content, bytes)
        return parts[0].get_filename(), content


@dataclass
class LandingZone:
    endpoint: str = ""
    head: str = BASE
    recovery: str = ""
    uploaded: bytes = b""
    objects: dict[str, bytes] = field(default_factory=dict)
    requests: list[Request] = field(default_factory=list)
    fault: str = ""

    @staticmethod
    def diff(rows, *, more=False):
        return 200, {"pagination": {"has_more": more}, "results": rows}

    def respond(self, request):
        path = request.path
        if request.authorization != BASIC:
            return 401, {"message": "unexpected fixture credentials"}
        if request.method == "GET":
            if path == "branches/develop":
                return 200, {"id": "develop", "commit_id": self.head}
            if path == f"branches/{self.recovery}":
                return 200, {"id": self.recovery, "commit_id": BASE}
            if path == "branches/develop/diff":
                return self.diff([DIFF_ROW] if self.fault == "dirty" else [])
            if path == f"branches/{self.recovery}/diff":
                return self.diff([DIFF_ROW] if self.uploaded else [])
            if path in {f"refs/{BASE}/diff/{ISOLATED}", f"refs/{BASE}/diff/{DEVELOP}"}:
                if self.fault == "extra_diff":
                    return self.diff([DIFF_ROW, {**DIFF_ROW, "path": "other.nq"}])
                if self.fault == "malformed_diff":
                    return self.diff([{**DIFF_ROW, "type": []}])
                if self.fault == "paginated_diff":
                    return self.diff([DIFF_ROW], more=True)
                return self.diff([DIFF_ROW])
            if path.startswith("refs/") and path.endswith("/objects"):
                ref = path.split("/")[1]
                if self.fault == "unauthorized":
                    return 403, {"message": f"Sensitive server response {ACCESS} {SECRET} {BASIC}"}
                if self.fault == "preflight_drift":
                    self.head = ADVANCED
                if self.fault == "redirect":
                    return 302, b""
                if ref in self.objects:
                    return 200, self.objects[ref]
                return 404, b""
        if request.method == "POST":
            if path == "branches":
                branch = json.loads(request.body)
                self.recovery = branch["name"]
                return 201, BASE.encode()
            if path == f"branches/{self.recovery}/objects":
                name, payload = request.uploaded_object()
                assert name == OBJECT
                self.uploaded = payload
                return 201, {"path": OBJECT}
            if path == f"branches/{self.recovery}/commits":
                if self.fault == "invalid_json":
                    return 201, b"not JSON"
                parent = ADVANCED if self.fault == "invalid_parent" else BASE
                if self.fault == "develop_drift":
                    self.head = ADVANCED
                self.objects[ISOLATED] = self.uploaded
                return 201, {"id": ISOLATED, "parents": [parent]}
            if path == "branches/develop/cherry-pick":
                if self.fault == "conflict":
                    return 409, {"message": f"Sensitive server response {SECRET}"}
                self.head = DEVELOP
                self.objects[DEVELOP] = (
                    b"x" * len(self.uploaded) if self.fault == "changed_bytes" else self.uploaded
                )
                return 201, {
                    "id": DEVELOP,
                    "parents": [BASE],
                    "metadata": {"cherry-pick-origin": ISOLATED},
                }
        return 404, {"message": f"Unexpected test request {request.method} {path}"}


@pytest.fixture
def landing_zone(monkeypatch):
    zone = LandingZone()

    class Handler(BaseHTTPRequestHandler):
        def exchange(self):
            parsed = urlsplit(self.path)
            assert parsed.path.startswith(API_PREFIX)
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            request = Request(
                self.command,
                parsed.path.removeprefix(API_PREFIX),
                parse_qs(parsed.query),
                self.headers.get("Authorization"),
                self.headers.get("If-None-Match"),
                self.headers.get("Content-Type", ""),
                body,
            )
            zone.requests.append(request)
            status, data = zone.respond(request)
            payload = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            if status == 302:
                self.send_header("Location", f"{API_PREFIX}branches/develop")
            self.end_headers()
            self.wfile.write(payload)

        do_GET = exchange
        do_POST = exchange

        def log_message(self, format, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        zone.endpoint = f"http://127.0.0.1:{server.server_port}/api/v1"
        monkeypatch.setattr(lakefs, "ENDPOINT", zone.endpoint)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        try:
            yield zone
        finally:
            server.shutdown()
            thread.join()


def make_config(path: Path, endpoint: str) -> Path:
    path.write_text(
        f"server:\n  endpoint_url: {endpoint}\n"
        f"credentials:\n  access_key_id: {ACCESS}\n  secret_access_key: {SECRET}\n"
    )
    return path


@pytest.fixture
def config(tmp_path, landing_zone):
    return make_config(tmp_path / "lakectl.yaml", landing_zone.endpoint)


def make_bundle(tmp_path, *, clean):
    root = source_repo(tmp_path)
    if clean:
        (root / ".git/info/exclude").write_text("/output/\n")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.org",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Add canonical export sources",
            ],
            check=True,
            stdin=subprocess.DEVNULL,
        )
    output = tmp_path / "bundle"
    rdf_submission.prepare(root, output)
    assert json.loads((output / "bundle.json").read_text())["source_dirty"] is not clean
    return output


@pytest.fixture
def bundle(tmp_path):
    return make_bundle(tmp_path, clean=True)


def test_preflight_and_stage_exact_canonical_bytes_then_retry(bundle, config, landing_zone):
    content = (bundle / OBJECT).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    preflight = lakefs.run(bundle, config)
    assert preflight["state"] == "ready"
    assert preflight["lakefs_commit"] == BASE
    assert preflight["sha256"] == digest
    assert all(req.method == "GET" for req in landing_zone.requests)

    receipt = lakefs.run(bundle, config, stage=True, expected_develop=BASE)
    actual = landing_zone.recovery
    assert actual.startswith("cognitive-upload-")
    assert receipt == {
        **preflight,
        "state": "staged",
        "lakefs_commit": DEVELOP,
        "parent": BASE,
        "staging_branch": actual,
        "staging_commit": ISOLATED,
    }
    assert landing_zone.objects[DEVELOP] == content
    writes = [req for req in landing_zone.requests if req.method == "POST"]
    create, upload, commit, pick = writes
    assert [req.path for req in writes] == [
        "branches",
        f"branches/{actual}/objects",
        f"branches/{actual}/commits",
        "branches/develop/cherry-pick",
    ]
    assert json.loads(create.body) == {"name": actual, "source": BASE}
    assert upload.if_none_match == "*"
    assert upload.query == {"path": [OBJECT]}
    assert upload.uploaded_object() == (OBJECT, content)
    assert json.loads(commit.body)["metadata"] == {
        "source_commit": preflight["bundle_source_commit"],
        "object_sha256": digest,
    }
    assert json.loads(pick.body) == {"ref": ISOLATED}
    assert [
        req.query for req in landing_zone.requests if req.path.startswith(f"refs/{BASE}/diff/")
    ] == [{"amount": ["2"], "type": ["two_dot"]}] * 2

    retry_start = len(landing_zone.requests)
    retry = lakefs.run(bundle, config, stage=True, expected_develop=BASE)
    assert retry["state"] == "already_present"
    assert retry["lakefs_commit"] == DEVELOP
    assert all(req.method == "GET" for req in landing_zone.requests[retry_start:])


def test_existing_content_requires_reviewed_base_before_replacement(bundle, config, landing_zone):
    landing_zone.objects[BASE] = b"existing distinct object"
    assert lakefs.run(bundle, config)["state"] == "replacement_required"
    with pytest.raises(lakefs.LakeFSError, match="replacing the object requires"):
        lakefs.run(bundle, config, stage=True)
    with pytest.raises(lakefs.LakeFSError, match="does not match --expected-develop"):
        lakefs.run(bundle, config, stage=True, expected_develop=ADVANCED)
    assert all(req.method == "GET" for req in landing_zone.requests)
    assert lakefs.run(bundle, config, stage=True, expected_develop=BASE)["state"] == "staged"
    [upload] = [
        req
        for req in landing_zone.requests
        if req.path.endswith("/objects") and req.method == "POST"
    ]
    assert upload.if_none_match is None


@pytest.mark.parametrize(
    ("fault", "reason"),
    [
        ("extra_diff", "does not change exactly"),
        ("malformed_diff", "does not change exactly"),
        ("paginated_diff", "incomplete diff"),
        ("develop_drift", "develop advanced"),
        ("invalid_parent", "parent does not match"),
        ("invalid_json", "invalid JSON"),
    ],
)
def test_unverified_isolated_commit_never_reaches_develop(
    bundle, config, landing_zone, fault, reason
):
    landing_zone.fault = fault
    with pytest.raises(lakefs.LakeFSError, match=reason) as raised:
        lakefs.run(bundle, config, stage=True)
    assert landing_zone.recovery in str(raised.value)
    assert not any(req.path == "branches/develop/cherry-pick" for req in landing_zone.requests)


def test_dirty_develop_refuses_staging(bundle, config, landing_zone):
    landing_zone.fault = "dirty"
    with pytest.raises(lakefs.LakeFSError, match="develop has uncommitted changes"):
        lakefs.run(bundle, config, stage=True)
    assert all(req.method == "GET" for req in landing_zone.requests)


def test_concurrent_advance_invalidates_preflight(bundle, config, landing_zone):
    landing_zone.fault = "preflight_drift"
    with pytest.raises(lakefs.LakeFSError, match="develop advanced during preflight"):
        lakefs.run(bundle, config)
    assert all(req.method == "GET" for req in landing_zone.requests)


def test_commit_verification_is_pinned_and_compares_content(bundle, config, landing_zone):
    content = (bundle / OBJECT).read_bytes()
    landing_zone.objects[DEVELOP] = content
    result = lakefs.run(bundle, config, commit=DEVELOP)
    assert result["state"] == "verified"
    assert result["lakefs_commit"] == DEVELOP
    [request] = landing_zone.requests
    assert request.method == "GET"
    assert request.path == f"refs/{DEVELOP}/objects"
    assert request.query == {"path": [OBJECT], "presign": ["false"]}
    landing_zone.objects[DEVELOP] = b"x" * len(content)
    with pytest.raises(lakefs.LakeFSError, match="does not contain the canonical object bytes"):
        lakefs.run(bundle, config, commit=DEVELOP)


def test_readback_mismatch_does_not_return_staging_receipt(bundle, config, landing_zone):
    landing_zone.fault = "changed_bytes"
    with pytest.raises(lakefs.LakeFSError, match="committed lakeFS bytes do not match"):
        lakefs.run(bundle, config, stage=True)
    assert landing_zone.head == DEVELOP


def test_config_endpoint_mismatch_refuses_before_using_credentials(bundle, config, landing_zone):
    make_config(config, landing_zone.endpoint + "/unexpected")
    with pytest.raises(lakefs.LakeFSError, match="configuration must use"):
        lakefs.run(bundle, config, stage=True)
    assert landing_zone.requests == []


def test_authenticated_request_does_not_follow_redirect(bundle, config, landing_zone):
    landing_zone.fault = "redirect"
    with pytest.raises(lakefs.LakeFSError, match="HTTP 302"):
        lakefs.run(bundle, config, commit=DEVELOP)
    [request] = landing_zone.requests
    assert request.path == f"refs/{DEVELOP}/objects"


@pytest.mark.parametrize(
    "options",
    [
        {"commit": DEVELOP, "stage": True},
        {"expected_develop": BASE},
        {"commit": DEVELOP[:16]},
        {"expected_develop": "develop", "stage": True},
    ],
)
def test_incompatible_operations_and_mutable_refs_are_rejected(
    bundle, config, landing_zone, options
):
    with pytest.raises(lakefs.LakeFSError, match="select one operation|full lakeFS commit ID"):
        lakefs.run(bundle, config, **options)
    assert landing_zone.requests == []


def test_source_dirty_or_bundle_tampered_blocks_all_network_io(tmp_path, config, landing_zone):
    bundle = make_bundle(tmp_path, clean=False)
    with pytest.raises(lakefs.LakeFSError, match="clean source checkout"):
        lakefs.run(bundle, config, stage=True)
    (bundle / OBJECT).write_bytes(b"tampered")
    with pytest.raises(lakefs.LakeFSError, match="bundle verification failed"):
        lakefs.run(bundle, config)
    assert landing_zone.requests == []


@pytest.mark.parametrize(("fault", "status"), [("unauthorized", 403), ("conflict", 409)])
def test_server_errors_report_status_without_echoing_credentials(
    bundle, config, landing_zone, capsys, caplog, fault, status
):
    landing_zone.fault = fault
    with pytest.raises(lakefs.LakeFSError, match=f"HTTP {status}") as raised:
        lakefs.run(bundle, config, stage=True)
    out, err = capsys.readouterr()
    diagnostic = str(raised.value) + out + err + caplog.text
    assert all(value not in diagnostic for value in (ACCESS, SECRET, BASIC))
