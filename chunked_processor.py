"""
PDF Chunker + Document AI Integration
Processes large PDFs by chunking and merging results
"""

import os
import logging
from typing import Dict, Any, List
from pdf_chunker import PDFChunker
from services.pdf_extractor import PDFExtractor
from services.mineru_extractor import MinerUExtractor
from utils.config import Config

logger = logging.getLogger(__name__)


class ChunkedPDFProcessor:
    """Processes large PDFs using chunking + Document AI"""

    def __init__(self, chunk_size: int = None):
        """
        Initialize chunked PDF processor

        Args:
            chunk_size: Number of pages per chunk (defaults to MAX_PAGES_PER_REQUEST from config)
        """
        # Get chunk size from environment or use default
        if chunk_size is None:
            chunk_size = Config.MAX_PAGES_PER_REQUEST

        self.chunker = PDFChunker(chunk_size=chunk_size)
        self.pdf_extractor = PDFExtractor()
        self.mineru_extractor = MinerUExtractor()
        logger.info(f"ChunkedPDFProcessor initialized with chunk_size={chunk_size}")

    def _adapt_mineru_response(self, mineru_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt MinerU response format to match Google Document AI format

        Args:
            mineru_result: Result from MinerUExtractor.extract_pdf()

        Returns:
            Adapted result in Google Document AI format
        """
        if not mineru_result.get("success", False):
            raise RuntimeError(
                f"MinerU extraction failed: {mineru_result.get('error', 'Unknown error')}"
            )

        data = mineru_result.get("data", {})

        # Adapt MinerU format to Google Document AI format
        adapted_result = {
            "pages": data.get("pages", []),
            "tables": data.get("tables", []),
            "full_text": data.get("full_text", ""),
            "markdown": data.get("markdown", ""),
            "metadata": {
                "total_pages": data.get("metadata", {}).get("total_pages", 0),
                "total_tables": len(data.get("tables", [])),
                "extraction_method": "mineru_chunked",
                "confidence": 0.95,  # High confidence for MinerU
                "file_size_mb": data.get("metadata", {}).get("file_size_mb", 0),
            },
            "raw_text": data.get("raw_text", ""),
            "structured_data": data.get("structured_data", {}),
        }

        return adapted_result

    def process_large_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a large PDF by chunking and merging results

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Complete document results
        """
        try:
            logger.info(f"Starting chunked processing for: {pdf_path}")

            # Step 1: Chunk the PDF
            chunks = self.chunker.chunk_pdf(pdf_path)
            logger.info(f"PDF split into {len(chunks)} chunks")

            # Step 2: Process each chunk with Document AI
            chunk_results = []

            for chunk in chunks:
                logger.info(
                    f"Processing chunk {chunk['chunk_id']}: pages {chunk['start_page']}-{chunk['end_page']}"
                )

                try:
                    # Process chunk with MinerU (instead of Google Document AI)
                    chunk_filename = (
                        f"chunk_{chunk['chunk_id']}_{os.path.basename(pdf_path)}"
                    )
                    mineru_result = self.mineru_extractor.extract_pdf(
                        chunk["file_path"], chunk_filename
                    )

                    # Adapt MinerU response to match expected format
                    chunk_result = self._adapt_mineru_response(mineru_result)

                    # Add chunk metadata
                    chunk_results.append(
                        {
                            "chunk_id": chunk["chunk_id"],
                            "success": True,
                            "data": chunk_result,
                            "chunk_info": chunk,
                        }
                    )

                    logger.info(f"Chunk {chunk['chunk_id']} processed successfully")

                except Exception as e:
                    logger.error(
                        f"Error processing chunk {chunk['chunk_id']}: {str(e)}"
                    )
                    chunk_results.append(
                        {
                            "chunk_id": chunk["chunk_id"],
                            "success": False,
                            "error": str(e),
                            "chunk_info": chunk,
                        }
                    )

            # Step 3: Merge results
            logger.info("Merging results from all chunks")
            merged_result = self.chunker.merge_results(chunk_results)

            # Step 4: Cleanup temporary files
            logger.info("Cleaning up temporary chunk files")
            self.chunker.cleanup_chunks(chunks)

            # Add processing metadata
            merged_result["metadata"]["processing_method"] = "mineru_chunked"
            merged_result["metadata"]["original_file"] = pdf_path
            merged_result["metadata"]["chunks_created"] = len(chunks)

            logger.info(f"Chunked processing completed successfully")
            return merged_result

        except Exception as e:
            logger.error(f"Error in chunked processing: {str(e)}")
            raise

    def process_small_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a small PDF directly (no chunking needed)

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Document results
        """
        try:
            logger.info(f"Processing small PDF directly with MinerU: {pdf_path}")
            filename = os.path.basename(pdf_path)
            mineru_result = self.mineru_extractor.extract_pdf(pdf_path, filename)

            # Adapt MinerU response to match expected format
            result = self._adapt_mineru_response(mineru_result)

            # Add processing metadata
            result["metadata"]["processing_method"] = "mineru_direct"
            result["metadata"]["original_file"] = pdf_path

            return result

        except Exception as e:
            logger.error(f"Error processing small PDF: {str(e)}")
            raise

    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Smart PDF processing - chunks if needed, processes directly if small

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Complete document results
        """
        try:
            logger.info(f"Starting smart processing for: {pdf_path}")

            # Check if PDF needs chunking
            chunks = self.chunker.chunk_pdf(pdf_path)

            if len(chunks) == 1 and not chunks[0]["is_chunked"]:
                # Small PDF - process directly
                logger.info("PDF is small, processing directly")
                return self.process_small_pdf(pdf_path)
            else:
                # Large PDF - process with chunking
                logger.info("PDF is large, processing with chunking")
                return self.process_large_pdf(pdf_path)

        except Exception as e:
            logger.error(f"Error in smart processing: {str(e)}")
            raise


# Example usage
if __name__ == "__main__":
    # Test with your PDF
    processor = ChunkedPDFProcessor()  # Uses MAX_PAGES_PER_REQUEST from config

    pdf_path = "./38190.pdf"  # Your large PDF

    if os.path.exists(pdf_path):
        try:
            print(f"Processing {pdf_path}...")
            result = processor.process_pdf(pdf_path)

            print(f"✅ Processing completed!")
            print(f"📄 Total pages: {result['metadata']['total_pages']}")
            print(f"📊 Total tables: {len(result['tables'])}")
            print(f"🔧 Processing method: {result['metadata']['processing_method']}")

            if result["metadata"]["processing_method"] == "chunked_document_ai":
                print(f"📦 Chunks created: {result['metadata']['chunks_created']}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
    else:
        print(f"PDF file not found: {pdf_path}")
