"""
Vector Store Module for MRPL AI Workbench.
Provides local persistent vector database storage abstractions.
"""

import logging
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
from chromadb.config import Settings as ChromaSettings
import numpy as np

from config.settings import settings

logger = logging.getLogger("MRPL.RAG.VectorStore")


class BaseVectorStore(ABC):
    """
    Abstract Base Class contract for local vector store database implementations.
    No cloud APIs or external SaaS dependencies.
    """

    @abstractmethod
    def create_collection(self, name: str) -> None:
        """Create or get target collection in vector store."""
        pass

    @abstractmethod
    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        collection_name: Optional[str] = None,
    ) -> None:
        """Add vectors, document text, and metadata to collection."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        collection_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search collection using vector similarity query."""
        pass

    @abstractmethod
    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> int:
        """Delete entries matching IDs or metadata filters from collection."""
        pass

    @abstractmethod
    def count(self, collection_name: Optional[str] = None) -> int:
        """Count total vectors indexed in collection."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Query vector store health metrics."""
        pass


class ChromaVectorStore(BaseVectorStore):
    """
    Production-grade local persistent vector store using ChromaDB.
    Persists index on disk under settings.VECTOR_STORE_PATH.
    """

    def __init__(
        self,
        persist_dir: Optional[Union[str, Path]] = None,
        default_collection: Optional[str] = None,
    ) -> None:
        self.persist_dir = Path(persist_dir or settings.VECTOR_STORE_PATH).resolve()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.default_collection_name = default_collection or settings.RAG_COLLECTION_NAME

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.create_collection(self.default_collection_name)

    def _get_collection(self, collection_name: Optional[str] = None) -> Any:
        target_name = collection_name or self.default_collection_name
        return self.client.get_or_create_collection(name=target_name)

    def create_collection(self, name: str) -> None:
        self.client.get_or_create_collection(name=name)

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        collection_name: Optional[str] = None,
    ) -> None:
        if not ids:
            return
        collection = self._get_collection(collection_name)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        collection_name: Optional[str] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection(collection_name)
        if collection.count() == 0:
            return []

        actual_k = min(top_k, collection.count())
        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": actual_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        res = collection.query(**query_kwargs)

        results: List[Dict[str, Any]] = []
        if res and res["ids"] and res["ids"][0]:
            ids = res["ids"][0]
            docs = res["documents"][0] if res["documents"] else [""] * len(ids)
            metas = res["metadatas"][0] if res["metadatas"] else [{}] * len(ids)
            dists = res["distances"][0] if res["distances"] else [0.0] * len(ids)

            for i in range(len(ids)):
                results.append(
                    {
                        "id": ids[i],
                        "document": docs[i],
                        "metadata": metas[i],
                        "distance": dists[i],
                        "score": round(1.0 / (1.0 + dists[i]), 4),
                    }
                )
        return results

    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> int:
        collection = self._get_collection(collection_name)
        initial_count = collection.count()

        if ids:
            collection.delete(ids=ids)
        elif where:
            collection.delete(where=where)
        else:
            return 0

        final_count = collection.count()
        return max(0, initial_count - final_count)

    def get_by_id(self, item_id: str, collection_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        collection = self._get_collection(collection_name)
        try:
            res = collection.get(ids=[item_id], include=["documents", "metadatas"])
            if res and res.get("ids") and len(res["ids"]) > 0:
                doc = res["documents"][0] if res.get("documents") else ""
                meta = res["metadatas"][0] if res.get("metadatas") else {}
                return {"id": res["ids"][0], "document": doc, "metadata": meta}
        except Exception:
            pass
        return None

    def count(self, collection_name: Optional[str] = None) -> int:
        collection = self._get_collection(collection_name)
        return collection.count()

    def health(self) -> Dict[str, Any]:
        return {
            "provider": "ChromaVectorStore",
            "status": "healthy",
            "persist_dir": str(self.persist_dir),
            "local": True,
            "collections_count": len(self.client.list_collections()),
            "items_count": self.count(),
            "default_collection_items": self.count(),
            "offline_safe": not getattr(settings, "ALLOW_REMOTE_VECTOR_STORE", False),
        }


class MockVectorStore(BaseVectorStore):
    """
    In-memory vector store using NumPy cosine similarity for fast offline testing.
    """

    def __init__(self, default_collection: str = "test_collection") -> None:
        self.default_collection_name = default_collection
        self.collections: Dict[str, Dict[str, Dict[str, Any]]] = {default_collection: {}}

    def create_collection(self, name: str) -> None:
        if name not in self.collections:
            self.collections[name] = {}

    def _get_coll(self, collection_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        name = collection_name or self.default_collection_name
        self.create_collection(name)
        return self.collections[name]

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        collection_name: Optional[str] = None,
    ) -> None:
        coll = self._get_coll(collection_name)
        for idx, item_id in enumerate(ids):
            coll[item_id] = {
                "embedding": embeddings[idx],
                "document": documents[idx],
                "metadata": metadatas[idx],
            }

    @staticmethod
    def _eval_where(meta: Dict[str, Any], where: Dict[str, Any]) -> bool:
        if not where:
            return True
        if "$and" in where:
            return all(MockVectorStore._eval_where(meta, clause) for clause in where["$and"])
        if "$or" in where:
            return any(MockVectorStore._eval_where(meta, clause) for clause in where["$or"])
        for k, v in where.items():
            if isinstance(v, dict):
                meta_val = meta.get(k)
                for op, val in v.items():
                    if op == "$eq" and meta_val != val:
                        return False
                    elif op == "$ne" and meta_val == val:
                        return False
                    elif op == "$lte" and (meta_val is None or meta_val > val):
                        return False
                    elif op == "$lt" and (meta_val is None or meta_val >= val):
                        return False
                    elif op == "$gte" and (meta_val is None or meta_val < val):
                        return False
                    elif op == "$gt" and (meta_val is None or meta_val <= val):
                        return False
                    elif op == "$in" and meta_val not in val:
                        return False
            else:
                if meta.get(k) != v:
                    return False
        return True

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        collection_name: Optional[str] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        coll = self._get_coll(collection_name)
        if not coll:
            return []

        q_vec = np.array(query_embedding)
        q_norm = np.linalg.norm(q_vec)

        scored: List[Tuple[float, str, Dict[str, Any]]] = []
        for item_id, item in coll.items():
            meta = item.get("metadata", {})
            if where and not self._eval_where(meta, where):
                continue

            d_vec = np.array(item["embedding"])
            d_norm = np.linalg.norm(d_vec)
            if q_norm > 0 and d_norm > 0:
                sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
            else:
                sim = 0.0
            scored.append((sim, item_id, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_items = scored[:top_k]

        results = []
        for sim, item_id, item in top_items:
            results.append(
                {
                    "id": item_id,
                    "document": item["document"],
                    "metadata": item["metadata"],
                    "distance": round(1.0 - sim, 4),
                    "score": round(sim, 4),
                }
            )
        return results

    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> int:
        coll = self._get_coll(collection_name)
        deleted = 0
        if ids:
            for item_id in ids:
                if item_id in coll:
                    del coll[item_id]
                    deleted += 1
        elif where:
            to_delete = []
            for item_id, item in coll.items():
                meta = item["metadata"]
                match = True
                for k, v in where.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if match:
                    to_delete.append(item_id)
            for item_id in to_delete:
                del coll[item_id]
                deleted += 1
        return deleted

    def count(self, collection_name: Optional[str] = None) -> int:
        coll = self._get_coll(collection_name)
        return len(coll)

    def health(self) -> Dict[str, Any]:
        return {
            "provider": "MockVectorStore",
            "status": "healthy",
            "collections_count": len(self.collections),
            "default_collection_items": self.count(),
        }
