"""
MRPL Knowledge Base Initialization & Ingestion Engine.
Permanently ingests and indexes the canonical MRPL Generic Knowledge Base (JSONL)
into local persistent ChromaDB with duplicate protection, metadata preservation,
position-based RBAC tags, and startup hash check mechanisms.
"""

import sys
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Base Directory Resolution
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import settings
from src.rag.embeddings import get_embedding_provider
from src.rag.vector_store import ChromaVectorStore
from src.schemas.document import DocumentChunkSchema

logger = logging.getLogger("MRPL.RAG.IngestMRPL")

CANONICAL_JSONL_PATH = BASE_DIR / "documents" / "knowledge_base" / "mrpl" / "mrpl_generic_knowledge_base.jsonl"
FALLBACK_JSONL_PATH = BASE_DIR / "data" / "documents" / "knowledge_base" / "mrpl" / "mrpl_generic_knowledge_base.jsonl"
MANIFEST_PATH = BASE_DIR / "data" / "cache" / "kb_manifest.json"

REQUIRED_FIELDS = {"id", "department", "position", "topic", "document_type", "content"}


class MRPLKnowledgeBaseIngester:
    """
    Ingestion manager for MRPL Generic Knowledge Base.
    Supports deterministic chunk IDs, metadata preservation, duplicate protection,
    and startup checksum validation.
    """

    def __init__(self, jsonl_path: Optional[Path] = None):
        self.jsonl_path = jsonl_path or (CANONICAL_JSONL_PATH if CANONICAL_JSONL_PATH.exists() else FALLBACK_JSONL_PATH)
        self.vector_store = ChromaVectorStore()
        self.embedding_provider = get_embedding_provider()

    def get_dataset_hash(self) -> str:
        """Calculate SHA-256 hash of dataset file for change detection."""
        if not self.jsonl_path.exists():
            return ""
        return hashlib.sha256(self.jsonl_path.read_bytes()).hexdigest()

    def load_and_validate_jsonl(self) -> List[Dict[str, Any]]:
        """
        Load and validate records from JSONL file.
        Returns list of validated record dictionaries.
        """
        if not self.jsonl_path.exists():
            raise FileNotFoundError(f"Canonical dataset not found at '{self.jsonl_path}'")

        records: List[Dict[str, Any]] = []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    data = json.loads(clean_line)
                except json.JSONDecodeError as err:
                    raise ValueError(f"Line {idx} invalid JSON: {err}")

                missing = REQUIRED_FIELDS - set(data.keys())
                if missing:
                    raise ValueError(f"Line {idx} (ID: {data.get('id', 'unknown')}) missing required fields: {missing}")

                records.append(data)

        return records

    def ingest(self, force: bool = False) -> Dict[str, Any]:
        """
        Execute dataset ingestion pipeline into ChromaDB with duplicate protection.
        """
        records = self.load_and_validate_jsonl()
        current_hash = self.get_dataset_hash()

        # Startup check: if manifest exists and matches current hash and vector store is non-empty, skip unless forced
        if not force and MANIFEST_PATH.exists():
            try:
                manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                if manifest_data.get("dataset_hash") == current_hash and self.vector_store.count() >= len(records):
                    logger.info("[KB STARTUP CHECK] Knowledge Base is up-to-date. Skipping re-indexing.")
                    return {
                        "status": "up_to_date",
                        "dataset_name": "MRPL Generic Knowledge Base",
                        "total_records": len(records),
                        "indexed_chunks": 0,
                        "skipped_chunks": len(records),
                        "errors": 0,
                        "message": "Knowledge Base dataset unchanged; existing vector store reused.",
                    }
            except Exception as e:
                logger.warning(f"Manifest read notice: {e}")

        indexed_count = 0
        skipped_count = 0
        error_count = 0

        for record in records:
            rec_id = record["id"]
            content = record["content"].strip()
            item_hash = hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()

            # Deterministic chunk ID
            chunk_id_str = f"{rec_id}-chunk-000"

            # Check duplicate in ChromaDB
            try:
                existing = self.vector_store.get_by_id(chunk_id_str)
                if not force and existing and existing.get("metadata", {}).get("item_hash") == item_hash:
                    skipped_count += 1
                    continue
            except Exception:
                pass

            try:
                # Generate embedding
                embedding = self.embedding_provider.embed_text(content)

                # Build preserved metadata payload
                metadata = {
                    "document_id": rec_id,
                    "record_id": rec_id,
                    "id": rec_id,
                    "filename": self.jsonl_path.name,
                    "department": record["department"],
                    "position": record["position"],
                    "topic": record["topic"],
                    "document_type": record["document_type"],
                    "file_hash": item_hash,
                    "item_hash": item_hash,
                    "chunk_id": 0,
                    "page": 1,
                    "workspace_id": record.get("department", "Operations"),
                    "classification_level": 1,
                    "is_generic_kb": True,
                    "synthetic_notice": "Generic refinery knowledge dataset for demonstration.",
                }

                # Upsert into ChromaDB
                self.vector_store.add(
                    ids=[chunk_id_str],
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                )
                indexed_count += 1
            except Exception as exc:
                logger.error(f"Failed to ingest record '{rec_id}': {exc}")
                error_count += 1

        # Save manifest
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = {
            "dataset_name": "MRPL Generic Knowledge Base",
            "version": "1.0",
            "dataset_hash": current_hash,
            "total_records": len(records),
            "indexed_count": indexed_count,
            "skipped_count": skipped_count,
            "last_ingested": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "embedding_model": settings.EMBEDDING_MODEL,
            "vector_store": "ChromaDB",
        }
        MANIFEST_PATH.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

        result = {
            "status": "success" if error_count == 0 else "degraded",
            "dataset_name": "MRPL Generic Knowledge Base",
            "total_records": len(records),
            "indexed_chunks": indexed_count,
            "skipped_chunks": skipped_count,
            "errors": error_count,
            "message": f"Knowledge Base ingestion completed: {indexed_count} indexed, {skipped_count} skipped, {error_count} errors.",
        }
        return result


def main():
    print("=" * 60)
    print("  MRPL AI Workbench — Knowledge Base Ingestion Engine")
    print("=" * 60)

    try:
        force_flag = "--force" in sys.argv
        ingester = MRPLKnowledgeBaseIngester()
        res = ingester.ingest(force=force_flag)

        print(f"Status:           {res['status'].upper()}")
        print(f"Dataset:          {res['dataset_name']}")
        print(f"Total Records:    {res['total_records']}")
        print(f"Chunks Indexed:   {res['indexed_chunks']}")
        print(f"Chunks Skipped:   {res['skipped_chunks']}")
        print(f"Errors:           {res['errors']}")
        print(f"Result Message:   {res['message']}")
        print("=" * 60)
    except Exception as err:
        print(f"Ingestion failed with error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
