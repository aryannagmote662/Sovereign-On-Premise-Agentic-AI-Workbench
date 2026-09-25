"""
Comprehensive Verification Test Suite for MRPL AI Workbench Authentication,
6-Role RBAC, ABAC Policy Engine, Pre-Retrieval RAG Security Filtering, Approvals, and Audit Ledger.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth.models import User, UserRole
from src.auth.roles import (
    PERM_APPROVAL_APPROVE,
    PERM_APPROVAL_REQUEST,
    PERM_CHAT_READ,
    PERM_CODE_GENERATE,
    PERM_DOC_VIEW,
    PERM_SYSTEM_CONFIGURE,
    PERM_USER_VIEW,
    get_permissions_for_role,
)
from src.auth.service import AuthService
from src.audit.hash_ledger import AuditLedger
from src.persistence.database import DatabaseManager
from src.persistence.repositories import (
    RoleRepository,
    UserRepository,
    SessionRepository,
)
from src.rag.indexer import DocumentIndexer
from src.rag.retriever import DocumentRetriever
from src.rag.vector_store import ChromaVectorStore
from src.rag.embeddings import MockEmbeddingProvider
from src.schemas.document import DocumentChunkSchema
from src.security.abac.policy_engine import (
    ABACPolicyEngine,
    ResourceAttributes,
)


class TestAuthRBACABACSubsystem(unittest.TestCase):
    """Integrated test suite verifying complete authorization architecture."""

    @classmethod
    def setUpClass(cls):
        # Use temporary test SQLite DB & audit log
        test_dir = Path("data/test_run")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        cls.db_mgr = DatabaseManager(db_path=test_dir / "test_workbench.db")
        cls.user_repo = UserRepository(db=cls.db_mgr)
        cls.role_repo = RoleRepository(db=cls.db_mgr)
        cls.session_repo = SessionRepository(db=cls.db_mgr)
        cls.audit_ledger = AuditLedger(ledger_path=test_dir / "test_audit.jsonl")
        
        cls.auth_svc = AuthService(
            user_repo=cls.user_repo,
            role_repo=cls.role_repo,
            session_repo=cls.session_repo,
            audit_ledger=cls.audit_ledger,
        )
        cls.abac_engine = ABACPolicyEngine()

    def test_01_role_permission_mappings(self):
        """Test exact 6 application roles and permission matrix."""
        # 1. PLANT_OPERATOR
        op_perms = get_permissions_for_role(UserRole.PLANT_OPERATOR)
        self.assertIn(PERM_CHAT_READ, op_perms)
        self.assertNotIn(PERM_CODE_GENERATE, op_perms)
        self.assertNotIn(PERM_USER_VIEW, op_perms)

        # 2. ENGINEER
        eng_perms = get_permissions_for_role(UserRole.ENGINEER)
        self.assertIn(PERM_CODE_GENERATE, eng_perms)
        self.assertIn(PERM_APPROVAL_REQUEST, eng_perms)
        self.assertNotIn(PERM_APPROVAL_APPROVE, eng_perms)

        # 3. SHIFT_SUPERVISOR
        sup_perms = get_permissions_for_role(UserRole.SHIFT_SUPERVISOR)
        self.assertIn(PERM_APPROVAL_APPROVE, sup_perms)
        self.assertNotIn(PERM_SYSTEM_CONFIGURE, sup_perms)

        # 4. PLANT_MANAGER
        mgr_perms = get_permissions_for_role(UserRole.PLANT_MANAGER)
        self.assertIn(PERM_APPROVAL_APPROVE, mgr_perms)

        # 5. AI_IT_ADMIN
        admin_perms = get_permissions_for_role(UserRole.AI_IT_ADMIN)
        self.assertIn(PERM_USER_VIEW, admin_perms)
        self.assertIn(PERM_SYSTEM_CONFIGURE, admin_perms)

        # 6. AUDITOR_DOC_CONTROLLER
        aud_perms = get_permissions_for_role(UserRole.AUDITOR_DOC_CONTROLLER)
        self.assertIn(PERM_DOC_VIEW, aud_perms)
        self.assertNotIn(PERM_SYSTEM_CONFIGURE, aud_perms)

    def test_02_registration_and_admin_approval_workflow(self):
        """Test registration creates PENDING user, duplicate email is rejected, admin approves to ACTIVE."""
        # Cleanup pre-existing user if present from prior runs
        existing = self.user_repo.get_user_by_email("ramesh@mrpl.local")
        if existing:
            with self.db_mgr.transaction() as conn:
                conn.execute("DELETE FROM users WHERE lower(email) = 'ramesh@mrpl.local';")

        # 1. Register pending user
        pending_user = self.auth_svc.register_user(
            full_name="Ramesh Operator",
            email="ramesh@mrpl.local",
            password="password123",
            department="Operations",
            requested_role="PLANT_OPERATOR",
        )
        self.assertEqual(pending_user.status, "PENDING")

        # 2. Duplicate registration attempt fails
        with self.assertRaises(ValueError):
            self.auth_svc.register_user(
                full_name="Ramesh Duplicate",
                email="ramesh@mrpl.local",
                password="password123",
            )

        # 3. Pending user login attempt fails
        login_res = self.auth_svc.authenticate_user("ramesh@mrpl.local", "password123")
        self.assertIsNone(login_res)

        # 4. Admin approves user account
        admin_auth = self.auth_svc.authenticate_user("admin@mrpl.local", "admin123")
        self.assertIsNotNone(admin_auth)
        admin_user, _ = admin_auth

        updated = self.auth_svc.update_user_status_or_role(
            admin_user=admin_user,
            target_user_id=pending_user.id,
            new_role="PLANT_OPERATOR",
            new_workspace_id="Operations",
            new_clearance_level=2,
            new_status="ACTIVE",
        )
        self.assertEqual(updated.status, "ACTIVE")
        self.assertEqual(updated.clearance_level, 2)

        # 5. Active user login succeeds
        auth_success = self.auth_svc.authenticate_user("ramesh@mrpl.local", "password123")
        self.assertIsNotNone(auth_success)
        domain_user, token = auth_success
        self.assertEqual(domain_user.email, "ramesh@mrpl.local")

    def test_03_abac_workspace_and_clearance_rules(self):
        """Test ABAC policy rules: status, workspace matching, clearance levels 1-5."""
        op_user = User(
            user_id="usr_test_op",
            full_name="Operator 1",
            email="test_op@mrpl.local",
            role=UserRole.PLANT_OPERATOR,
            department="Operations",
            workspace_id="Operations",
            clearance_level=2,
            status="ACTIVE",
            permissions=get_permissions_for_role(UserRole.PLANT_OPERATOR),
        )

        # 1. Same workspace + sufficient clearance -> ALLOW
        res_allowed = ResourceAttributes(
            resource_id="doc_ops_001",
            workspace_id="Operations",
            classification_level=2,
        )
        dec1 = self.abac_engine.evaluate(user=op_user, action=PERM_DOC_VIEW, resource=res_allowed)
        self.assertTrue(dec1.allowed)

        # 2. Same workspace + insufficient clearance -> DENY
        res_high_clearance = ResourceAttributes(
            resource_id="doc_ops_classified",
            workspace_id="Operations",
            classification_level=4,
        )
        dec2 = self.abac_engine.evaluate(user=op_user, action=PERM_DOC_VIEW, resource=res_high_clearance)
        self.assertFalse(dec2.allowed)
        self.assertEqual(dec2.decision_code, "DENY_INSUFFICIENT_CLEARANCE")

        # 3. Wrong workspace -> DENY
        res_cdu = ResourceAttributes(
            resource_id="doc_cdu_001",
            workspace_id="Engineering",
            classification_level=2,
        )
        dec3 = self.abac_engine.evaluate(user=op_user, action=PERM_DOC_VIEW, resource=res_cdu)
        self.assertFalse(dec3.allowed)
        self.assertEqual(dec3.decision_code, "DENY_WORKSPACE_MISMATCH")

    def test_04_preretrieval_rag_security_filtering(self):
        """Verify pre-retrieval vector store query filters out unauthorized chunks BEFORE retrieval."""
        test_store = ChromaVectorStore(persist_dir="data/test_run/chroma", default_collection="test_sec_rag")
        embedder = MockEmbeddingProvider()
        
        indexer = DocumentIndexer(vector_store=test_store, embedding_provider=embedder)
        retriever = DocumentRetriever(vector_store=test_store, embedding_provider=embedder, audit_ledger=self.audit_ledger)

        # Index 2 documents into RAG store with different metadata
        # Doc 1: Operations workspace, Clearance Level 1
        chunks_ops = [DocumentChunkSchema(chunk_id=1, content="CDU-1 normal operational procedure text.", start_char=0, end_char=40, word_count=5)]
        indexer.index_document(
            filename="ops_manual.txt",
            file_hash="hash_ops_111",
            chunks=chunks_ops,
            document_id="doc_ops_111",
            metadata={"workspace_id": "Operations", "classification_level": 1},
            collection_name="test_sec_rag",
        )

        # Doc 2: Engineering workspace, Clearance Level 4 (Top Secret)
        chunks_eng = [DocumentChunkSchema(chunk_id=1, content="CDU-1 confidential pressure safety margin formula.", start_char=0, end_char=50, word_count=6)]
        indexer.index_document(
            filename="eng_classified.txt",
            file_hash="hash_eng_999",
            chunks=chunks_eng,
            document_id="doc_eng_999",
            metadata={"workspace_id": "Engineering", "classification_level": 4},
            collection_name="test_sec_rag",
        )

        # Query 1: Plant Operator in Operations (Clearance 1)
        user_op = User(
            user_id="op_rag_user",
            full_name="Operator User",
            email="op_rag@mrpl.local",
            role=UserRole.PLANT_OPERATOR,
            workspace_id="Operations",
            clearance_level=1,
            status="ACTIVE",
            permissions=get_permissions_for_role(UserRole.PLANT_OPERATOR),
        )

        op_results = retriever.retrieve(query="CDU-1 pressure", user=user_op, collection_name="test_sec_rag")
        self.assertEqual(len(op_results), 1)
        self.assertEqual(op_results[0]["filename"], "ops_manual.txt")
        self.assertNotIn("eng_classified.txt", [r["filename"] for r in op_results])

        # Query 2: Engineer in Engineering (Clearance 4)
        user_eng = User(
            user_id="eng_rag_user",
            full_name="Senior Engineer",
            email="eng_rag@mrpl.local",
            role=UserRole.ENGINEER,
            workspace_id="Engineering",
            clearance_level=4,
            status="ACTIVE",
            permissions=get_permissions_for_role(UserRole.ENGINEER),
        )

        eng_results = retriever.retrieve(query="CDU-1 pressure", user=user_eng, collection_name="test_sec_rag")
        self.assertEqual(len(eng_results), 1)
        self.assertEqual(eng_results[0]["filename"], "eng_classified.txt")

    def test_05_audit_ledger_hash_chain_integrity(self):
        """Verify SHA-256 chained audit ledger integrity."""
        is_valid = self.audit_ledger.verify_integrity()
        self.assertTrue(is_valid)


if __name__ == "__main__":
    unittest.main()
