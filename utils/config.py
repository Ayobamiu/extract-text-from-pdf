import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration settings for the PDF extractor service"""

    # Server settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5001))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Google Cloud Document AI settings
    GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
    GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us")
    GOOGLE_PROCESSOR_ID = os.getenv("GOOGLE_PROCESSOR_ID")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Document AI processing options
    MAX_PAGES_PER_REQUEST = int(os.getenv("MAX_PAGES_PER_REQUEST", "15"))

    @classmethod
    def validate_google_config(cls):
        """Validate Google Cloud configuration"""
        required_vars = [
            ("GOOGLE_PROJECT_ID", cls.GOOGLE_PROJECT_ID),
            ("GOOGLE_PROCESSOR_ID", cls.GOOGLE_PROCESSOR_ID),
        ]

        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return True

    # File settings
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    TEMP_FOLDER = os.getenv("TEMP_FOLDER", "temp")

    # Processing settings
    ENABLE_TABLE_EXTRACTION = (
        os.getenv("ENABLE_TABLE_EXTRACTION", "True").lower() == "true"
    )
    ENABLE_OCR_EXTRACTION = os.getenv("ENABLE_OCR_EXTRACTION", "True").lower() == "true"

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.TEMP_FOLDER, exist_ok=True)
