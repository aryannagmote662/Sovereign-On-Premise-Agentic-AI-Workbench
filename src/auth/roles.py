"""
Role & Permission Definitions for MRPL AI Workbench.
Defines permissions and exact mappings for the 6 Application Roles.
"""

from typing import Dict, List, Set
from src.auth.models import UserRole

# ---------------------------------------------------------
# Centralized Permission Constants
# ---------------------------------------------------------

# Chat
PERM_CHAT_READ = "chat.read"
PERM_CHAT_CREATE = "chat.create"
PERM_CHAT_ATTACH = "chat.attach"

# Documents
PERM_DOC_VIEW = "document.view"
PERM_DOC_UPLOAD = "document.upload"
PERM_DOC_DOWNLOAD = "document.download"
PERM_DOC_UPDATE = "document.update"
PERM_DOC_DELETE = "document.delete"
PERM_DOC_CLASSIFY = "document.classify"
PERM_DOC_INDEX = "document.index"

# RAG Retrieval
PERM_RAG_SEARCH = "rag.search"
PERM_RAG_RETRIEVE = "rag.retrieve"
PERM_RAG_INSPECT_SOURCE = "rag.inspect_source"

# OCR & Vision
PERM_OCR_EXECUTE = "ocr.execute"
PERM_VISION_ANALYZE = "vision.analyze"
PERM_VISION_PID_ANALYZE = "vision.pid_analyze"

# Telemetry & Analytics
PERM_TELEMETRY_VIEW = "telemetry.view"
PERM_TELEMETRY_QUERY = "telemetry.query"
PERM_TELEMETRY_EXPORT = "telemetry.export"
PERM_ANALYTICS_SQL = "analytics.execute_sql"

# Code Execution
PERM_CODE_GENERATE = "code.generate"
PERM_CODE_VALIDATE = "code.validate"
PERM_CODE_EXECUTE = "code.execute"

# Artifacts
PERM_ARTIFACT_CREATE = "artifact.create"
PERM_ARTIFACT_VIEW = "artifact.view"
PERM_ARTIFACT_DOWNLOAD = "artifact.download"

# Approvals
PERM_APPROVAL_VIEW = "approval.view"
PERM_APPROVAL_REQUEST = "approval.request"
PERM_APPROVAL_APPROVE = "approval.approve"
PERM_APPROVAL_REJECT = "approval.reject"

# User Administration
PERM_USER_VIEW = "user.view"
PERM_USER_CREATE = "user.create"
PERM_USER_UPDATE = "user.update"
PERM_USER_DISABLE = "user.disable"
PERM_USER_APPROVE = "user.approve"

# Role Administration
PERM_ROLE_VIEW = "role.view"
PERM_ROLE_ASSIGN = "role.assign"

# Audit & Integrity
PERM_AUDIT_VIEW = "audit.view"
PERM_AUDIT_SEARCH = "audit.search"
PERM_AUDIT_EXPORT = "audit.export"
PERM_AUDIT_VERIFY = "audit.verify"
PERM_ATTESTATION_VERIFY = "attestation.verify"

# System Configuration
PERM_SYSTEM_CONFIGURE = "system.configure"
PERM_MODEL_CONFIGURE = "model.configure"


# Backward-compatibility alias constants
PERMISSION_CHAT = PERM_CHAT_READ
PERMISSION_DOCUMENT_UPLOAD = PERM_DOC_UPLOAD
PERMISSION_RAG_QUERY = PERM_RAG_SEARCH
PERMISSION_VISION = PERM_VISION_ANALYZE
PERMISSION_AGENT_RUN = PERM_APPROVAL_REQUEST
PERMISSION_AGENT_APPROVE = PERM_APPROVAL_APPROVE
PERMISSION_AGENT_REJECT = PERM_APPROVAL_REJECT
PERMISSION_AGENT_CANCEL = PERM_APPROVAL_REJECT
PERMISSION_OPERATOR_READ = PERM_TELEMETRY_VIEW
PERMISSION_AUDIT_READ = PERM_AUDIT_VIEW
PERMISSION_SYSTEM_ADMIN = PERM_SYSTEM_CONFIGURE


