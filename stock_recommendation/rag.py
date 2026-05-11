from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import requests

from stock_recommendation.config import PROJECT_DIR


DEFAULT_INDEX_DIR = PROJECT_DIR / "data" / "rag" / "faiss"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".csv", ".log", ".pdf"}
SKIP_DIRS = {".git", ".venv", "__pycache__", "build", "dist", ".idea", "rag"}


@dataclass
class ChunkMeta:
    id: int
    source: str
    start: int
    end: int
    text: str


def iter_source_files(sources: list[Path]) -> Iterable[Path]:
    for source in sources:
        path = source.expanduser()
        if not path.is_absolute():
            path = PROJECT_DIR / path
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix.lower() in TEXT_EXTENSIONS:
                yield path
            continue
        for child in path.rglob("*"):
            if child.is_dir():
                continue
            if any(part in SKIP_DIRS for part in child.parts):
                continue
            if child.suffix.lower() in TEXT_EXTENSIONS:
                yield child


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise SystemExit("pypdf is required to index PDF files. Run `pip install -r requirements.txt`.") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_chars: int, overlap_chars: int) -> list[tuple[int, int, str]]:
    clean = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not clean:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    step = max(1, chunk_chars - overlap_chars)
    while start < len(clean):
        end = min(len(clean), start + chunk_chars)
        cut = clean.rfind("\n\n", start, end)
        if cut > start + chunk_chars // 2:
            end = cut
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append((start, end, chunk))
        if end >= len(clean):
            break
        start = max(end - overlap_chars, start + step)
    return chunks


def load_embedding_model(model_name: str, allow_download: bool = False):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise SystemExit("sentence-transformers is required for local RAG. Run `pip install -r requirements.txt`.") from exc
    try:
        return SentenceTransformer(model_name, local_files_only=not allow_download)
    except Exception as exc:
        if allow_download:
            raise
        raise SystemExit(
            f"Embedding model is not available locally: {model_name}. "
            "Run ingest once with `--allow-model-download`, then rerun without that flag."
        ) from exc


def embed_texts(model, texts: list[str], batch_size: int = 32) -> np.ndarray:
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype="float32")


