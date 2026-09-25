"""
PDF Document Generator for MRPL AI Workbench.
Generates structured PDF reports for industrial inspection and sovereign operational deliverables.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import os


def generate_pdf_artifact(
    output_path: Path,
    task_id: str,
    title: str = "MRPL AI WORKBENCH — OFFICIAL AUDIT & REPORT",
    reference_number: str = "MRPL-AI-REPORT-001",
    subject: str = "Inspection Findings & Operational Compliance Report",
    background: str = "Automated analysis conducted via MRPL Sovereign On-Premise AI Workbench.",
    findings: Optional[List[str]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    recommendations: Optional[List[str]] = None,
    approver: str = "Chief Technical Inspector",
    approval_status: str = "APPROVED",
) -> Path:
    """
    Generates a structured PDF document.
    Uses `reportlab` if available, otherwise writes a structured plain file fallback.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    findings = findings or [
        "All pressure and temperature metrics comply with ISO 9001 standards.",
        "Zero structural micro-fractures detected across inspected joints.",
        "Refinery Unit 4 telemetry remains within baseline parameters.",
    ]
    recommendations = recommendations or [
        "Continue standard operational monitoring schedule.",
        "Archive telemetry logs into Sovereign Data Store.",
    ]
    sources = sources or []

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        
        # Custom Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor('#003366'),
            alignment=1, # Center
            spaceAfter=12
        )
        
        heading_style = ParagraphStyle(
            'ReportHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#0f766e'),
            spaceBefore=10,
            spaceAfter=6
        )

        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=4
        )

        meta_style = ParagraphStyle(
            'ReportMeta',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=colors.HexColor('#4b5563')
        )

        story = []

        # Title
        story.append(Paragraph(title, title_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f766e'), spaceAfter=12))

        # Metadata Block
        meta_data = [
            [Paragraph("<b>Reference Number:</b>", meta_style), Paragraph(reference_number, body_style)],
            [Paragraph("<b>Task ID:</b>", meta_style), Paragraph(task_id, body_style)],
            [Paragraph("<b>Subject:</b>", meta_style), Paragraph(subject, body_style)],
            [Paragraph("<b>Status:</b>", meta_style), Paragraph(f"<font color='#10b981'><b>{approval_status}</b></font>", body_style)],
        ]
        meta_table = Table(meta_data, colWidths=[120, 400])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f3f4f6')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # Background
        story.append(Paragraph("1. Background & Context", heading_style))
        story.append(Paragraph(background, body_style))
        story.append(Spacer(1, 8))

        # Key Findings
        story.append(Paragraph("2. Key Findings & Observations", heading_style))
        for item in findings:
            story.append(Paragraph(f"• {item}", body_style))
        story.append(Spacer(1, 8))

        # Sources
        if sources:
            story.append(Paragraph("3. Reference Evidence", heading_style))
            for src in sources:
                s_name = src.get("source", "Document")
                s_txt = src.get("text", "")
                story.append(Paragraph(f"• <b>{s_name}</b>: {s_txt[:180]}...", body_style))
            story.append(Spacer(1, 8))

        # Recommendations
        story.append(Paragraph("4. Recommendations", heading_style))
        for rec in recommendations:
            story.append(Paragraph(f"• {rec}", body_style))
        story.append(Spacer(1, 8))

        # Governance
        story.append(Paragraph("5. Approval Governance", heading_style))
        story.append(Paragraph(f"<b>Approver:</b> {approver}", body_style))
        story.append(Paragraph(f"<b>Governance Status:</b> {approval_status}", body_style))
        story.append(Spacer(1, 16))

        # Footer Watermark
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#9ca3af'), spaceAfter=8))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#6b7280'), alignment=1)
        story.append(Paragraph("GENERATED BY MRPL AI WORKBENCH — AIR-GAPPED ENTERPRISE SOVEREIGNTY", footer_style))

        doc.build(story)
    except Exception:
        # Fallback PDF generator using simple PDF stream structure
        pdf_content = (
            f"%PDF-1.4\n"
            f"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            f"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            f"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            f"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        )
        text_stream = (
            f"BT /F1 14 Tf 50 740 Td ({title}) Tj ET\n"
            f"BT /F1 10 Tf 50 710 Td (Reference: {reference_number} | Task ID: {task_id}) Tj ET\n"
            f"BT /F1 10 Tf 50 690 Td (Subject: {subject}) Tj ET\n"
            f"BT /F1 10 Tf 50 660 Td (1. Background: {background[:70]}) Tj ET\n"
            f"BT /F1 10 Tf 50 630 Td (2. Findings: {findings[0] if findings else 'Passed'}) Tj ET\n"
            f"BT /F1 10 Tf 50 600 Td (3. Status: {approval_status} by {approver}) Tj ET\n"
            f"BT /F1 8 Tf 50 50 Td (GENERATED BY MRPL AI WORKBENCH) Tj ET\n"
        )
        stream_len = len(text_stream)
        pdf_content += f"4 0 obj << /Length {stream_len} >> stream\n{text_stream}\nendstream\nendobj\n"
        pdf_content += "xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000320 00000 n \n0000000240 00000 n \ntrailer << /Size 6 /Root 1 0 R >>\nstartxref\n450\n%%EOF\n"
        
        output_path.write_bytes(pdf_content.encode("latin-1", errors="replace"))

    return output_path
