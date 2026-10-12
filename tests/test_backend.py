"""Offline backend acceptance checks; these tests never contact a chat model."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from backend.core import AppError, ModelSettings, NotebookStore, parse_document, sanitize_citations, validate_base_url
from backend.main import create_app


def make_two_page_pdf(oversized_stream: bool = False) -> bytes:
    """Create an original, small PDF fixture without another PDF library."""
    first = b"BT /F1 12 Tf 50 750 Td (First page: glossary preparation.) Tj ET"
    first_filter = b""
    if oversized_stream:
        first = zlib.compress(b" " * (21 * 1024 * 1024))
        first_filter = b" /Filter /FlateDecode"
    second = b"BT /F1 12 Tf 50 750 Td (Second page: practice review.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(first)).encode() + first_filter + b" >>\nstream\n" + first + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
        b"<< /Length " + str(len(second)).encode() + b" >>\nstream\n" + second + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


class ParsingTests(unittest.TestCase):
    def test_pdf_preserves_one_based_page_locations(self):
        pages = parse_document("original-fixture.pdf", make_two_page_pdf())
        self.assertEqual([page["page"] for page in pages], [1, 2])
        self.assertIn("glossary preparation", pages[0]["text"])
        self.assertIn("practice review", pages[1]["text"])

    def test_text_preserves_unicode(self):
        pages = parse_document("phrases.md", "# Révision\nمرحبا — bonjour".encode("utf-8"))
        self.assertEqual(len(pages), 1)
        self.assertIn("مرحبا", pages[0]["text"])

    def test_rejects_a_small_pdf_with_an_oversized_decoded_stream(self):
        data = make_two_page_pdf(oversized_stream=True)
        self.assertLess(len(data), 30_000)
        with self.assertRaises(AppError):
            parse_document("compressed-fixture.pdf", data)


class LocalEndpointTests(unittest.TestCase):
    def test_accepts_loopback_api(self):
        self.assertEqual(validate_base_url("http://127.0.0.1:8090/v1"), "http://127.0.0.1:8090/v1")

    def test_rejects_remote_or_deceptive_endpoints(self):
        invalid = [
            "https://example.com/v1",
            "http://192.168.1.10:8090/v1",
            "http://127.0.0.1.evil.example/v1",
            "http://user:password@127.0.0.1:8090/v1",
            "ftp://127.0.0.1/v1",
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_base_url(url)


class CitationTests(unittest.TestCase):
    def test_unknown_source_ids_cannot_become_source_links(self):
        evidence = [Document(page_content="An original glossary excerpt.", metadata={
            "document_id": "first-document", "document_name": "glossary.md", "page": 2, "chunk": 3,
        })]
        answer, citations, warnings = sanitize_citations("Review the glossary [S1]. Invented claim [S999].", evidence)
        self.assertEqual([citation["id"] for citation in citations], ["S1"])
        self.assertEqual(citations[0]["document_id"], "first-document")
        self.assertEqual(citations[0]["page"], 2)
        self.assertNotIn("[S999]", answer)
        self.assertIn("[unverified source]", answer)
        self.assertTrue(warnings)


class NotebookTests(unittest.TestCase):
    def setUp(self):
        local_environment = patch.dict(os.environ, {
            "STUDYBOOK_EMBEDDING_MODE": "lexical",
            "STUDYBOOK_BASE_URL": "http://127.0.0.1:8090/v1",
        })
        local_environment.start()
        self.addCleanup(local_environment.stop)
        self.directory = tempfile.TemporaryDirectory(prefix="studybook-test-", ignore_cleanup_errors=True)
        self.addCleanup(self.directory.cleanup)
        self.data_dir = Path(self.directory.name)
        self.store = NotebookStore(data_dir=self.data_dir)
        self.addCleanup(self.store.close)
        self.addCleanup(lambda: asyncio.run(self.store.http_async_client.aclose()))

    def add_sources(self):
        first = self.store.ingest(
            "glossary.md",
            b"# Glossary\nThe glossary exercise reviews five phrases before a practice session.",
        )
        second = self.store.ingest(
            "journal.txt",
            b"The learning journal records the date, a difficulty, and the next action after practice.",
        )
        return first, second

    def test_multiple_documents_are_retrievable_with_provenance(self):
        first, second = self.add_sources()
        evidence = self.store.retrieve("glossary journal practice", [first["id"], second["id"]], k=8)
        self.assertEqual({chunk.metadata["document_id"] for chunk in evidence}, {first["id"], second["id"]})
        self.assertTrue(all(chunk.page_content for chunk in evidence))

    def test_selection_excludes_other_documents_and_empty_means_none(self):
        first, second = self.add_sources()
        selected = self.store.retrieve("journal next action practice", [first["id"]], k=8)
        self.assertTrue(selected)
        self.assertTrue(all(chunk.metadata["document_id"] == first["id"] for chunk in selected))
        self.assertEqual(self.store.retrieve("glossary journal", [], k=8), [])

    def test_reimport_deduplicates_the_same_source(self):
        original = self.store.ingest("repeat.md", b"A repeated source has one library entry.")
        repeated = self.store.ingest("repeat.md", b"A repeated source has one library entry.")
        self.assertEqual(original["id"], repeated["id"])
        self.assertEqual(len(self.store.list_documents()), 1)

    def test_untrusted_filename_stays_inside_the_library(self):
        document = self.store.ingest("../../outside.md", b"This source tests filename handling.")
        self.assertNotIn("/", document["name"])
        self.assertNotIn("\\", document["name"])
        self.assertFalse((self.data_dir.parent / "outside.md").exists())
        content = self.store.document_content(document["id"])
        self.assertIn("filename handling", content["pages"][0]["text"])

    def test_document_and_index_survive_a_store_reload(self):
        first, _ = self.add_sources()
        reopened = NotebookStore(data_dir=self.data_dir)
        self.addCleanup(reopened.close)
        self.addCleanup(lambda: asyncio.run(reopened.http_async_client.aclose()))
        self.assertEqual(len(reopened.list_documents()), 2)
        evidence = reopened.retrieve("glossary phrases", [first["id"]])
        self.assertTrue(evidence)
        self.assertEqual(evidence[0].metadata["document_id"], first["id"])

    def test_pdf_retrieval_keeps_the_correct_page_number(self):
        document = self.store.ingest("pages.pdf", make_two_page_pdf())
        evidence = self.store.retrieve("glossary preparation practice review", [document["id"]], k=8)
        self.assertEqual({chunk.metadata["page"] for chunk in evidence}, {1, 2})

    def test_global_chroma_configuration_cannot_redirect_the_local_index(self):
        with patch.dict(os.environ, {
            "CHROMA_API_IMPL": "chromadb.api.fastapi.FastAPI",
            "CHROMA_SERVER_HOST": "remote.invalid",
            "CHROMA_SERVER_HTTP_PORT": "443",
            "CHROMA_OTEL_COLLECTION_ENDPOINT": "https://remote.invalid/traces",
            "CHROMA_OTEL_GRANULARITY": "all",
        }), patch("socket.socket.connect", side_effect=AssertionError("Real sockets are forbidden")):
            document = self.store.ingest("offline.md", b"This glossary stays on the local computer.")
            evidence = self.store.retrieve("glossary", [document["id"]])
        self.assertTrue(evidence)
        self.assertTrue((self.data_dir / "vectors" / "chroma.sqlite3").is_file())
        settings = self.store.vector._client.get_settings()
        self.assertEqual(settings.chroma_otel_granularity, "none")
        self.assertFalse(settings.chroma_otel_collection_endpoint)

    def test_failed_later_index_batch_removes_partial_source_and_keeps_existing_data(self):
        existing = self.store.ingest("existing.md", b"The existing glossary source must remain intact.")
        vector = self.store.vector
        original_add = vector.add_documents
        attempted_batches = []

        def fail_second_batch(documents, ids):
            attempted_batches.append(ids)
            if len(attempted_batches) == 2:
                raise RuntimeError("Simulated embedding failure after the first batch")
            return original_add(documents, ids=ids)

        with patch.object(vector, "add_documents", side_effect=fail_second_batch):
            with self.assertRaises(AppError):
                self.store.ingest("interrupted.md", b"A glossary practice session reviews original phrases. " * 2000)
        self.assertEqual(len(attempted_batches), 2)
        self.assertEqual([document["id"] for document in self.store.list_documents()], [existing["id"]])
        self.assertEqual(len(list((self.data_dir / "uploads").iterdir())), 1)
        indexed = vector.get(include=["metadatas"])
        self.assertTrue(indexed["ids"])
        self.assertEqual({metadata["document_id"] for metadata in indexed["metadatas"]}, {existing["id"]})
        self.assertTrue(self.store.retrieve("glossary", [existing["id"]]))

    def test_delete_removes_original_text_and_vectors_but_keeps_other_sources(self):
        first, second = self.add_sources()
        original_file, _ = self.store.document_file(first["id"])
        self.store.delete_document(first["id"])
        self.assertFalse(original_file.exists())
        self.assertEqual([document["id"] for document in self.store.list_documents()], [second["id"]])
        with self.assertRaises(AppError) as error:
            self.store.document_content(first["id"])
        self.assertEqual(error.exception.status, 404)
        self.assertEqual(self.store.vector.get(where={"document_id": first["id"]})["ids"], [])
        self.assertTrue(self.store.retrieve("journal", [second["id"]]))


class ApiTests(unittest.TestCase):
    def setUp(self):
        local_environment = patch.dict(os.environ, {
            "STUDYBOOK_EMBEDDING_MODE": "lexical",
            "STUDYBOOK_BASE_URL": "http://127.0.0.1:8090/v1",
        })
        local_environment.start()
        self.addCleanup(local_environment.stop)
        self.directory = tempfile.TemporaryDirectory(prefix="studybook-api-test-", ignore_cleanup_errors=True)
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(data_dir=self.directory.name)
        self.client = self.enterContext(TestClient(self.app))

    def upload(self):
        response = self.client.post("/api/documents", files=[
            ("files", ("phrases.md", b"The glossary practice uses five phrases.", "text/markdown")),
            ("files", ("journal.txt", b"The journal records a review action after practice.", "text/plain")),
        ])
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["errors"], [])
        self.assertEqual(len(payload["documents"]), 2)
        return payload["documents"]

    def test_health_is_passive_and_cross_origin_writes_are_rejected(self):
        with patch.object(self.app.state.store.http_client, "request", side_effect=AssertionError("Network call")):
            health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertFalse(health.json()["model_connected"])
        result = self.client.post("/api/chat", json={"message": "practice", "document_ids": []}, headers={"Origin": "https://untrusted.example"})
        self.assertEqual(result.status_code, 403)

    def test_chat_uses_selected_source_and_rejects_unknown_citations(self):
        documents = self.upload()
        selected = documents[0]["id"]
        with patch.object(self.app.state.store, "invoke", return_value="Review five phrases [S1]. Unverified [S999].") as invoke:
            response = self.client.post("/api/chat", json={"message": "How many glossary phrases?", "document_ids": [selected]})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual({citation["document_id"] for citation in result["citations"]}, {selected})
        self.assertNotIn("[S999]", result["answer"])
        supplied_context = invoke.call_args.args[0][-1].content
        self.assertIn("phrases.md", supplied_context)
        self.assertNotIn("journal.txt", supplied_context)

    def test_empty_selection_does_not_call_model(self):
        self.upload()
        with patch.object(self.app.state.store, "invoke", side_effect=AssertionError("Must not invoke")):
            response = self.client.post("/api/chat", json={"message": "practice", "document_ids": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Select", response.json()["error"])

    def test_missing_evidence_does_not_call_model(self):
        documents = self.upload()
        with patch.object(self.app.state.store, "invoke", side_effect=AssertionError("Must not invoke")):
            response = self.client.post("/api/chat", json={
                "message": "xylophonic quasar", "document_ids": [documents[0]["id"]],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["citations"], [])
        self.assertIn("could not find matching evidence", response.json()["answer"])

    def test_studio_export_download_contains_content_and_verified_source_excerpts(self):
        documents = self.upload()
        with patch.object(self.app.state.store, "invoke", return_value="## Overview\nRévision of glossary phrases [S1]."):
            artifact = self.client.post("/api/studio", json={
                "kind": "study_guide", "document_ids": [documents[0]["id"]],
            }).json()
        response = self.client.get(f"/api/studio/{artifact['id']}/export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="studybook-study_guide.md"')
        self.assertIn("text/markdown", response.headers["content-type"])
        self.assertIn("charset=utf-8", response.headers["content-type"])
        self.assertTrue(response.text.startswith("# Study guide\n\n"))
        self.assertIn("Révision of glossary phrases [S1]", response.text)
        self.assertIn("## Source excerpts", response.text)
        self.assertIn("- [S1] phrases.md, page 1, chunk 1", response.text)
        self.assertIn("The glossary practice uses five phrases.", response.text)
        self.assertEqual(self.client.get("/api/studio/missing-artifact/export").status_code, 404)

    def test_studio_artifact_includes_each_selected_document_and_persists(self):
        documents = self.upload()
        selected = [document["id"] for document in documents]
        with patch.object(self.app.state.store, "invoke", return_value="## Overview\nGlossary [S1]; journal [S2].") as invoke:
            response = self.client.post("/api/studio", json={"kind": "study_guide", "document_ids": selected})
        self.assertEqual(response.status_code, 200)
        artifact = response.json()
        self.assertEqual({citation["document_id"] for citation in artifact["citations"]}, set(selected))
        self.assertIn("Coverage:", artifact["content"])
        context = invoke.call_args.args[0][-1].content
        self.assertIn("phrases.md", context)
        self.assertIn("journal.txt", context)
        saved = self.client.get("/api/studio").json()["artifacts"]
        self.assertEqual(saved[0]["id"], artifact["id"])

    def test_embedding_change_requires_an_empty_collection(self):
        self.upload()
        settings = self.client.get("/api/settings").json()
        settings["embedding_mode"] = "local_openai"
        response = self.client.put("/api/settings", json=settings)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/api/settings").json()["embedding_mode"], "lexical")

    def test_batch_reports_invalid_file_and_keeps_successful_upload(self):
        response = self.client.post("/api/documents", files=[
            ("files", ("good.txt", b"An original source for practice.", "text/plain")),
            ("files", ("unsupported.exe", b"not a supported source", "application/octet-stream")),
        ])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["documents"]), 1)
        self.assertEqual(len(response.json()["errors"]), 1)
        self.assertEqual(len(self.client.get("/api/documents").json()["documents"]), 1)


class OpenAITransportTests(unittest.TestCase):
    """Exercise the actual LangChain/OpenAI clients using in-memory HTTP only."""

    def setUp(self):
        environment = patch.dict(os.environ, {
            "STUDYBOOK_EMBEDDING_MODE": "lexical",
            "STUDYBOOK_BASE_URL": "http://127.0.0.1:8090/v1",
            "STUDYBOOK_MODEL": "offline-chat-fixture",
            "STUDYBOOK_API_KEY": "offline-test-key",
        })
        environment.start()
        self.addCleanup(environment.stop)
        directory = tempfile.TemporaryDirectory(prefix="studybook-transport-test-", ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.store = NotebookStore(data_dir=directory.name)
        self.store.http_client.close()
        asyncio.run(self.store.http_async_client.aclose())
        self.requests = []
        self.response_status = 200
        transport = httpx.MockTransport(self.handle_request)
        self.store.http_client = httpx.Client(transport=transport, trust_env=False, follow_redirects=False)
        self.store.http_async_client = httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False)
        self.addCleanup(self.store.close)
        self.addCleanup(lambda: asyncio.run(self.store.http_async_client.aclose()))

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.host, "127.0.0.1")
        self.assertEqual(request.url.port, 8090)
        self.assertEqual(request.headers["authorization"], "Bearer offline-test-key")
        payload = json.loads(request.content)
        self.requests.append((request.url.path, payload))
        if self.response_status == 307:
            return httpx.Response(307, headers={"location": "https://remote.invalid/v1/chat/completions"})
        if self.response_status != 200:
            return httpx.Response(self.response_status, json={"error": {"message": "Offline fixture failure"}})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(200, json={
                "id": "chatcmpl-offline-fixture", "object": "chat.completion", "created": 0,
                "model": "offline-chat-fixture",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Review five glossary phrases [S1]. Unknown reference [S999]."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 42, "completion_tokens": 16, "total_tokens": 58},
            })
        if request.url.path == "/v1/embeddings":
            texts = payload["input"]
            if isinstance(texts, str):
                texts = [texts]
            self.assertTrue(texts)
            self.assertTrue(all(isinstance(text, str) for text in texts), "Local embedding input must be raw text, not token IDs")
            data = []
            for index, text in enumerate(texts):
                vector = [1.0, 0.0, 0.0, 0.0] if "glossary" in text.casefold() else [0.0, 1.0, 0.0, 0.0]
                data.append({"object": "embedding", "index": index, "embedding": vector})
            return httpx.Response(200, json={
                "object": "list", "model": "offline-embedding-fixture", "data": data,
                "usage": {"prompt_tokens": 12, "total_tokens": 12},
            })
        self.fail(f"Unexpected in-memory API path: {request.url.path}")

    def test_real_chat_client_serializes_context_and_returns_verified_citations(self):
        document = self.store.ingest("glossary.md", b"The glossary practice reviews five phrases.")
        with patch("socket.create_connection", side_effect=AssertionError("Real sockets are forbidden")):
            answer = self.store.chat("How many glossary phrases should I review?", [document["id"]], [])
        self.assertEqual(len(self.requests), 1)
        route, payload = self.requests[0]
        self.assertEqual(route, "/v1/chat/completions")
        self.assertEqual(payload["model"], "offline-chat-fixture")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        context = payload["messages"][-1]["content"]
        self.assertIsInstance(context, str)
        self.assertIn("The glossary practice reviews five phrases.", context)
        self.assertIn("How many glossary phrases should I review?", context)
        self.assertEqual([citation["id"] for citation in answer["citations"]], ["S1"])
        self.assertEqual(answer["citations"][0]["document_id"], document["id"])
        self.assertIn("[unverified source]", answer["answer"])
        self.assertTrue(self.store.health()["model_connected"])

    def test_real_embedding_client_sends_raw_text_for_ingestion_and_retrieval(self):
        self.store.set_settings(ModelSettings(
            base_url="http://127.0.0.1:8090/v1", model="offline-chat-fixture",
            embedding_mode="local_openai", embedding_model="offline-embedding-fixture",
        ))
        with patch("socket.create_connection", side_effect=AssertionError("Real sockets are forbidden")):
            glossary = self.store.ingest("glossary.md", "The bilingual glossary includes مرحبا and bonjour.".encode("utf-8"))
            self.store.ingest("journal.md", b"The learning journal records the next review action.")
            evidence = self.store.retrieve("glossary phrases", [glossary["id"]], k=4)
        self.assertTrue(evidence)
        self.assertTrue(all(chunk.metadata["document_id"] == glossary["id"] for chunk in evidence))
        self.assertEqual(len(self.requests), 3)
        self.assertTrue(all(route == "/v1/embeddings" for route, _ in self.requests))
        self.assertTrue(all(payload["model"] == "offline-embedding-fixture" for _, payload in self.requests))
        inputs = [text for _, payload in self.requests for text in payload["input"]]
        self.assertIn("The bilingual glossary includes مرحبا and bonjour.", inputs)
        self.assertIn("glossary phrases", inputs)

    def test_model_failure_keeps_sources_and_resets_connection_status(self):
        document = self.store.ingest("glossary.md", b"A glossary contains five phrases.")
        self.store.model_connected = True
        self.response_status = 503
        with patch("socket.socket.connect", side_effect=AssertionError("Real sockets are forbidden")):
            with self.assertRaises(AppError) as error:
                self.store.chat("glossary phrases", [document["id"]])
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(self.store.health()["model_connected"])
        self.assertEqual(self.store.list_documents()[0]["id"], document["id"])
        self.assertIn("five phrases", self.store.document_content(document["id"])["pages"][0]["text"])

    def test_chat_redirect_is_rejected_without_following_remote_location(self):
        document = self.store.ingest("glossary.md", b"A glossary contains five phrases.")
        self.response_status = 307
        with patch("socket.socket.connect", side_effect=AssertionError("Real sockets are forbidden")):
            with self.assertRaises(AppError):
                self.store.chat("glossary phrases", [document["id"]])
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(self.store.health()["model_connected"])


if __name__ == "__main__":
    unittest.main()