def save_index(index_dir: Path, embeddings: np.ndarray, metadata: list[ChunkMeta], embedding_model: str) -> None:
    import faiss

    index_dir.mkdir(parents=True, exist_ok=True)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(index_dir / "index.faiss"))
    payload = {
        "embedding_model": embedding_model,
        "dimension": int(embeddings.shape[1]),
        "count": len(metadata),
        "chunks": [asdict(item) for item in metadata],
    }
    (index_dir / "metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_index(index_dir: Path) -> tuple[object, dict]:
    import faiss

    index_path = index_dir / "index.faiss"
    meta_path = index_dir / "metadata.json"
    if not index_path.exists() or not meta_path.exists():
        raise SystemExit(f"FAISS index not found in {index_dir}. Run `ingest` first.")
    return faiss.read_index(str(index_path)), json.loads(meta_path.read_text(encoding="utf-8"))


def ingest(args: argparse.Namespace) -> int:
    source_items = args.source or ["README.md", "Agent.md", "config", "data"]
    files = sorted(set(iter_source_files([Path(item) for item in source_items])))
    metadata: list[ChunkMeta] = []
    for file_path in files:
        rel = str(file_path.relative_to(PROJECT_DIR)) if file_path.is_relative_to(PROJECT_DIR) else str(file_path)
        for start, end, text in chunk_text(read_text(file_path), args.chunk_chars, args.overlap_chars):
            metadata.append(ChunkMeta(id=len(metadata), source=rel, start=start, end=end, text=text))
    if not metadata:
        raise SystemExit("No text chunks found for ingestion.")
    model = load_embedding_model(args.embedding_model, args.allow_model_download)
    embeddings = embed_texts(model, [item.text for item in metadata], args.batch_size)
    save_index(args.index_dir, embeddings, metadata, args.embedding_model)
    print(f"Indexed {len(metadata)} chunks from {len(files)} files into {args.index_dir}")
    return 0


def retrieve(args: argparse.Namespace) -> list[dict]:
    meta_path = args.index_dir / "metadata.json"
    index_path = args.index_dir / "index.faiss"
    if not index_path.exists() or not meta_path.exists():
        raise SystemExit(f"FAISS index not found in {args.index_dir}. Run `ingest` first.")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    model_name = payload.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
    model = load_embedding_model(model_name, getattr(args, "allow_model_download", False))
    query_vec = embed_texts(model, [args.query])
    import faiss

    index = faiss.read_index(str(index_path))
    scores, ids = index.search(query_vec, args.top_k)
    chunks = payload.get("chunks", [])
    results: list[dict] = []
    for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
        if idx < 0 or idx >= len(chunks):
            continue
        item = dict(chunks[idx])
        item["score"] = round(float(score), 4)
        results.append(item)
    return results


def build_context(results: list[dict], max_context_chars: int) -> str:
    parts: list[str] = []
    used = 0
    for item in results:
        block = f"Source: {item['source']}:{item['start']}\n{item['text'].strip()}"
        if used + len(block) > max_context_chars:
            remaining = max_context_chars - used
            if remaining <= 0:
                break
            block = block[:remaining]
        parts.append(block)
        used += len(block)
    return "\n\n---\n\n".join(parts)


def query(args: argparse.Namespace) -> int:
    for item in retrieve(args):
        print(f"[{item['score']}] {item['source']}:{item['start']}")
        print(item["text"][: args.preview_chars].strip())
        print()
    return 0


def ask(args: argparse.Namespace) -> int:
    results = retrieve(args)
    context = build_context(results, args.max_context_chars)
    prompt = (
        "You are a local RAG assistant for a stock recommendation project. "
        "Answer using only the context below. If the context is insufficient, say what is missing. "
        "Cite source paths from the context.\n\n"
        f"Question: {args.query}\n\nContext:\n{context}"
    )
    try:
        response = requests.post(
            f"{args.ollama_base_url.rstrip('/')}/api/generate",
            json={"model": args.ollama_model, "prompt": prompt, "stream": False},
            timeout=args.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise SystemExit(
            f"Could not reach Ollama at {args.ollama_base_url}. Start Ollama and run `ollama pull {args.ollama_model}`."
        ) from exc
    if not response.ok:
        raise SystemExit(f"Ollama request failed: HTTP {response.status_code}: {response.text[:500]}")
    data = response.json()
    print(str(data.get("response", "")).strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local RAG: sentence-transformers embeddings, FAISS vector DB, Ollama LLM.")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Build or replace the FAISS index.")
    ingest_p.add_argument("--source", action="append", default=None, help="File or directory to index. Can be repeated. Defaults to README.md, Agent.md, config, and data.")
    ingest_p.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    ingest_p.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    ingest_p.add_argument("--allow-model-download", action="store_true", help="Allow downloading the sentence-transformers model from Hugging Face if it is not cached locally.")
    ingest_p.add_argument("--batch-size", type=int, default=32)
    ingest_p.add_argument("--chunk-chars", type=int, default=1800)
    ingest_p.add_argument("--overlap-chars", type=int, default=200)
    ingest_p.set_defaults(func=ingest)

    query_p = sub.add_parser("query", help="Retrieve relevant chunks from FAISS.")
    query_p.add_argument("query")
    query_p.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    query_p.add_argument("--top-k", type=int, default=5)
    query_p.add_argument("--preview-chars", type=int, default=900)
    query_p.add_argument("--allow-model-download", action="store_true", help="Allow downloading the embedding model if it is not cached locally.")
    query_p.set_defaults(func=query)

    ask_p = sub.add_parser("ask", help="Retrieve chunks from FAISS and answer with local Ollama.")
    ask_p.add_argument("query")
    ask_p.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    ask_p.add_argument("--top-k", type=int, default=5)
    ask_p.add_argument("--allow-model-download", action="store_true", help="Allow downloading the embedding model if it is not cached locally.")
    ask_p.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL))
    ask_p.add_argument("--ollama-model", default=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))
    ask_p.add_argument("--max-context-chars", type=int, default=12000)
    ask_p.add_argument("--timeout-seconds", type=int, default=120)
    ask_p.set_defaults(func=ask)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
