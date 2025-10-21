"""
PDF Chunker + Document AI Integration
Processes large PDFs by chunking and merging results
"""

import os
import logging
from typing import Dict, Any
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

        # Registry for extractors and adapters
        self.extractors = {
            "mineru": self.mineru_extractor,
            "documentai": self.pdf_extractor,
        }
        self.adapters = {
            "mineru": self._adapt_mineru_response,
            "documentai": self._adapt_documentai_response,
        }

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
                "extraction_method": "mineru",
                "confidence": 0.95,  # High confidence for MinerU
                "file_size_mb": data.get("metadata", {}).get("file_size_mb", 0),
            },
            "raw_text": data.get("raw_text", ""),
            "structured_data": data.get("structured_data", {}),
        }

        return adapted_result

    def _adapt_documentai_response(
        self, documentai_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adapt Document AI response format to match expected format

        Args:
            documentai_result: Result from PDFExtractor.extract_from_pdf()

        Returns:
            Adapted result in expected format
        """
        # Document AI already returns the expected format, but let's ensure consistency
        adapted_result = {
            "pages": documentai_result.get("pages", []),
            "tables": documentai_result.get("tables", []),
            "full_text": documentai_result.get("full_text", ""),
            "markdown": documentai_result.get("markdown", ""),
            "metadata": {
                "total_pages": documentai_result.get("metadata", {}).get(
                    "total_pages", 0
                ),
                "total_tables": len(documentai_result.get("tables", [])),
                "extraction_method": "documentai",
                "confidence": documentai_result.get("metadata", {}).get(
                    "confidence", 0.8
                ),
                "file_size_mb": documentai_result.get("metadata", {}).get(
                    "file_size_mb", 0
                ),
            },
            "raw_text": documentai_result.get("raw_text", ""),
            "structured_data": documentai_result.get("structured_data", {}),
        }

        return adapted_result

    def _get_extractor(self, extraction_method: str):
        """Get the appropriate extractor based on method"""
        if extraction_method not in self.extractors:
            raise ValueError(f"Unsupported extraction method: {extraction_method}")
        return self.extractors[extraction_method]

    def _adapt_response(self, result: Dict[str, Any], method: str) -> Dict[str, Any]:
        """Adapt response format based on extraction method"""
        if method not in self.adapters:
            raise ValueError(f"Unknown method: {method}")
        return self.adapters[method](result)

    def process_large_pdf(
        self, pdf_path: str, extraction_method: str = "mineru"
    ) -> Dict[str, Any]:
        """
        Process a large PDF by chunking and merging results

        Args:
            pdf_path: Path to the PDF file
            extraction_method: Method to use for extraction ('mineru' or 'documentai')

        Returns:
            Complete document results
        """
        try:
            logger.info(
                f"Starting chunked processing for: {pdf_path} with {extraction_method}"
            )

            # Step 1: Chunk the PDF
            chunks = self.chunker.chunk_pdf(pdf_path)
            logger.info(f"PDF split into {len(chunks)} chunks")

            # Step 2: Process each chunk with selected extractor
            chunk_results = []
            extractor = self._get_extractor(extraction_method)

            for chunk in chunks:
                logger.info(
                    f"Processing chunk {chunk['chunk_id']}: pages {chunk['start_page']}-{chunk['end_page']} with {extraction_method}"
                )

                try:
                    # Process chunk with selected extractor
                    chunk_filename = (
                        f"chunk_{chunk['chunk_id']}_{os.path.basename(pdf_path)}"
                    )

                    # Extract using the selected method
                    if extraction_method == "mineru":
                        raw_result = extractor.extract_pdf(
                            chunk["file_path"], chunk_filename
                        )
                    elif extraction_method == "documentai":
                        raw_result = extractor.extract_from_pdf(chunk["file_path"])
                    else:
                        raise ValueError(
                            f"Unsupported extraction method: {extraction_method}"
                        )

                    # Adapt the response to expected format
                    chunk_result = self._adapt_response(raw_result, extraction_method)

                    # Add chunk metadata
                    chunk_results.append(
                        {
                            "chunk_id": chunk["chunk_id"],
                            "success": True,
                            "data": chunk_result,
                            "chunk_info": chunk,
                        }
                    )

                    logger.info(
                        f"Chunk {chunk['chunk_id']} processed successfully with {extraction_method}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing chunk {chunk['chunk_id']} with {extraction_method}: {str(e)}"
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
            merged_result["metadata"]["processing_method"] = (
                f"{extraction_method}_chunked"
            )
            merged_result["metadata"]["original_file"] = pdf_path
            merged_result["metadata"]["chunks_created"] = len(chunks)

            logger.info(
                f"Chunked processing completed successfully with {extraction_method}"
            )
            return merged_result

        except Exception as e:
            logger.error(
                f"Error in chunked processing with {extraction_method}: {str(e)}"
            )
            raise

    def process_small_pdf(
        self, pdf_path: str, extraction_method: str = "mineru"
    ) -> Dict[str, Any]:
        """
        Process a small PDF directly (no chunking needed)

        Args:
            pdf_path: Path to the PDF file
            extraction_method: Method to use for extraction ('mineru' or 'documentai')

        Returns:
            Document results
        """
        try:
            logger.info(
                f"Processing small PDF directly with {extraction_method}: {pdf_path}"
            )

            # Get the appropriate extractor
            extractor = self._get_extractor(extraction_method)
            filename = os.path.basename(pdf_path)

            # Extract using the selected method
            if extraction_method == "mineru":
                raw_result = extractor.extract_pdf(pdf_path, filename)
            elif extraction_method == "documentai":
                raw_result = extractor.extract_from_pdf(pdf_path)
            else:
                raise ValueError(f"Unsupported extraction method: {extraction_method}")

            # Adapt the response to expected format
            result = self._adapt_response(raw_result, extraction_method)

            # Add processing metadata
            result["metadata"]["processing_method"] = f"{extraction_method}_direct"
            result["metadata"]["original_file"] = pdf_path

            return result

        except Exception as e:
            logger.error(
                f"Error processing small PDF with {extraction_method}: {str(e)}"
            )
            raise

    def process_pdf(
        self, pdf_path: str, extraction_method: str = "mineru"
    ) -> Dict[str, Any]:
        """
        Smart PDF processing - chunks if needed, processes directly if small

        Args:
            pdf_path: Path to the PDF file
            extraction_method: Method to use for extraction ('mineru' or 'documentai')

        Returns:
            Complete document results
        """
        try:
            logger.info(f"Starting smart processing for: {pdf_path}")

            logger.info(f"Using extraction method: {extraction_method}")

            # Check if PDF needs chunking
            chunks = self.chunker.chunk_pdf(pdf_path)

            if len(chunks) == 1 and not chunks[0]["is_chunked"]:
                # Small PDF - process directly
                logger.info(
                    f"PDF is small, processing directly with {extraction_method}"
                )
                return self.process_small_pdf(pdf_path, extraction_method)
            else:
                # Large PDF - process with chunking
                logger.info(
                    f"PDF is large, processing with chunking using {extraction_method}"
                )
                return self.process_large_pdf(pdf_path, extraction_method)

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

            print("✅ Processing completed!")
            print(f"📄 Total pages: {result['metadata']['total_pages']}")
            print(f"📊 Total tables: {len(result['tables'])}")
            print(f"🔧 Processing method: {result['metadata']['processing_method']}")

            if result["metadata"]["processing_method"] == "chunked_document_ai":
                print(f"📦 Chunks created: {result['metadata']['chunks_created']}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
    else:
        print(f"PDF file not found: {pdf_path}")
