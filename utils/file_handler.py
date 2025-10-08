import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FileHandler:
    """Handle file operations for the PDF extractor"""

    @staticmethod
    def validate_file(
        file_path: str, max_size: int = 50 * 1024 * 1024
    ) -> Dict[str, Any]:
        """
        Validate uploaded file

        Args:
            file_path: Path to the file
            max_size: Maximum file size in bytes

        Returns:
            Dict with validation results
        """
        result = {"valid": True, "errors": [], "file_info": {}}

        try:
            # Check if file exists
            if not os.path.exists(file_path):
                result["valid"] = False
                result["errors"].append("File does not exist")
                return result

            # Get file info
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_name)[1].lower()

            result["file_info"] = {
                "name": file_name,
                "size": file_size,
                "extension": file_ext,
            }

            # Check file size
            if file_size > max_size:
                result["valid"] = False
                result["errors"].append(
                    f"File too large: {file_size} bytes (max: {max_size})"
                )

            # Check file extension
            if file_ext not in [".pdf"]:
                result["valid"] = False
                result["errors"].append(
                    f"Invalid file type: {file_ext} (only PDF allowed)"
                )

            logger.info(
                f"File validation completed: {file_name} - Valid: {result['valid']}"
            )

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Validation error: {str(e)}")
            logger.error(f"File validation failed: {str(e)}")

        return result

    @staticmethod
    def cleanup_file(file_path: str) -> bool:
        """
        Clean up temporary file

        Args:
            file_path: Path to file to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup file {file_path}: {str(e)}")

        return False

    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """
        Generate a safe filename by removing special characters

        Args:
            filename: Original filename

        Returns:
            Safe filename
        """
        import re

        # Remove special characters and replace with underscores
        safe_name = re.sub(r"[^\w\-_\.]", "_", filename)
        return safe_name
