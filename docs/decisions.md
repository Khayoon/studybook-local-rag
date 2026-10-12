# Engineering decisions

The project prioritizes an inspectable local workflow: import documents, retrieve evidence, invoke a separately operated model, and let the reader trace an answer back to its sources. These choices keep the initial application understandable while exposing the limits that matter.

## A reusable Python core with a small browser client

`NotebookStore` contains the document and RAG behavior, while FastAPI handles HTTP validation and serves static assets. The CLI calls the same store rather than implementing a second retrieval pipeline. This makes ingestion, retrieval, and generation testable without the browser.

Vanilla JavaScript and CSS keep installation to one Python environment and one server. The tradeoff is manual client-side state and rendering rather than framework-provided components. A component system would become more useful as the interface grows.

## Chroma for vectors, SQLite for source records

Chroma supplies persistent vector storage, similarity search, and document metadata filters. SQLite holds the source library, full extracted text, chunk records, and saved study material. Keeping those records accessible separately makes source reading and broad studio sampling independent of the embedding service.

The tradeoff is duplicated chunk text and coordinated writes across two stores. Failure cleanup exists, but there is no cross-store transaction. Crash recovery and index reconciliation are sensible next steps before treating this as a large document archive.

## A lexical default that works before a model is installed

The built-in embedding implementation hashes normalized word counts into vectors. It is deterministic, works offline after dependencies are installed, and exercises the same Chroma interface as a semantic encoder. That lets users inspect the product and developers run meaningful tests without model weights or GPU access.

It also has clear weaknesses: hash collisions, no learned meaning, and weak paraphrase or cross-language matching. The interface identifies this mode as a built-in index, and chat responses disclose the limitation. The optional local semantic embedding endpoint is the extension point; it has not been quality-benchmarked against a real embedding model.

Embedding identity includes the mode and relevant model/chunking configuration. A settings change that would mix incompatible vectors is rejected while sources remain indexed. The current recovery is explicit deletion and reimport; a future reindex job could preserve the library while replacing its vectors.

## Source selection is an API contract

Every dashboard question and studio request includes selected document IDs. Retrieval applies those IDs as Chroma filters before returning evidence. Empty selection means no evidence, and the frontend clears the current conversation when the selection changes.

This behavior prevents a common source-scope surprise: an answer appearing to use only the selected document while actually drawing on the whole library. Tests verify both exclusion of unselected sources and refusal to call the model for an empty chat selection.

## Citations are checked as provenance, not truth

Chunk metadata is attached during ingestion and carried through retrieval. Citation links are built from that metadata, never from filenames or URLs invented by the model. Unknown source markers are visibly rejected.

This is a useful, testable guarantee, but it does not establish that a sentence is supported by its cited text. Automated entailment checks or human evaluation would address a different problem. Keeping that distinction explicit avoids presenting clickable citations as proof of correctness.

## Different evidence strategies for questions and overviews

Question answering uses the most similar chunks from the selected sources. Studio overviews use evenly spaced excerpts from each selected document, ensuring that a longer or more keyword-dense source does not exclude every other source.

The studio approach improves representation across documents, but it can skip an important passage. Output includes coverage counts and a sampling notice. Hierarchical summaries, token-aware budgets, and a coverage evaluation set would be useful improvements before supporting larger corpora.

## Local inference stays behind an explicit boundary

The backend accepts only loopback model endpoints, disables redirects and environment proxies, and does not start model processes. Health checks and settings saves do not test a connection. Document instructions are treated as untrusted source text, and generated text is escaped before display.

These controls suit a personal desktop application. They do not add authentication, sandbox PDF parsing at the OS level, guarantee resistance to model prompt injection, or control the independently operated inference service. A hosted or multi-user version would need a separate deployment and isolation design.

## Tests exercise the boundary without requiring inference

The offline suite uses temporary data directories and deterministic text. It verifies actual persistence and retrieval, page provenance, selected-source isolation, upload failures, citation validation, and Markdown export. In-memory HTTP transport tests run the real LangChain chat and embedding clients, including raw-text embedding inputs and response handling.

The browser fixture is separate from production, blocks model HTTP calls, and labels all canned responses. It enables repeatable checks of citation navigation, studio saving, and downloads without presenting test text as real model output.

The remaining acceptance work is explicit: run a chosen local chat and embedding model against a small labeled corpus, assess answer support and retrieval recall, and record the exact model/settings used. Passing transport tests alone does not resolve those questions.

## Focused next improvements

1. **Evaluate retrieval and generation:** add a labeled corpus with expected source passages and evaluate lexical versus local semantic retrieval, including paraphrases and multilingual questions.
2. **Manage context by tokens:** make model context limits configurable and replace fixed character/excerpt budgets with a documented token budget.
3. **Recover and reindex safely:** add an index reconciliation check and a reindex operation that preserves the source library.
4. **Improve long-running work:** add progress and cancellation for ingestion/generation, followed by response streaming where the selected server supports it.
5. **Expand document support deliberately:** introduce optional local OCR and measure extraction quality on tables and multi-column PDFs before promising layout fidelity.
