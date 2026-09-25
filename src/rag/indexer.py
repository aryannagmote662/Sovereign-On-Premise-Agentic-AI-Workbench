"""
Document Indexer Module for MRPL AI Workbench.
Indexes Phase 5 document chunks, generates embeddings, and persists vectors and source metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.rag.embeddings import BaseEmbeddingProvider
from src.rag.vector_store import BaseVectorStore
from src.schemas.document import DocumentChunkSchema

logger = logging.getLogger("MRPL.RAG.Indexer")


class DocumentIndexer:
    """
    Document Indexer responsible for generating text chunk embeddings
    and storing vectors with rich source metadata into the local vector store.
    Prevents duplicate vector indexing using document hash and identity filtering.
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider

    def index_document(
        self,
        filename: str,
        file_hash: str,
        chunks: List[DocumentChunkSchema],
        document_id: Optional[str] = None,
        file_extension: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Index text chunks into local vector store.

        Args:
            filename: Original file name.
            file_hash: SHA-256 hash digest of document content.
            chunks: List of DocumentChunkSchema items from Phase 5 pipeline.
            document_id: Optional unique document ID string.
            file_extension: Optional extension (e.g. .pdf).
            metadata: Optional additional metadata fields.
            collection_name: Optional target vector collection name.

        Returns:
            Dictionary containing indexing outcome details.
        """
        if not chunks:
            return {
                "status": "SKIPPED",
                "document_id": document_id or f"doc_{file_hash[:12]}",
                "filename": filename,
                "indexed_chunks_count": 0,
                "message": "No text chunks provided for indexing.",
            }

        doc_id = document_id or f"doc_{file_hash[:12]}"
        meta_base = metadata or {}
        now_utc = datetime.now(timezone.utc).isoformat()

        # Deduplication safeguard: Purge existing chunks matching document_id or file_hash
        self.vector_store.delete(where={"document_id": doc_id}, collection_name=collection_name)

        # 1. Extract Texts & Generate Embeddings
        chunk_texts = [c.content for c in chunks]
        embeddings = self.embedding_provider.embed_documents(chunk_texts)

        # 2. Build Chunk Vector IDs & Rich Source Metadatas
        vector_ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for c in chunks:
            vector_id = f"{doc_id}_chunk_{c.chunk_id}"
            vector_ids.append(vector_id)

            chunk_meta = {
                "document_id": doc_id,
                "filename": filename,
                "file_hash": file_hash,
                "chunk_id": c.chunk_id,
                "page": meta_base.get("page", 1),
                "file_extension": file_extension or "",
                "start_char": c.start_char,
                "end_char": c.end_char,
                "word_count": c.word_count,
                "workspace_id": str(meta_base.get("workspace_id", "Operations")).strip(),
                "classification_level": int(meta_base.get("classification_level", 1)),
                "indexed_at": now_utc,
            }

            metadatas.append(chunk_meta)

        # 3. Store in Local Vector Database
        self.vector_store.add(
            ids=vector_ids,
            embeddings=embeddings,
            documents=chunk_texts,
            metadatas=metadatas,
            collection_name=collection_name,
        )

        logger.info(
            f"[DOCUMENT INDEXER] indexed document_id='{doc_id}' | "
            f"filename='{filename}' | "
            f"hash={file_hash[:12]} | "
            f"chunks_count={len(chunks)}"
        )

        return {
            "status": "SUCCESS",
            "document_id": doc_id,
            "filename": filename,
            "indexed_chunks_count": len(chunks),
            "message": f"Successfully indexed {len(chunks)} chunks into vector store.",
        }

    def delete_document(
        self,
        document_id: str,
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Delete all indexed vector chunks belonging to a document_id.

        Args:
            document_id: Target document ID.
            collection_name: Target collection name.

        Returns:
            Number of deleted chunks.
        """
        deleted_count = self.vector_store.delete(
            where={"document_id": document_id},
            collection_name=collection_name,
        )
        logger.info(f"[DOCUMENT INDEXER] deleted document_id='{document_id}' | count={deleted_count}")
        return deleted_count
