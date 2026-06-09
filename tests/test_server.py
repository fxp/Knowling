"""HTTP API smoke tests — run the real server on an ephemeral port (offline mock)."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from knowling import server


@pytest.fixture()
def base_url():
    httpd = server.serve("127.0.0.1", 0)  # port 0 → OS picks a free port
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# force the offline provider so tests need no API key / network
MOCK = {"provider": "mock"}


def test_health_and_blocks(base_url):
    s, d = _get(base_url + "/v1/health")
    assert s == 200 and d["ok"] is True and "version" in d
    s, d = _get(base_url + "/v1/blocks")
    assert s == 200 and "manim" in d["blocks"] and "quiz" in d["blocks"]


def test_plan(base_url):
    s, d = _post(base_url + "/v1/knowling/plan",
                 {**MOCK, "kp": {"id": "k1", "title": "斜率"}})
    assert s == 200 and d["spec"]["knowledge_point_id"] == "k1"
    assert d["spec"]["blocks"]


def test_generate_returns_self_contained_html(base_url):
    s, d = _post(base_url + "/v1/knowling/generate",
                 {**MOCK, "kp": {"id": "k2", "title": "链式法则", "description": "复合函数求导"}})
    assert s == 200
    assert d["knowling"]["knowledge_point_id"] == "k2"
    assert "<!DOCTYPE html>" in d["html"]


def test_compile_then_refine(base_url):
    _, p = _post(base_url + "/v1/knowling/plan", {**MOCK, "kp": {"id": "k3", "title": "导数"}})
    s, d = _post(base_url + "/v1/knowling/compile",
                 {**MOCK, "kp": {"id": "k3", "title": "导数"}, "spec": p["spec"]})
    assert s == 200 and "<!DOCTYPE html>" in d["html"]
    s, d = _post(base_url + "/v1/knowling/refine",
                 {**MOCK, "kp": {"id": "k3", "title": "导数"}, "spec": p["spec"], "instruction": "太难了"})
    assert s == 200 and d["summary"] and isinstance(d["changes"], list)


def test_reteach_and_quiz_eval(base_url):
    _, p = _post(base_url + "/v1/knowling/plan", {**MOCK, "kp": {"id": "k4", "title": "斜率"}})
    s, d = _post(base_url + "/v1/knowling/reteach",
                 {**MOCK, "kp": {"id": "k4", "title": "斜率"}, "spec": p["spec"],
                  "quiz": {"total": 5, "correct": 1}})
    assert s == 200 and "<!DOCTYPE html>" in d["html"]
    s, d = _post(base_url + "/v1/knowling/quiz-eval",
                 {"kp_id": "k4", "quiz": {"total": 5, "correct": 5}})
    assert s == 200 and d["mastery"]["passed"] is True and d["mastery"]["level"] == "green"


def test_errors(base_url):
    s, d = _post(base_url + "/v1/knowling/plan", {**MOCK})  # missing kp
    assert s == 400 and "error" in d
    s, d = _get(base_url + "/v1/nope")
    assert s == 404


def test_base_path_mount(base_url, monkeypatch):
    # behind a shared gateway mounted at /knowling
    monkeypatch.setenv("KNOWLING_BASE_PATH", "/knowling")
    s, d = _get(base_url + "/knowling/v1/health")
    assert s == 200 and d["ok"] is True
    s, d = _post(base_url + "/knowling/v1/knowling/plan",
                 {**MOCK, "kp": {"id": "k", "title": "t"}})
    assert s == 200 and d["spec"]["knowledge_point_id"] == "k"


def test_token_auth(base_url, monkeypatch):
    monkeypatch.setenv("KNOWLING_API_TOKEN", "secret123")
    # no token → 401
    s, d = _post(base_url + "/v1/knowling/plan", {**MOCK, "kp": {"id": "k", "title": "t"}})
    assert s == 401
    # GET stays open
    s, _ = _get(base_url + "/v1/health")
    assert s == 200
    # with token → ok
    req = urllib.request.Request(
        base_url + "/v1/knowling/plan",
        data=json.dumps({**MOCK, "kp": {"id": "k", "title": "t"}}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer secret123"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        assert r.status == 200
