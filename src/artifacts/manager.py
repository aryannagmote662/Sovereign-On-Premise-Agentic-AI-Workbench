"""
Artifact Manager Subsystem for MRPL AI Workbench.
Orchestrates generation, persistence, retrieval, and metadata tracking for all deliverables.
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.artifacts.code_artifact import generate_code_artifact
from src.artifacts.docx_generator import generate_docx_approval_note
from src.artifacts.models import ArtifactMetadata, ArtifactType
from src.artifacts.pdf_generator import generate_pdf_artifact
from src.artifacts.pptx_generator import generate_pptx_artifact
from src.artifacts.xlsx_generator import generate_xlsx_artifact



class ArtifactManager:
    """
    Central Artifact Manager for MRPL AI Workbench.
    Persists deliverables under `data/artifacts/` or `examples/output/`.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("examples/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._artifact_registry: Dict[str, ArtifactMetadata] = {}

    def create_docx_approval_note(
        self,
        task_id: str,
        filename: Optional[str] = None,
        title: str = "MRPL AI WORKBENCH — OFFICIAL APPROVAL NOTE",
        reference_number: str = "MRPL-AI-DEMO-001",
        subject: str = "Inspection Findings & Recommended Maintenance Actions",
        background: str = "Automated inspection analysis conducted via MRPL Sovereign On-Premise AI Workbench.",
        findings: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[List[str]] = None,
        approver: str = "Chief Technical Inspector",
        approval_status: str = "APPROVED",
    ) -> ArtifactMetadata:
        """
        Creates and registers a .docx Approval Note artifact.
        """
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"
        filename = filename or f"approval_note_{task_id}.docx"
        target_path = self.output_dir / filename

        generate_docx_approval_note(
            output_path=target_path,
            task_id=task_id,
            title=title,
            reference_number=reference_number,
            subject=subject,
            background=background,
            findings=findings,
            sources=sources,
            recommendations=recommendations,
            approver=approver,
            approval_status=approval_status,
        )

        size_bytes = target_path.stat().st_size if target_path.exists() else 0

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            filename=filename,
            artifact_type=ArtifactType.DOCX,
            filepath=str(target_path.resolve()),
            size_bytes=size_bytes,
            metadata={
                "title": title,
                "reference_number": reference_number,
                "subject": subject,
                "approver": approver,
                "approval_status": approval_status,
            },
        )

        self._artifact_registry[artifact_id] = metadata
        return metadata

    def create_xlsx_deliverable(
        self,
        task_id: str,
        filename: Optional[str] = None,
        title: str = "MRPL AI WORKBENCH — TABULAR DELIVERABLE",
        headers: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
    ) -> ArtifactMetadata:
        """
        Creates and registers a .xlsx deliverable artifact.
        """
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"
        filename = filename or f"deliverable_{task_id}.xlsx"
        target_path = self.output_dir / filename

        generate_xlsx_artifact(
            output_path=target_path,
            task_id=task_id,
            title=title,
            headers=headers,
            rows=rows,
        )

        size_bytes = target_path.stat().st_size if target_path.exists() else 0

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            filename=filename,
            artifact_type=ArtifactType.XLSX,
            filepath=str(target_path.resolve()),
            size_bytes=size_bytes,
            metadata={"title": title},
        )

        self._artifact_registry[artifact_id] = metadata
        return metadata

    def create_pptx_summary(
        self,
        task_id: str,
        filename: Optional[str] = None,
        title: str = "MRPL AI WORKBENCH — EXECUTIVE SUMMARY",
        slides_content: Optional[List[Dict[str, Any]]] = None,
    ) -> ArtifactMetadata:
        """
        Creates and registers a .pptx deliverable artifact.
        """
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"
        filename = filename or f"summary_{task_id}.pptx"
        target_path = self.output_dir / filename

        generate_pptx_artifact(
            output_path=target_path,
            task_id=task_id,
            title=title,
            slides_content=slides_content,
        )

        size_bytes = target_path.stat().st_size if target_path.exists() else 0

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            filename=filename,
            artifact_type=ArtifactType.PPTX,
            filepath=str(target_path.resolve()),
            size_bytes=size_bytes,
            metadata={"title": title},
        )

        self._artifact_registry[artifact_id] = metadata
        return metadata

    def create_code_deliverable(
        self,
        task_id: str,
        code_content: str,
        filename: Optional[str] = None,
        language: str = "python",
    ) -> ArtifactMetadata:
        """
        Creates and registers a verified code artifact.
        """
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"
        ext = "py" if language.lower() == "python" else "txt"
        filename = filename or f"verified_code_{task_id}.{ext}"
        target_path = self.output_dir / filename

        generate_code_artifact(
            output_path=target_path,
            task_id=task_id,
            code_content=code_content,
            language=language,
        )

        size_bytes = target_path.stat().st_size if target_path.exists() else 0

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            filename=filename,
            artifact_type=ArtifactType.CODE,
            filepath=str(target_path.resolve()),
            size_bytes=size_bytes,
            metadata={"language": language},
        )

        self._artifact_registry[artifact_id] = metadata
        return metadata

    def create_pdf_document(
        self,
        task_id: str,
        filename: Optional[str] = None,
        title: str = "MRPL AI WORKBENCH — OFFICIAL AUDIT & REPORT",
        reference_number: str = "MRPL-AI-REPORT-001",
        subject: str = "Inspection Findings & Operational Compliance Report",
        background: str = "Automated analysis conducted via MRPL Sovereign On-Premise AI Workbench.",
        findings: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[List[str]] = None,
        approver: str = "Chief Technical Inspector",
        approval_status: str = "APPROVED",
    ) -> ArtifactMetadata:
        """
        Creates and registers a .pdf deliverable artifact.
        """
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"
        filename = filename or f"report_{task_id}.pdf"
        target_path = self.output_dir / filename

        generate_pdf_artifact(
            output_path=target_path,
            task_id=task_id,
            title=title,
            reference_number=reference_number,
            subject=subject,
            background=background,
            findings=findings,
            sources=sources,
            recommendations=recommendations,
            approver=approver,
            approval_status=approval_status,
        )

        size_bytes = target_path.stat().st_size if target_path.exists() else 0

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            filename=filename,
            artifact_type=ArtifactType.PDF,
            filepath=str(target_path.resolve()),
            size_bytes=size_bytes,
            metadata={"title": title, "subject": subject},
        )

        self._artifact_registry[artifact_id] = metadata
        return metadata

    def create_csv_deliverable(
        self,
        task_id: str,
        filename: Optional[str] = None,
        headers: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
    ) -> ArtifactMetadata:
        """
        Creates and registers a .csv deliverable artifact.
        """
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"
        filename = filename or f"analysis_{task_id}.csv"
        target_path = self.output_dir / filename
        headers = headers or ["Item ID", "Parameter", "Observed Value", "Status"]
        rows = rows or [
            ["1", "Operating Pressure", "12.4 bar", "PASS"],
            ["2", "Wall Thickness", "14.2 mm", "PASS"],
        ]

        lines = [",".join(headers)]
        for row in rows:
            lines.append(",".join(str(cell) for cell in row))

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("\n".join(lines), encoding="utf-8")

        size_bytes = target_path.stat().st_size if target_path.exists() else 0

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            filename=filename,
            artifact_type=ArtifactType.TXT,
            filepath=str(target_path.resolve()),
            size_bytes=size_bytes,
            metadata={"title": filename},
        )

        self._artifact_registry[artifact_id] = metadata
        return metadata

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        return self._artifact_registry.get(artifact_id)

    def list_artifacts_for_task(self, task_id: str) -> List[ArtifactMetadata]:
        return [meta for meta in self._artifact_registry.values() if meta.task_id == task_id]


# Global Default ArtifactManager Singleton
artifact_manager = ArtifactManager()

