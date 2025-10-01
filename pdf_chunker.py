"""
Simple PDF Chunker for Google Document AI
Handles splitting large PDFs into processable chunks
"""

import os
import logging
from typing import List, Dict, Any
import fitz  # PyMuPDF
from utils.config import Config

logger = logging.getLogger(__name__)


class PDFChunker:
    """Simple PDF chunker for Document AI processing"""

    def __init__(self, chunk_size: int = None):
        """
        Initialize PDF chunker

        Args:
            chunk_size: Number of pages per chunk (defaults to MAX_PAGES_PER_REQUEST from config)
        """
        # Get chunk size from parameter or config
        if chunk_size is None:
            chunk_size = Config.MAX_PAGES_PER_REQUEST

        self.chunk_size = chunk_size
        logger.info(f"PDFChunker initialized with chunk_size={chunk_size}")

    def chunk_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Split PDF into chunks for Document AI processing

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of chunk info dictionaries
        """
        try:
            logger.info(f"Starting PDF chunking for: {pdf_path}")

            # Open PDF
            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            logger.info(f"PDF has {total_pages} pages")

            if total_pages <= self.chunk_size:
                logger.info("PDF is small enough, no chunking needed")
                return [
                    {
                        "chunk_id": 0,
                        "start_page": 1,
                        "end_page": total_pages,
                        "page_count": total_pages,
                        "file_path": pdf_path,
                        "is_chunked": False,
                    }
                ]

            # Create chunks
            chunks = []
            chunk_id = 0

            for start_page in range(0, total_pages, self.chunk_size):
                end_page = min(start_page + self.chunk_size - 1, total_pages - 1)
                page_count = end_page - start_page + 1

                # Create chunk PDF
                chunk_doc = fitz.open()
                chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)

                # Save chunk file
                chunk_filename = f"chunk_{chunk_id}_{os.path.basename(pdf_path)}"
                chunk_path = os.path.join(os.path.dirname(pdf_path), chunk_filename)
                chunk_doc.save(chunk_path)
                chunk_doc.close()

                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "start_page": start_page + 1,  # 1-indexed
                        "end_page": end_page + 1,  # 1-indexed
                        "page_count": page_count,
                        "file_path": chunk_path,
                        "is_chunked": True,
                    }
                )

                logger.info(
                    f"Created chunk {chunk_id}: pages {start_page + 1}-{end_page + 1} ({page_count} pages)"
                )
                chunk_id += 1

            doc.close()
            logger.info(f"PDF chunking completed: {len(chunks)} chunks created")
            return chunks

        except Exception as e:
            logger.error(f"Error chunking PDF: {str(e)}")
            raise

    def merge_results(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge results from multiple chunks back into a single document

        Args:
            chunk_results: List of results from each chunk

        Returns:
            Merged document results
        """
        try:
            logger.info(f"Merging results from {len(chunk_results)} chunks")

            # Sort chunks by chunk_id to maintain order
            chunk_results.sort(key=lambda x: x.get("chunk_id", 0))

            merged_pages = []
            merged_tables = []
            merged_text = []
            total_pages = 0

            for chunk_result in chunk_results:
                if not chunk_result.get("success", False):
                    logger.warning(
                        f"Chunk {chunk_result.get('chunk_id', 'unknown')} failed, skipping"
                    )
                    continue

                data = chunk_result.get("data", {})

                # Merge pages
                pages = data.get("pages", [])
                for page in pages:
                    # Adjust page numbers to be sequential
                    page["page_number"] = total_pages + page["page_number"]
                    merged_pages.append(page)

                # Merge tables
                tables = data.get("tables", [])
                for table in tables:
                    # Adjust page numbers
                    table["page_number"] = total_pages + table["page_number"]
                    merged_tables.append(table)

                # Merge text
                chunk_text = data.get("full_text", "")
                if chunk_text:
                    merged_text.append(chunk_text)

                total_pages += len(pages)

            # Create merged result
            merged_result = {
                "pages": merged_pages,
                "tables": merged_tables,
                "full_text": "\n\n".join(merged_text),
                "metadata": {
                    "total_pages": total_pages,
                    "chunks_processed": len(chunk_results),
                    "extraction_method": "chunked_document_ai",
                },
            }

            logger.info(
                f"Results merged successfully: {total_pages} pages, {len(merged_tables)} tables"
            )
            return merged_result

        except Exception as e:
            logger.error(f"Error merging results: {str(e)}")
            raise

    def cleanup_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Clean up temporary chunk files

        Args:
            chunks: List of chunk info dictionaries
        """
        try:
            logger.info("Cleaning up temporary chunk files")

            for chunk in chunks:
                if chunk.get("is_chunked", False):
                    chunk_path = chunk.get("file_path")
                    if chunk_path and os.path.exists(chunk_path):
                        os.remove(chunk_path)
                        logger.info(f"Removed chunk file: {chunk_path}")

            logger.info("Cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
