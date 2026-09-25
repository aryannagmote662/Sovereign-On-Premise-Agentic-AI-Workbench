"""
RAG Service Module for MRPL AI Workbench.
Orchestrates indexing, vector retrieval, context building, and grounded Qwen LLM synthesis.
Never communicates directly with Ollama network endpoints.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from config.settings import settings
from src.rag.context_builder import ContextBuilder
from src.rag.embeddings import BaseEmbeddingProvider, get_embedding_provider
from src.rag.indexer import DocumentIndexer
from src.rag.retriever import DocumentRetriever
from src.rag.vector_store import BaseVectorStore, ChromaVectorStore
from src.schemas.document import DocumentChunkSchema
from src.schemas.rag import RAGQueryResponse, SourceCitationSchema

if TYPE_CHECKING:
    from src.models.base_model import BaseModel

logger = logging.getLogger("MRPL.RAG.Service")


class RAGService:
    """
    RAG Service layer orchestrating document indexing, vector retrieval,
    context building, and grounded text generation using QwenManager.
    """

    def __init__(
        self,
        vector_store: Optional[BaseVectorStore] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        qwen_manager: Optional[Any] = None,
        context_builder: Optional[ContextBuilder] = None,
    ) -> None:
        from src.models.qwen_manager import QwenManager

        self.vector_store = vector_store or ChromaVectorStore()
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.qwen_manager = qwen_manager or QwenManager()
        self.context_builder = context_builder or ContextBuilder()

        self.indexer = DocumentIndexer(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
        )
        self.retriever = DocumentRetriever(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
        )

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
        Index Phase 5 document chunks into local vector store.

        Args:
            filename: Name of file.
            file_hash: SHA-256 hash.
            chunks: List of DocumentChunkSchema items.
            document_id: Optional custom document ID.
            file_extension: Optional file extension.
            metadata: Optional additional metadata.
            collection_name: Optional target collection name.

        Returns:
            Dictionary with status, document_id, filename, indexed_chunks_count.
        """
        return self.indexer.index_document(
            filename=filename,
            file_hash=file_hash,
            chunks=chunks,
            document_id=document_id,
            file_extension=file_extension,
            metadata=metadata,
            collection_name=collection_name,
        )

    async def query(
        self,
        query: str,
        user: Optional[Any] = None,
        top_k: Optional[int] = None,
        collection_name: Optional[str] = None,
    ) -> RAGQueryResponse:
        """
        Execute grounded RAG query flow with pre-retrieval authorization.
        """
        start_time = time.perf_counter()
        cleaned_query = (query or "").strip()

        # 1. Retrieve Relevant Vector Chunks with Pre-Retrieval Authorization Filter
        retrieved_chunks = self.retriever.retrieve(
            query=cleaned_query,
            user=user,
            top_k=top_k,
            collection_name=collection_name,
        )


        # 2. Build Compact Context Payload & Citations
        built_context = self.context_builder.build_context(
            retrieved_chunks=retrieved_chunks,
            query=cleaned_query,
        )

        # 3. Grounding Fallback: If context is insufficient/empty, return explicit fallback
        if not built_context.has_sufficient_context:
            exec_time = time.perf_counter() - start_time
            return RAGQueryResponse(
                answer="The available documents do not contain sufficient information to answer this query.",
                sources=[],
                query=cleaned_query,
                model_used=self.qwen_manager.model_name,
                tokens_generated=14,
                execution_time_seconds=round(exec_time, 4),
                status="FALLBACK_NO_CONTEXT",
            )

        # 4. Generate Grounded Answer using QwenManager
        generated_answer = self.qwen_manager.generate(
            prompt=built_context.grounded_prompt,
            temperature=0.2,  # Low temperature for strict factual adherence
        )

        exec_time = time.perf_counter() - start_time
        tokens = len(generated_answer.split()) if generated_answer else 0

        logger.info(
            f"[RAG SERVICE] query='{cleaned_query[:40]}...' | "
            f"model='{self.qwen_manager.model_name}' | "
            f"sources_count={len(built_context.sources)} | "
            f"exec_time={exec_time:.3f}s"
        )

        return RAGQueryResponse(
            answer=generated_answer,
            sources=built_context.sources,
            query=cleaned_query,
            model_used=self.qwen_manager.model_name,
            tokens_generated=tokens,
            execution_time_seconds=round(exec_time, 4),
            status="SUCCESS",
        )

    def delete_document(
        self,
        document_id: str,
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Delete document chunks by document_id.
        """
        return self.indexer.delete_document(
            document_id=document_id,
            collection_name=collection_name,
        )

    def health(self) -> Dict[str, Any]:
        """
        Query RAG subsystem health status.
        """
        vector_health = self.vector_store.health()
        embedding_health = self.embedding_provider.health()
        qwen_health = self.qwen_manager.health()

        return {
            "status": "healthy" if settings.RAG_ENABLED else "disabled",
            "rag_enabled": settings.RAG_ENABLED,
            "collection_name": settings.RAG_COLLECTION_NAME,
            "total_chunks_indexed": self.vector_store.count(),
            "embedding_provider": embedding_health,
            "vector_store": vector_health,
            "llm_manager": {
                "model_name": self.qwen_manager.model_name,
                "status": qwen_health,
            },
        }
