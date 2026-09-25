"""
OCR Pipeline Module for MRPL AI Workbench.
Orchestrates document validation, PDF page content detection, machine-readable text extraction,
OCR/Vision processing, text normalization, and Phase 5-compatible chunk generation.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.document_processing.chunker import DocumentChunker
from src.ocr.image_processor import ImageProcessor
from src.ocr.pdf_detector import PDFDetector, PDFPageType
from src.ocr.text_ocr import TextOCREngine
from src.schemas.document import DocumentChunkSchema
from src.schemas.ocr import OCRPageResultSchema, OCRProcessResponse

logger = logging.getLogger("MRPL.OCR.Pipeline")


class OCRPipeline:
    """
    Production-ready OCR Pipeline managing incremental page processing,
    intelligent page type detection, and Phase 5 / Phase 6 RAG integration.
    """

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

    def __init__(
        self,
        pdf_detector: Optional[PDFDetector] = None,
        image_processor: Optional[ImageProcessor] = None,
        text_ocr: Optional[TextOCREngine] = None,
        chunker: Optional[DocumentChunker] = None,
    ) -> None:
        self.pdf_detector = pdf_detector or PDFDetector()
        self.image_processor = image_processor or ImageProcessor()
        self.text_ocr = text_ocr or TextOCREngine(image_processor=self.image_processor)
        self.chunker = chunker or DocumentChunker()

    def process_document(
        self,
        filename: str,
        content_bytes: bytes,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        document_id: Optional[str] = None,
    ) -> OCRProcessResponse:
        """
        Execute OCR pipeline processing for scanned PDFs, images, or mixed documents.

        Args:
            filename: Original file name.
            content_bytes: Raw document or image byte string payload.
            chunk_size: Optional custom chunk character limit.
            chunk_overlap: Optional custom chunk character overlap.
            document_id: Optional custom document ID string.

        Returns:
            OCRProcessResponse container containing per-page results and Phase 5 chunks.
        """
        start_time = time.perf_counter()
        if not content_bytes:
            raise ValueError(f"Content payload for '{filename}' is empty (0 bytes).")

        ext = Path(filename).suffix.lower()
        file_hash = hashlib.sha256(content_bytes).hexdigest()
        doc_id = document_id or f"doc_ocr_{file_hash[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        page_results: List[OCRPageResultSchema] = []
        full_text_parts: List[str] = []
        ocr_pages_count = 0
        text_pages_count = 0

        # 1. PDF Document Processing Path
        if ext == ".pdf":
            detections = self.pdf_detector.detect_pdf_pages(content_bytes)

            for det in detections:
                page_num = det.page_number
                if not det.requires_ocr:
                    # Machine-readable text path (skip OCR)
                    text_pages_count += 1
                    cleaned_text = det.extracted_text.strip()
                    page_results.append(
                        OCRPageResultSchema(
                            page_number=page_num,
                            page_type=det.page_type.value,
                            ocr_applied=False,
                            extracted_text=cleaned_text,
                            word_count=len(cleaned_text.split()) if cleaned_text else 0,
                            char_count=len(cleaned_text),
                            extraction_method="text_parser",
                            metadata={"char_count": len(cleaned_text)},
                        )
                    )
                    if cleaned_text:
                        full_text_parts.append(f"--- Page {page_num} ---\n{cleaned_text}")
                else:
                    # Scanned / Image page path (apply OCR)
                    ocr_pages_count += 1
                    ocr_res = self.text_ocr.process_page(
                        page_bytes=content_bytes,
                        page_number=page_num,
                    )
                    cleaned_text = ocr_res["text"].strip()
                    page_results.append(
                        OCRPageResultSchema(
                            page_number=page_num,
                            page_type=det.page_type.value,
                            ocr_applied=True,
                            extracted_text=cleaned_text,
                            word_count=ocr_res["word_count"],
                            char_count=ocr_res["char_count"],
                            extraction_method=ocr_res["method"],
                            metadata=ocr_res.get("metadata", {}),
                        )
                    )
                    if cleaned_text:
                        full_text_parts.append(f"--- Page {page_num} ---\n{cleaned_text}")

        # 2. Image Document Processing Path (.png, .jpg, .jpeg, etc.)
        elif ext in self.IMAGE_EXTENSIONS or ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
            ocr_pages_count += 1
            ocr_res = self.text_ocr.process_image(
                image_bytes=content_bytes,
                filename=filename,
            )
            cleaned_text = ocr_res["text"].strip()
            page_results.append(
                OCRPageResultSchema(
                    page_number=1,
                    page_type="SCANNED_IMAGE",
                    ocr_applied=True,
                    extracted_text=cleaned_text,
                    word_count=ocr_res["word_count"],
                    char_count=ocr_res["char_count"],
                    extraction_method=ocr_res["method"],
                    metadata=ocr_res.get("metadata", {}),
                )
            )
            if cleaned_text:
                full_text_parts.append(cleaned_text)

        else:
            # Fallback for plain text files
            text_pages_count += 1
            decoded_text = content_bytes.decode("utf-8", errors="replace").strip()
            page_results.append(
                OCRPageResultSchema(
                    page_number=1,
                    page_type="TEXT",
                    ocr_applied=False,
                    extracted_text=decoded_text,
                    word_count=len(decoded_text.split()) if decoded_text else 0,
                    char_count=len(decoded_text),
                    extraction_method="text_decoder",
                    metadata={},
                )
            )
            full_text_parts.append(decoded_text)

        # 3. Text Normalization & Phase 5-Compatible Chunking
        combined_text = "\n\n".join(full_text_parts).strip()

        active_chunker = (
            DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if (chunk_size or chunk_overlap)
            else self.chunker
        )
        chunks = active_chunker.chunk_text(combined_text)

        chunk_schemas = [
            DocumentChunkSchema(
                chunk_id=c.chunk_id,
                content=c.content,
                start_char=c.start_char,
                end_char=c.end_char,
                word_count=c.word_count,
            )
            for c in chunks
        ]

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            f"[OCR PIPELINE] processed filename='{filename}' | "
            f"document_id='{doc_id}' | "
            f"total_pages={len(page_results)} | "
            f"ocr_pages={ocr_pages_count} | "
            f"text_pages={text_pages_count} | "
            f"chunks_generated={len(chunk_schemas)} | "
            f"duration={duration_ms:.2f}ms"
        )

        primary_page_type = page_results[0].page_type if page_results else "SCANNED_IMAGE"
        primary_extraction_mode = page_results[0].extraction_method if page_results else "ocr"
        confidence_score = 0.96 if "paddleocr" in primary_extraction_mode else 0.90

        return OCRProcessResponse(
            status="SUCCESS",
            filename=filename,
            document_id=doc_id,
            total_pages=len(page_results),
            ocr_pages_count=ocr_pages_count,
            text_pages_count=text_pages_count,
            extracted_text=combined_text,
            total_characters=len(combined_text),
            page_type=primary_page_type,
            extraction_mode=primary_extraction_mode,
            confidence=confidence_score,
            pages=page_results,
            chunks=chunk_schemas,
            metadata={
                "file_hash": file_hash,
                "file_size_bytes": len(content_bytes),
                "file_extension": ext,
                "processed_at": now_utc,
                "duration_ms": round(duration_ms, 2),
            },
        )
