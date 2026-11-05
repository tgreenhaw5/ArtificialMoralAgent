"""
HTTP server: versioned REST API (/api/v1), the routes used by the bundled web UI (/api/...), and the UI.

OpenAPI docs: /docs. Every evaluation response carries `general_disclaimer`; crisis responses carry
resources instead of an analysis.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
from importlib import resources

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, engine, frameworks, prompts, providers, safety, security
from .config import get_settings, has_cloud_key
from .store import get_store
from .store.base import new_id, public, record_from_analysis

log = logging.getLogger("ama.api")
STATIC = resources.files("ama") / "web" / "static"


# ---------------------------------------------------------------------------
# Request / response models (the v1 contract)
# ---------------------------------------------------------------------------
class EvaluationRequest(BaseModel):
    dilemma: str = Field(..., description="The situation to analyse, in plain language.")
    model: str | None = Field(None, description="LiteLLM model string; signed-in users and API keys only.")


class LegacyDilemmaRequest(BaseModel):
    dilemma_text: str
    model: str | None = None


class ModelChoice(BaseModel):
    model: str | None = None


class LoginRequest(BaseModel):
    password: str
    user: str | None = None


class FeedbackRequest(BaseModel):
    rating: int


class TriageRequest(BaseModel):
    text: str


class QuickRequest(BaseModel):
    action: str
    context: str = ""


class KeyRequest(BaseModel):
    label: str = "integration"


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class McpKeyGate:
    """MCP over HTTP spends the host's model key, so it needs an AMA API key (Authorization: Bearer ama_…)
    and obeys the per-minute rate limit. Local MCP over stdio (`ama mcp`) is unaffected."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            tok = auth[7:].strip() if auth.lower().startswith("bearer ") else headers.get("x-ama-key")
            key = security.check_key(tok)
            if not key:
                return await self._reply(send, 401, "MCP over HTTP needs an API key: send Authorization: Bearer "
                                                    "ama_… (create one with `ama keys create`).")
            if not security.rate_ok(f"key:{key['key_id']}"):
                return await self._reply(send, 429, "Too many requests; please slow down.")
        await self.app(scope, receive, send)

    @staticmethod
    async def _reply(send, status, detail):
        body = json.dumps({"detail": detail}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def create_app(mcp_http: bool = False) -> FastAPI:
    """The web app and REST API. With mcp_http=True, also MCP (Streamable HTTP) at /mcp, behind an API key."""
    s = get_settings()
    s.ensure_secret()
    get_store()
    lifespan = mcp_app = None
    if mcp_http:
        from .mcp_server import mcp as mcp_server
        mcp_server.settings.streamable_http_path = "/"        # served at /mcp/ once mounted at /mcp
        mcp_server._session_manager = None                   # a session manager runs once; new app, new one
        # The library's localhost-only Host check would reject Docker and reverse-proxy (IIS) requests. The
        # API key gate below is what protects this endpoint; a web page can't supply the key (no CORS here).
        from mcp.server.transport_security import TransportSecuritySettings
        mcp_server.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        mcp_app = mcp_server.streamable_http_app()

        @contextlib.asynccontextmanager
        async def lifespan(_app):
            async with mcp_server.session_manager.run():     # a mounted app's own startup never runs
                yield

    app = FastAPI(title="ArtificialMoralAgent", version=__version__, root_path=s.root_path, lifespan=lifespan,
                  description="Structured ethical analysis across four frameworks and a Chief Moral Arbiter. "
                              + safety.DISCLAIMER)
    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                           allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-cache, max-age=0"
        return resp

    _routes(app)
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    if mcp_app is not None:
        app.mount("/mcp", McpKeyGate(mcp_app))
        app.add_middleware(_McpNoSlash)

    return app


class _McpNoSlash:
    """Clients use both /mcp and /mcp/. Serve both directly: a redirect breaks clients that won't re-POST."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/mcp":
            scope = dict(scope, path="/mcp/", raw_path=b"/mcp/")
        await self.app(scope, receive, send)


def client_ip(request: Request) -> str:
    if os.environ.get("AMA_TRUST_PROXY", "").lower() in ("1", "true", "yes"):
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def identity(request: Request) -> dict:
    """Who is calling: {'kind': 'user'|'key'|'guest', 'name': …}."""
    auth = request.headers.get("authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else request.headers.get("x-ama-key")
    if tok:
        k = security.check_key(tok)
        if k:
            return {"kind": "key", "name": k["owner"], "key": k["key_id"]}
        u = security.read_session(tok)
        if u:
            return {"kind": "user", "name": u}
    u = security.read_session(request.cookies.get(security.SESSION_COOKIE))
    if u:
        return {"kind": "user", "name": u}
    return {"kind": "guest", "name": client_ip(request)}


def require_auth(request: Request) -> dict:
    who = identity(request)
    if who["kind"] == "guest":
        raise HTTPException(401, "Sign in or send an API key (Authorization: Bearer ama_…).")
    return who


def rate_limited(request: Request):
    who = identity(request)
    key = f"{who['kind']}:{who.get('key') or who['name']}"
    if not security.rate_ok(key):
        raise HTTPException(429, "Too many requests; please slow down.")
    return who


def normalise_model(m: str | None) -> str:
    s = get_settings()
    if not m:
        return s.model
    m = m.strip()
    if "/" not in m:      # names from AMA 2.x UI: gemini-…, claude-…, local Ollama tags
        m = ("gemini/" if m.startswith("gemini") else "anthropic/" if m.startswith("claude") else "ollama_chat/") + m
    if m not in s.allowed_models and m != s.model:
        raise HTTPException(400, f"Model not allowed on this server: {m}. Allowed: {', '.join(s.allowed_models)}")
    return m


def check_text(text: str) -> str:
    s = get_settings()
    text = (text or "").strip()
    if len(text) < 10:
        raise HTTPException(400, "Please describe the dilemma in at least 10 characters.")
    if len(text) > s.max_chars:
        raise HTTPException(413, f"Please keep the dilemma under {s.max_chars} characters.")
    return text


async def run_evaluation(text: str, model: str, published: bool, source: str) -> dict:
    """Cache check (exact, then near-duplicate), evaluation, storage. Returns the API payload."""
    st = get_store()
    hit = st.find_exact(text, model)
    if hit:
        return safety.with_disclaimer({**public(hit), "cached": True, "cache_type": "exact_match"})
    qvec = None
    try:
        qvec = await providers.embed(text, "query")
        near = st.similar(qvec, k=1, model=model)
        if near and near[0][1] < 0.04:
            return safety.with_disclaimer({**public(near[0][0]), "cached": True, "cache_type": "vector_near_match",
                                           "distance": near[0][1]})
    except Exception as e:
        log.info("near-duplicate check skipped: %s", e)
    try:
        analysis = await engine.evaluate(text, model)
    except providers.ModelError as e:
        raise HTTPException(502, f"The model could not complete the analysis: {e}") from e
    if analysis.get("is_crisis"):
        return analysis
    if qvec and not analysis.get("embedding"):
        analysis["embedding"] = qvec
    rec = st.add(record_from_analysis(text, analysis, published=published, source=source))
    return safety.with_disclaimer({**public(rec), "cached": False, "usage": analysis.get("usage")})


def _routes(app: FastAPI):
    s = get_settings()

    # ---- public info ---------------------------------------------------------
    @app.get("/health")
    @app.get("/api/v1/health")
    def health():
        st = get_store()
        return {"status": "ok", "version": __version__, "database": st.backend, "model": s.model,
                "prompt_version": prompts.PROMPT_VERSION, "counts": st.count()}

    @app.get("/api/v1/config")
    def public_config(request: Request):
        who = identity(request)
        return {"version": __version__, "default_model": s.model, "public_demo": s.public_demo,
                "kb_public": security.kb_public(), "model_key_configured": s.fake_llm or has_cloud_key(s.model),
                "signed_in": who["kind"] != "guest", "disclaimer": safety.DISCLAIMER,
                "max_chars": s.max_chars, "demo_per_ip_per_day": s.demo_per_ip_per_day}

    @app.get("/api/v1/frameworks")
    def list_frameworks():
        return [{"key": f.key, "title": f.title, "description": f.description} for f in frameworks.active()] + \
               [{"key": "arbiter", "title": "Chief Moral Arbiter",
                 "description": "Blends the frameworks' recommendations by their conviction weights; reports "
                                "consensus or the leading action plus dissenting views."}]

    # ---- auth ----------------------------------------------------------------------
    @app.get("/api/auth/status")
    @app.get("/api/v1/auth/status")
    def auth_status(request: Request):
        who = identity(request)
        return {"auth_required": True, "authenticated": who["kind"] != "guest", "user": who["name"]
                if who["kind"] != "guest" else None, "public_demo": s.public_demo}

    @app.post("/api/auth/login")
    @app.post("/api/v1/auth/login")
    def login(req: LoginRequest, response: Response, request: Request):
        if not security.rate_ok("login:" + client_ip(request)):
            raise HTTPException(429, "Too many attempts; wait a minute.")
        name = req.user
        if not name:      # AMA 2.x UI sends only a password: allowed when there is exactly one admin
            users = get_store().list_users()
            name = users[0]["name"] if len(users) == 1 else ""
        u = security.check_login(name, req.password)
        if not u:
            raise HTTPException(401, "Wrong user name or password.")
        tok = security.make_session(u["name"])
        response.set_cookie(security.SESSION_COOKIE, tok, max_age=security.SESSION_DAYS * 86400, httponly=True,
                            samesite="lax", secure=request.url.scheme == "https", path="/")
        return {"status": "success", "token": tok, "user": u["name"]}

    @app.post("/api/auth/logout")
    @app.post("/api/v1/auth/logout")
    def logout(response: Response):
        response.delete_cookie(security.SESSION_COOKIE, path="/")
        return {"status": "success"}

    @app.get("/api/v1/keys")
    def keys(who=Depends(require_auth)):
        return get_store().list_keys()

    @app.post("/api/v1/keys")
    def new_key(req: KeyRequest, who=Depends(require_auth)):
        if who["kind"] != "user":
            raise HTTPException(403, "Create keys while signed in.")
        return {"key": security.create_key(req.label, who["name"]), "note": "Shown once; store it securely."}

    @app.delete("/api/v1/keys/{key_id}")
    def del_key(key_id: str, who=Depends(require_auth)):
        return {"revoked": get_store().revoke_key(key_id)}

    # ---- models ------------------------------------------------------------------------
    @app.get("/api/models")
    @app.get("/api/v1/models")
    def models(who=Depends(require_auth)):
        return {"models": [s.model] + [m for m in s.allowed_models if m != s.model], "default": s.model}

    # ---- evaluations -----------------------------------------------------------------------
    async def submit(text: str, model: str | None, request: Request):
        who = rate_limited(request)
        text = check_text(text)
        st = get_store()
        if who["kind"] == "guest":
            ok, why = security.demo_allowance(who["name"])
            if not ok:
                rec = st.add({"id": new_id(), "dilemma_text": text, "status": "pending",
                              "model_details": "Pending Evaluation", "prompt_version": prompts.PROMPT_VERSION,
                              "published": False, "source": "guest"})
                return safety.with_disclaimer({**public(rec), "queued": True, "message": why})
            result = await run_evaluation(text, s.model, published=False, source="demo")
            security.record_demo(who["name"], float((result.get("usage") or {}).get("cost_usd") or 0))
            return result
        return await run_evaluation(text, normalise_model(model), published=True,
                                    source="api" if who["kind"] == "key" else "admin")

    @app.post("/api/v1/evaluations")
    async def create_evaluation(req: EvaluationRequest, request: Request, stream: bool = False):
        if not stream:
            return await submit(req.dilemma, req.model, request)
        who = rate_limited(request)
        if who["kind"] == "guest":
            raise HTTPException(401, "Streaming is available to signed-in users and API keys.")
        text = check_text(req.dilemma)
        model = normalise_model(req.model)

        async def events():
            final = None
            try:
                async for ev in engine.evaluate_stream(text, model):
                    if ev["stage"] == "done":
                        final = ev["result"]
                        continue
                    yield f"event: {ev['stage']}\ndata: {json.dumps(ev)}\n\n"
                if final and not final.get("is_crisis"):
                    rec = get_store().add(record_from_analysis(text, final, published=True, source="api"))
                    final = safety.with_disclaimer({**public(rec), "usage": final.get("usage")})
                yield f"event: done\ndata: {json.dumps(final)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)[:300]})}\n\n"
        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/dilemmas")
    async def legacy_create(req: LegacyDilemmaRequest, request: Request):
        return await submit(req.dilemma_text, req.model, request)

    def can_read(rec: dict | None, request: Request) -> bool:
        if not rec:
            return False
        if identity(request)["kind"] != "guest":
            return True
        return bool(rec.get("published")) and rec.get("status") == "done" and security.kb_public()

    @app.get("/api/v1/evaluations/{dilemma_id}")
    @app.get("/api/dilemmas/{dilemma_id}")
    def get_evaluation(dilemma_id: str, request: Request):
        rec = get_store().get(dilemma_id)
        if not can_read(rec, request):
            raise HTTPException(404, "Not found.")
        return safety.with_disclaimer(public(rec))

    @app.post("/api/v1/evaluations/{dilemma_id}/frameworks/{name}")
    async def rerun_framework(dilemma_id: str, name: str, req: ModelChoice, who=Depends(require_auth)):
        st = get_store()
        rec = st.get(dilemma_id)
        fw = frameworks.get(name)
        if not rec or not fw:
            raise HTTPException(404, "Unknown evaluation or framework.")
        data, usage = await providers.complete_json(fw.prompt.format(fenced=prompts.fence(rec["dilemma_text"])),
                                                    normalise_model(req.model), fw.key)
        if fw.db_column:
            st.update(dilemma_id, {fw.db_column: data})
        return {"framework": fw.key, "result": data, "usage": usage, "general_disclaimer": safety.DISCLAIMER}

    @app.get("/api/v1/dilemmas")
    @app.get("/api/dilemmas")
    def knowledge_base(request: Request, limit: int = Query(25, le=200), offset: int = 0):
        guest = identity(request)["kind"] == "guest"
        if guest and not security.kb_public():
            return []
        return [public(r) for r in get_store().list("done", published_only=guest, limit=limit, offset=offset)]

    @app.get("/api/v1/search")
    @app.get("/api/search")
    async def search(request: Request, q: str = Query(..., min_length=3, max_length=500), limit: int = Query(6, le=25)):
        guest = rate_limited(request)["kind"] == "guest"
        if guest and not security.kb_public():
            return []
        st = get_store()
        try:
            vec = await providers.embed(q, "query")
            hits = st.similar(vec, k=limit, published_only=guest)
            return [{**public(r), "distance": round(d, 4)} for r, d in hits]
        except Exception as e:
            log.info("vector search unavailable (%s); falling back to text match", e)
            ql = q.lower()
            rows = st.list("done", published_only=guest, limit=500)
            return [public(r) for r in rows if ql in (r.get("dilemma_text") or "").lower()][:limit]

    @app.post("/api/v1/feedback/{dilemma_id}")
    @app.post("/api/feedback/{dilemma_id}")
    def feedback(dilemma_id: str, fb: FeedbackRequest, request: Request):
        rate_limited(request)
        st = get_store()
        if not st.get(dilemma_id):
            raise HTTPException(404, "Not found.")
        st.update(dilemma_id, {"thumbs_up_down": 1 if fb.rating > 0 else -1})
        return {"status": "success", "rating": 1 if fb.rating > 0 else -1}

    @app.post("/api/v1/triage")
    async def triage_only(req: TriageRequest, request: Request, who=Depends(require_auth)):
        res, usage = await engine.triage(check_text(req.text))
        return {**res, "usage": usage, "hotlines": safety.HOTLINES if res["is_crisis"] else [],
                "general_disclaimer": safety.DISCLAIMER}

    @app.post("/api/v1/quick-check")
    async def quick(req: QuickRequest, request: Request, who=Depends(require_auth)):
        return await engine.quick_check(check_text(req.action), req.context[:2000])

    # ---- admin: submissions queue ---------------------------------------------------------
    @app.get("/api/v1/submissions")
    @app.get("/api/submissions")
    def submissions(status_filter: str | None = None, limit: int = Query(100, le=500), who=Depends(require_auth)):
        status = status_filter if status_filter in ("pending", "done") else None
        return [public(r) for r in get_store().list(status, limit=limit)]

    @app.post("/api/v1/submissions/{dilemma_id}/evaluate")
    @app.post("/api/submissions/{dilemma_id}/evaluate")
    async def evaluate_submission(dilemma_id: str, req: ModelChoice, who=Depends(require_auth)):
        st = get_store()
        rec = st.get(dilemma_id)
        if not rec:
            raise HTTPException(404, "Not found.")
        model = normalise_model(req.model)
        try:
            analysis = await engine.evaluate(rec["dilemma_text"], model)
        except providers.ModelError as e:
            raise HTTPException(502, str(e)) from e
        if analysis.get("is_crisis"):
            st.update(dilemma_id, {"status": "done", "model_details": model,
                                   "extra": {"crisis": analysis.get("crisis_type")}})
            return analysis
        new = record_from_analysis(rec["dilemma_text"], analysis)
        fields = {k: new[k] for k in ("utilitarian_response", "deontology_response", "virtue_ethics_response",
                                      "care_ethics_response", "verdict", "extra", "embedding", "model_details",
                                      "prompt_version")}
        fields["status"] = "done"
        out = st.update(dilemma_id, fields)
        return safety.with_disclaimer({**public(out), "cached": False, "usage": analysis.get("usage")})

    @app.post("/api/v1/submissions/{dilemma_id}/done")
    @app.post("/api/submissions/{dilemma_id}/done")
    def mark_done(dilemma_id: str, who=Depends(require_auth)):
        out = get_store().update(dilemma_id, {"status": "done"})
        if not out:
            raise HTTPException(404, "Not found.")
        return public(out)

    @app.delete("/api/v1/submissions/{dilemma_id}")
    @app.delete("/api/submissions/{dilemma_id}")
    @app.delete("/api/v1/dilemmas/{dilemma_id}")
    def delete_dilemma(dilemma_id: str, who=Depends(require_auth)):
        """Permanently remove a dilemma (pending or evaluated), its analysis and its vector."""
        if not get_store().delete(dilemma_id):
            raise HTTPException(404, "Not found.")
        log.info("dilemma %s deleted by %s", dilemma_id, who.get("name") or who.get("kind"))
        return {"deleted": dilemma_id}

    @app.post("/api/v1/dilemmas/{dilemma_id}/publish")
    def publish(dilemma_id: str, published: bool = True, who=Depends(require_auth)):
        out = get_store().update(dilemma_id, {"published": published})
        if not out:
            raise HTTPException(404, "Not found.")
        return public(out)

    # ---- UI ------------------------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(STATIC / "index.html"))

    @app.get("/help/gemini-key", include_in_schema=False)
    def gemini_help():
        return FileResponse(str(STATIC / "gemini-key.html"))


app = None


def get_app():
    global app
    if app is None:
        app = create_app()
    return app
