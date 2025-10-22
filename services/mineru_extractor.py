"""
MinerU PDF Extractor Service

This service handles PDF extraction using MinerU API with markdown cleaning.
Separated from the main PDF extractor to maintain separation of concerns.
"""

import os
import tempfile
import logging
import signal
import sys
from typing import Dict, Any, Optional
from utils.config import Config

# Fix PyTorch model loading issue
import torch

torch.serialization.add_safe_globals(["doclayout_yolo.nn.tasks.YOLOv10DetectionModel"])

logger = logging.getLogger(__name__)

# Import MinerU API functions
try:
    from mineru.cli.common import do_parse, prepare_env
    from mineru.utils.enum_class import MakeMode

    logger.info("✅ MinerU API functions imported successfully")
    mineru_available = True
except ImportError as e:
    logger.error(f"❌ Failed to import MinerU API: {e}")
    mineru_available = False

# Import markdown cleaner
try:
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from clean_mineru_markdown import clean_lines_pipeline

    logger.info("✅ MinerU markdown cleaner imported successfully")
    cleaner_available = True
except ImportError as e:
    logger.error(f"❌ Failed to import MinerU markdown cleaner: {e}")
    cleaner_available = False


class MinerUExtractor:
    """MinerU PDF Extractor with markdown cleaning capabilities"""

    def __init__(self):
        """Initialize the MinerU extractor"""
        self.mineru_available = mineru_available
        self.cleaner_available = cleaner_available

        # Timeout settings
        self.timeout = Config.MINERU_TIMEOUT if Config.MINERU_TIMEOUT > 0 else None
        self.max_file_size_mb = Config.MAX_FILE_SIZE_MB
        self.enable_large_file_chunking = Config.ENABLE_LARGE_FILE_CHUNKING

        if not self.mineru_available:
            logger.warning("MinerU API not available - extraction will fail")
        if not self.cleaner_available:
            logger.warning(
                "MinerU markdown cleaner not available - raw output will be returned"
            )

        logger.info(
            f"MinerU timeout: {'Disabled' if self.timeout is None else f'{self.timeout}s'}"
        )
        logger.info(f"Max file size: {self.max_file_size_mb}MB")
        logger.info(
            f"Large file chunking: {'Enabled' if self.enable_large_file_chunking else 'Disabled'}"
        )

    def extract_pdf(self, pdf_path: str, filename: str) -> Dict[str, Any]:
        """
        Extract PDF using MinerU API and clean the markdown output

        Args:
            pdf_path: Path to the PDF file
            filename: Original filename

        Returns:
            Dictionary with extraction results
        """
        if not self.mineru_available:
            return {
                "success": False,
                "error": "MinerU API not available",
                "filename": filename,
            }

        try:
            # Check file size
            file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
            logger.info(
                f"Starting MinerU extraction for: {filename} ({file_size_mb:.2f}MB)"
            )

            if file_size_mb > self.max_file_size_mb:
                logger.warning(
                    f"File size ({file_size_mb:.2f}MB) exceeds limit ({self.max_file_size_mb}MB)"
                )
                if not self.enable_large_file_chunking:
                    return {
                        "success": False,
                        "error": f"File too large ({file_size_mb:.2f}MB). Max allowed: {self.max_file_size_mb}MB",
                        "filename": filename,
                    }

            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create output directory
                output_dir = os.path.join(temp_dir, "output")
                os.makedirs(output_dir, exist_ok=True)

                # Read PDF file as bytes
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                logger.info(f"PDF file read: {len(pdf_bytes)} bytes")

                # Use MinerU API directly with timeout handling
                logger.info(f"Calling MinerU do_parse for: {filename}")

                # Set up timeout handler if timeout is configured
                if self.timeout:
                    logger.info(f"Setting timeout to {self.timeout} seconds")

                    def timeout_handler(signum, frame):
                        logger.error(
                            f"MinerU processing timed out after {self.timeout} seconds"
                        )
                        raise TimeoutError(
                            f"MinerU processing timed out after {self.timeout} seconds"
                        )

                    # Set the timeout
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(self.timeout)

                try:
                    do_parse(
                        output_dir=output_dir,
                        pdf_file_names=[filename],
                        pdf_bytes_list=[pdf_bytes],
                        p_lang_list=["en"],  # English
                        backend="pipeline",
                        parse_method="auto",
                        formula_enable=False,
                        table_enable=True,
                        f_dump_md=True,
                        f_dump_middle_json=True,
                        f_dump_model_output=True,
                        f_dump_orig_pdf=False,
                        f_dump_content_list=False,
                        f_make_md_mode=MakeMode.MM_MD,
                    )

                    logger.info("MinerU API extraction completed successfully")

                except TimeoutError as e:
                    logger.error(f"MinerU processing timed out: {str(e)}")
                    return {
                        "success": False,
                        "error": f"MinerU processing timed out after {self.timeout} seconds. Try increasing MINERU_TIMEOUT or processing smaller files.",
                        "filename": filename,
                    }
                finally:
                    # Cancel the timeout
                    if self.timeout:
                        signal.alarm(0)

                # Find the generated markdown file
                markdown_files = []
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith(".md"):
                            markdown_files.append(os.path.join(root, file))

                if not markdown_files:
                    logger.error("No markdown file generated")
                    return {
                        "success": False,
                        "error": "No markdown file generated",
                        "filename": filename,
                    }

                # Read the first markdown file
                markdown_file = markdown_files[0]
                logger.info(f"Reading markdown from: {markdown_file}")

                with open(markdown_file, "r", encoding="utf-8") as f:
                    markdown_content = f.read()

                # Clean the markdown using our cleaner
                cleaned_markdown = self._clean_markdown(markdown_content)

                logger.info("MinerU extraction and cleaning completed successfully")

                return {
                    "success": True,
                    "filename": filename,
                    "data": {
                        "markdown": cleaned_markdown,
                        "metadata": {
                            "processing_method": "mineru_api",
                            "total_pages": self._count_pages(markdown_content),
                            "word_count": len(cleaned_markdown.split()),
                            "original_file": filename,
                            "file_size_mb": file_size_mb,
                        },
                        "pages": [],
                        "tables": [],
                        "full_text": cleaned_markdown,
                        "raw_text": cleaned_markdown,
                        "structured_data": {},
                    },
                }

        except Exception as e:
            logger.error(f"Error processing PDF with MinerU API: {str(e)}")
            return {
                "success": False,
                "error": f"Error processing PDF: {str(e)}",
                "filename": filename,
            }

    def _clean_markdown(self, markdown_content: str) -> str:
        """
        Clean the markdown content using our markdown cleaner

        Args:
            markdown_content: Raw markdown content from MinerU

        Returns:
            Cleaned markdown content
        """
        if not self.cleaner_available:
            logger.warning("Markdown cleaner not available, returning raw content")
            return markdown_content

        try:
            logger.info("Cleaning markdown content...")
            lines = markdown_content.splitlines()

            # Create args object for the cleaner
            class CleanerArgs:
                def __init__(self):
                    self.header_repeat_threshold = 3
                    self.debug = False
                    self.middle_json = None

            args = CleanerArgs()

            # Process the markdown
            cleaned_lines = clean_lines_pipeline(lines, args)
            cleaned_markdown = "\n".join(cleaned_lines)

            logger.info("Markdown cleaning completed successfully")
            return cleaned_markdown

        except Exception as e:
            logger.error(f"Error cleaning markdown: {str(e)}")
            return markdown_content  # Return original if cleaning fails

    def _count_pages(self, markdown_content: str) -> int:
        """
        Estimate page count from markdown content

        Args:
            markdown_content: Markdown content

        Returns:
            Estimated page count
        """
        try:
            # Simple heuristic: count page breaks or estimate from content length
            page_breaks = markdown_content.count("\f")  # Form feed characters
            if page_breaks > 0:
                return page_breaks + 1

            # Estimate based on content length (rough approximation)
            lines = markdown_content.splitlines()
            return max(1, len(lines) // 50)  # Assume ~50 lines per page

        except Exception:
            return 1

    def is_available(self) -> bool:
        """Check if MinerU extractor is available"""
        return self.mineru_available

    def cleanup(self):
        """Clean up MinerU resources to prevent semaphore leaks"""
        try:
            logger.info("Cleaning up MinerU resources...")

            # Clear PyTorch cache
            if "torch" in globals():
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                torch.cuda.synchronize()

            logger.info("MinerU cleanup completed")
        except Exception as e:
            logger.warning(f"Error during MinerU cleanup: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the MinerU extractor"""
        return {
            "mineru_available": self.mineru_available,
            "cleaner_available": self.cleaner_available,
            "status": "ready" if self.mineru_available else "not_available",
        }