# ---------------------------------------------------------
# Exact 6-Role Permission Mappings
# ---------------------------------------------------------

ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    UserRole.PLANT_OPERATOR: {
        PERM_CHAT_READ,
        PERM_CHAT_CREATE,
        PERM_CHAT_ATTACH,
        PERM_DOC_VIEW,
        PERM_RAG_SEARCH,
        PERM_RAG_RETRIEVE,
        PERM_RAG_INSPECT_SOURCE,
        PERM_OCR_EXECUTE,
        PERM_VISION_ANALYZE,
        PERM_VISION_PID_ANALYZE,
        PERM_TELEMETRY_VIEW,
        PERM_ARTIFACT_CREATE,
        PERM_ARTIFACT_VIEW,
        PERM_ARTIFACT_DOWNLOAD,
    },
    UserRole.ENGINEER: {
        PERM_CHAT_READ,
        PERM_CHAT_CREATE,
        PERM_CHAT_ATTACH,
        PERM_DOC_VIEW,
        PERM_DOC_UPLOAD,
        PERM_RAG_SEARCH,
        PERM_RAG_RETRIEVE,
        PERM_RAG_INSPECT_SOURCE,
        PERM_OCR_EXECUTE,
        PERM_VISION_ANALYZE,
        PERM_VISION_PID_ANALYZE,
        PERM_TELEMETRY_VIEW,
        PERM_TELEMETRY_QUERY,
        PERM_ANALYTICS_SQL,
        PERM_ARTIFACT_CREATE,
        PERM_ARTIFACT_VIEW,
        PERM_ARTIFACT_DOWNLOAD,
        PERM_APPROVAL_REQUEST,
        PERM_CODE_GENERATE,
        PERM_CODE_VALIDATE,
    },
    UserRole.SHIFT_SUPERVISOR: {
        PERM_CHAT_READ,
        PERM_CHAT_CREATE,
        PERM_CHAT_ATTACH,
        PERM_DOC_VIEW,
        PERM_RAG_SEARCH,
        PERM_RAG_RETRIEVE,
        PERM_RAG_INSPECT_SOURCE,
        PERM_OCR_EXECUTE,
        PERM_VISION_ANALYZE,
        PERM_VISION_PID_ANALYZE,
        PERM_TELEMETRY_VIEW,
        PERM_TELEMETRY_QUERY,
        PERM_ANALYTICS_SQL,
        PERM_ARTIFACT_CREATE,
        PERM_ARTIFACT_VIEW,
        PERM_ARTIFACT_DOWNLOAD,
        PERM_APPROVAL_VIEW,
        PERM_APPROVAL_APPROVE,
        PERM_APPROVAL_REJECT,
    },
    UserRole.PLANT_MANAGER: {
        PERM_CHAT_READ,
        PERM_CHAT_CREATE,
        PERM_CHAT_ATTACH,
        PERM_DOC_VIEW,
        PERM_RAG_SEARCH,
        PERM_RAG_RETRIEVE,
        PERM_RAG_INSPECT_SOURCE,
        PERM_TELEMETRY_VIEW,
        PERM_TELEMETRY_QUERY,
        PERM_ANALYTICS_SQL,
        PERM_ARTIFACT_CREATE,
        PERM_ARTIFACT_VIEW,
        PERM_ARTIFACT_DOWNLOAD,
        PERM_APPROVAL_VIEW,
        PERM_APPROVAL_APPROVE,
        PERM_APPROVAL_REJECT,
        PERM_AUDIT_VIEW,
    },
    UserRole.AI_IT_ADMIN: {
        PERM_USER_VIEW,
        PERM_USER_CREATE,
        PERM_USER_UPDATE,
        PERM_USER_DISABLE,
        PERM_USER_APPROVE,
        PERM_ROLE_VIEW,
        PERM_ROLE_ASSIGN,
        PERM_SYSTEM_CONFIGURE,
        PERM_MODEL_CONFIGURE,
        PERM_AUDIT_VIEW,
        PERM_AUDIT_SEARCH,
        PERM_AUDIT_VERIFY,
        PERM_CHAT_READ,
        PERM_CHAT_CREATE,
        PERM_DOC_VIEW,
        PERM_APPROVAL_VIEW,
        PERM_APPROVAL_APPROVE,
        PERM_APPROVAL_REJECT,
    },
    UserRole.AUDITOR_DOC_CONTROLLER: {
        PERM_DOC_VIEW,
        PERM_DOC_UPLOAD,
        PERM_DOC_DOWNLOAD,
        PERM_DOC_UPDATE,
        PERM_DOC_CLASSIFY,
        PERM_DOC_INDEX,
        PERM_AUDIT_VIEW,
        PERM_AUDIT_SEARCH,
        PERM_AUDIT_EXPORT,
        PERM_AUDIT_VERIFY,
        PERM_ATTESTATION_VERIFY,
    },
}


def get_permissions_for_role(role: UserRole) -> List[str]:
    """Retrieve canonical list of permissions for specified role."""
    return sorted(list(ROLE_PERMISSIONS.get(role, set())))
