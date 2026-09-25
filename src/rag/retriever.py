"""
Document Retriever Module for MRPL AI Workbench.
Executes pre-retrieval security filtered vector similarity search for user questions,
ensuring unauthorized document chunks NEVER enter LLM context.
"""

import logging
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.audit.hash_ledger import AuditLedger
from src.auth.models import User, UserRole
from src.auth.roles import PERM_RAG_RETRIEVE, PERM_RAG_SEARCH
from src.rag.embeddings import BaseEmbeddingProvider
from src.rag.vector_store import BaseVectorStore

logger = logging.getLogger("MRPL.RAG.Retriever")



class DocumentRetriever:
    """
    Document Retriever executing pre-retrieval ABAC-filtered vector similarity search
    against the local ChromaDB vector store.
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
        default_top_k: Optional[int] = None,
        audit_ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.default_top_k = default_top_k or settings.RAG_TOP_K
        self.audit_ledger = audit_ledger or AuditLedger()

    def retrieve(
        self,
        query: str,
        user: Optional[User] = None,
        top_k: Optional[int] = None,
        collection_name: Optional[str] = None,
        where_override: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top_k relevant text chunks for a query text with PRE-RETRIEVAL security filtering.

        Args:
            query: User question string.
            user: Authenticated User domain object.
            top_k: Optional top_k integer limit.
            collection_name: Optional target collection name.
            where_override: Optional explicit filter override.

        Returns:
            List of dictionary items containing matched text and preserved source metadata.
        """
        cleaned_query = query.strip() if query else ""
        if not cleaned_query:
            return []

        k = top_k or self.default_top_k

        # 1. Pre-Retrieval Authorization Check & Filter Construction
        where_clause: Optional[Dict[str, Any]] = where_override

        if user:
            # Verify basic RBAC permission for RAG search
            if not user.has_permission(PERM_RAG_SEARCH) and not user.has_permission(PERM_RAG_RETRIEVE):
                logger.warning(f"[RAG SECURITY DENY] User '{user.email}' lacks RAG retrieve permission.")
                self.audit_ledger.append_event(
                    event_type="RAG_ACCESS_DENIED",
                    request_id=f"req_rag_deny_{user.user_id}",
                    user_id=user.user_id,
                    workspace_id=user.workspace_id,
                    operation="RAG_SEARCH",
                    result="DENIED",
                    metadata={"reason": "NO_RAG_PERMISSION", "role": user.role},
                )
                return []

            # Build Pre-Retrieval ChromaDB ABAC & Position Metadata Filter
            # Admin and Auditor roles can search across workspaces, but clearance level is still enforced!
            if user.role in {UserRole.AI_IT_ADMIN, UserRole.AUDITOR_DOC_CONTROLLER}:
                where_clause = {"classification_level": {"$lte": user.clearance_level}}
            else:
                user_pos = user.get_effective_position() if hasattr(user, "get_effective_position") else user.department
                user_dept = user.department or "Operations"
                where_clause = {
                    "$and": [
                        {"classification_level": {"$lte": user.clearance_level}},
                        {
                            "$or": [
                                {"workspace_id": {"$eq": user.workspace_id}},
                                {"position": {"$eq": user_pos}},
                                {"department": {"$eq": user_dept}},
                            ]
                        }
                    ]
                }

        # 2. Generate Query Vector Embedding
        query_embedding = self.embedding_provider.embed_text(cleaned_query)

        # 3. Perform Filtered Vector Similarity Search in ChromaDB
        search_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            collection_name=collection_name,
            where=where_clause,
        )

        retrieved_chunks: List[Dict[str, Any]] = []
        for item in search_results:
            meta = item.get("metadata", {})
            retrieved_chunks.append(
                {
                    "vector_id": item.get("id"),
                    "id": meta.get("record_id") or meta.get("id") or item.get("id"),
                    "text": item.get("document", ""),
                    "score": item.get("score", 0.0),
                    "distance": item.get("distance", 0.0),
                    "document_id": meta.get("document_id", "unknown"),
                    "filename": meta.get("filename", "unknown"),
                    "file_hash": meta.get("file_hash", ""),
                    "chunk_id": meta.get("chunk_id", 0),
                    "page": meta.get("page", 1),
                    "file_extension": meta.get("file_extension", ""),
                    "workspace_id": meta.get("workspace_id", "Operations"),
                    "classification_level": meta.get("classification_level", 1),
                    "department": meta.get("department", ""),
                    "position": meta.get("position", ""),
                    "topic": meta.get("topic", ""),
                    "document_type": meta.get("document_type", ""),
                }
            )

        user_info = f"user='{user.email}' ({user.workspace_id}, Level {user.clearance_level})" if user else "user='anonymous'"
        logger.info(
            f"[PRE-RETRIEVAL FILTERED SEARCH] {user_info} | "
            f"query='{cleaned_query[:40]}...' | top_k={k} | "
            f"retrieved_count={len(retrieved_chunks)}"
        )

        return retrieved_chunks
