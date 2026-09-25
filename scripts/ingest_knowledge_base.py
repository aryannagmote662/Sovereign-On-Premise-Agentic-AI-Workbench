"""
Bulk Ingestion Utility Script for MRPL Sovereign AI Workbench.
Scans and indexes documents from a target directory into local persistent ChromaDB RAG store.
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.workbench_service import WorkbenchService

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx"}


def ingest_knowledge_base(
    target_dir: Path,
    workspace_id: str = "Operations",
    clearance_level: int = 1,
) -> None:
    """
    Ingest all documents from target_dir into the RAG vector store.
    """
    if not target_dir.exists():
        print(f"❌ Error: Target directory '{target_dir}' does not exist.")
        sys.exit(1)

    service = WorkbenchService()
    files_to_process = [
        f for f in target_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files_to_process:
        print(f"⚠️ No supported documents ({', '.join(SUPPORTED_EXTENSIONS)}) found in '{target_dir}'.")
        return

    print(f"\n🚀 Starting Knowledge Base Ingestion for {len(files_to_process)} document(s)...")
    print(f"   Target Directory: {target_dir}")
    print(f"   Workspace ID:     {workspace_id}")
    print(f"   Clearance Level:  {clearance_level}\n" + "-" * 60)

    success_count = 0
    total_chunks = 0

    for idx, filepath in enumerate(files_to_process, 1):
        filename = filepath.name
        try:
            print(f"[{idx}/{len(files_to_process)}] Processing: {filename}...", end=" ", flush=True)
            content_bytes = filepath.read_bytes()

            res = service.process_document(
                filename=filename,
                content_bytes=content_bytes,
                workspace_id=workspace_id,
                classification_level=clearance_level,
            )

            success_count += 1
            total_chunks += res.indexed_chunks_count
            print(f"✅ Success! Indexed {res.indexed_chunks_count} chunks ({res.extraction_mode}).")

        except Exception as exc:
            print(f"❌ Failed: {exc}")

    print("-" * 60)
    print(f"🎉 Ingestion Complete!")
    print(f"   Successfully Indexed: {success_count}/{len(files_to_process)} documents")
    print(f"   Total Chunks Added:   {total_chunks}")
    print(f"   Vector Database Path: data/chroma/\n")


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into local MRPL AI Workbench knowledge base.")
    parser.add_argument(
        "--dir",
        type=str,
        default=str(PROJECT_ROOT / "data" / "documents"),
        help="Directory containing documents to ingest (default: data/documents/)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="Operations",
        help="Workspace ID metadata tag (default: Operations)",
    )
    parser.add_argument(
        "--clearance",
        type=int,
        default=1,
        help="Clearance classification level 1-5 (default: 1)",
    )

    args = parser.parse_args()
    ingest_knowledge_base(
        target_dir=Path(args.dir),
        workspace_id=args.workspace,
        clearance_level=args.clearance,
    )


if __name__ == "__main__":
    main()
