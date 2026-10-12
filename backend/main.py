"""Run with: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .core import AppError, MAX_FILE_BYTES, MAX_SELECTED_DOCUMENTS, ModelSettings, NotebookStore, PROJECT_ROOT


class SettingsUpdate(ModelSettings):
    api_key: str | None = Field(default=None, max_length=1000)


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=8000)
    document_ids: list[str] = Field(default_factory=list, max_length=MAX_SELECTED_DOCUMENTS)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)


class StudioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["summary", "study_guide", "flashcards", "quiz"]
    document_ids: list[str] = Field(default_factory=list, max_length=MAX_SELECTED_DOCUMENTS)


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = NotebookStore(data_dir)
        yield
        await app.state.store.http_async_client.aclose()
        app.state.store.close()

    app = FastAPI(title="Studybook local RAG", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_request_guard(request: Request, call_next):
        # A browser on another website must not operate this local service.
        origin = request.headers.get("origin")
        expected_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if request.url.path.startswith("/api/") and origin and origin != expected_origin:
            return JSONResponse({"error": "Cross-origin API requests are not allowed."}, status_code=403)
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > 100 * 1024 * 1024:
                    return JSONResponse({"error": "A request must be 100 MB or smaller."}, status_code=413)
            except ValueError:
                return JSONResponse({"error": "Invalid Content-Length header."}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # Original source files are downloads. The UI renders all source/model text as text.
        return response

    @app.exception_handler(AppError)
    async def app_error(_request, exc: AppError):
        return JSONResponse({"error": exc.message, "detail": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        message = "; ".join(f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}" for error in exc.errors())
        return JSONResponse({"error": message, "detail": message}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(_request, exc):
        logging.getLogger("studybook").error("Request failed (%s)", type(exc).__name__)
        return JSONResponse({"error": "The local service could not complete this request. Your stored sources have been retained."}, status_code=500)

    @app.get("/api/health")
    def health(request: Request):
        return request.app.state.store.health()

    @app.get("/api/settings")
    def settings(request: Request):
        return request.app.state.store.get_settings()

    @app.put("/api/settings")
    def update_settings(payload: SettingsUpdate, request: Request):
        values = payload.model_dump(exclude={"api_key"})
        return request.app.state.store.set_settings(ModelSettings(**values), payload.api_key)

    @app.post("/api/connection")
    def connection(request: Request):
        return request.app.state.store.connection()

    @app.get("/api/documents")
    def documents(request: Request):
        return {"documents": request.app.state.store.list_documents()}

    @app.post("/api/documents")
    async def upload_documents(request: Request, files: list[UploadFile] = File(...)):
        if len(files) > 20:
            for upload in files:
                await upload.close()
            raise AppError("Upload at most 20 files at a time.")
        documents, errors = [], []
        for upload in files:
            name = upload.filename or "unnamed"
            try:
                data = await upload.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise AppError("Each file must be 25 MB or smaller.", 413)
                document = await run_in_threadpool(request.app.state.store.ingest, name, data)
                documents.append(document)
            except AppError as exc:
                errors.append({"name": name, "error": exc.message})
            finally:
                await upload.close()
        return {"documents": documents, "errors": errors}

    @app.delete("/api/documents/{document_id}")
    def delete_document(document_id: str, request: Request):
        request.app.state.store.delete_document(document_id)
        return {"status": "deleted"}

    @app.get("/api/documents/{document_id}/content")
    def document_content(document_id: str, request: Request):
        return request.app.state.store.document_content(document_id)

    @app.get("/api/documents/{document_id}/file")
    def document_file(document_id: str, request: Request):
        path, name = request.app.state.store.document_file(document_id)
        return FileResponse(path, filename=name, media_type="application/octet-stream", content_disposition_type="attachment")

    @app.post("/api/chat")
    def chat(payload: ChatRequest, request: Request):
        return request.app.state.store.chat(payload.message, payload.document_ids, [turn.model_dump() for turn in payload.history])

    @app.get("/api/studio")
    def studio(request: Request):
        return {"artifacts": request.app.state.store.list_artifacts()}

    @app.post("/api/studio")
    def generate(payload: StudioRequest, request: Request):
        return request.app.state.store.generate(payload.kind, payload.document_ids)

    @app.get("/api/studio/{identity}/export")
    def export_artifact(identity: str, request: Request):
        markdown, filename = request.app.state.store.export_artifact(identity)
        return Response(content=markdown.encode("utf-8"), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @app.delete("/api/studio/{identity}")
    def delete_artifact(identity: str, request: Request):
        request.app.state.store.delete_artifact(identity)
        return {"status": "deleted"}

    examples = PROJECT_ROOT / "examples"
    if examples.is_dir():
        app.mount("/examples", StaticFiles(directory=examples), name="examples")

    # Mount last so API routes always take precedence. No build step or external CDN.
    frontend = PROJECT_ROOT / "frontend"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
