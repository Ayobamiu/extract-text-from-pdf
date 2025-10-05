from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import tempfile
import logging
from services.pdf_extractor import PDFExtractor
from chunked_processor import ChunkedPDFProcessor
from utils.config import Config

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_google_credentials():
    """Setup Google Cloud credentials for production"""
    try:
        # Check if we have service account JSON in environment variable
        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if service_account_json:
            logger.info(
                "Setting up Google credentials from GOOGLE_SERVICE_ACCOUNT_JSON"
            )

            # Parse the JSON to validate it
            try:
                credentials_data = json.loads(service_account_json)
                logger.info(
                    f"Service account for project: {credentials_data.get('project_id', 'unknown')}"
                )
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
                raise ValueError("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON")

            # Create temporary file for credentials
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                f.write(service_account_json)
                credentials_path = f.name

            # Set the environment variable for Google Cloud libraries
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            logger.info(f"Google credentials file created at: {credentials_path}")

        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            logger.info("Using existing GOOGLE_APPLICATION_CREDENTIALS file path")

        else:
            logger.warning(
                "No Google credentials found. Service will start but Document AI will fail."
            )

    except Exception as e:
        logger.error(f"Error setting up Google credentials: {e}")
        raise


# Setup Google credentials before validating config
try:
    setup_google_credentials()
except Exception as e:
    logger.error(f"Failed to setup Google credentials: {e}")
    # Don't raise here - let the service start and fail gracefully

# Validate Google Cloud configuration
try:
    Config.validate_google_config()
    logger.info("Google Cloud configuration validated successfully")
except ValueError as e:
    logger.error(f"Google Cloud configuration error: {str(e)}")
    logger.error("Please set the following environment variables:")
    logger.error("- GOOGLE_PROJECT_ID")
    logger.error("- GOOGLE_PROCESSOR_ID")
    logger.error(
        "- GOOGLE_SERVICE_ACCOUNT_JSON (JSON content) OR GOOGLE_APPLICATION_CREDENTIALS (file path)"
    )
    logger.error("- GOOGLE_LOCATION (optional, defaults to 'us')")
    logger.error("")
    logger.error("Service will start but Document AI features will not work.")

app = Flask(__name__)
CORS(app)  # Enable CORS for Node.js communication

# Initialize PDF extractor and chunked processor
try:
    pdf_extractor = PDFExtractor()
    chunked_processor = ChunkedPDFProcessor()  # Uses MAX_PAGES_PER_REQUEST from config
    logger.info("PDF extractor and chunked processor initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize PDF extractor: {e}")
    pdf_extractor = None
    chunked_processor = None


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "service": "pdf-extractor",
        "google_cloud_configured": pdf_extractor is not None,
    }
    return jsonify(status)


@app.route("/extract", methods=["POST"])
def extract_pdf():
    """Main PDF extraction endpoint with automatic chunking for large PDFs"""
    try:
        logger.info("=== EXTRACT ENDPOINT CALLED ===")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request files: {list(request.files.keys())}")

        if not pdf_extractor:
            return jsonify(
                {
                    "status": "error",
                    "message": "PDF extractor not initialized. Check Google Cloud configuration.",
                }
            ), 500

        # Check if file is provided
        if "file" not in request.files:
            logger.error("No file provided in request")
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            logger.error("No file selected")
            return jsonify({"error": "No file selected"}), 400

        logger.info(f"Received file: {file.filename}")
        logger.info(f"File content type: {file.content_type}")
        logger.info(f"File content length: {file.content_length}")

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            logger.error(
                f"Invalid file type: {file.filename}. Only PDF files are supported."
            )
            return jsonify({"error": "Only PDF files are supported"}), 400

        # Save uploaded file temporarily
        temp_path = f"temp_{file.filename}"
        logger.info(f"Saving file to: {temp_path}")
        file.save(temp_path)
        logger.info(
            f"File saved successfully. Size: {os.path.getsize(temp_path)} bytes"
        )

        try:
            # Use chunked processor for smart PDF processing
            logger.info(f"Starting smart PDF processing for: {file.filename}")
            results = chunked_processor.process_pdf(temp_path)
            logger.info(f"PDF processing completed successfully")

            return jsonify(
                {"success": True, "data": results, "filename": file.filename}
            )

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                logger.info(f"Cleaning up temporary file: {temp_path}")
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/extract-text", methods=["POST"])
def extract_text_only():
    """Extract only text content using chunked processing"""
    try:
        logger.info("=== EXTRACT TEXT ENDPOINT CALLED ===")

        if not pdf_extractor:
            return jsonify(
                {"status": "error", "message": "PDF extractor not initialized"}
            ), 500

        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are supported"}), 400

        # Save uploaded file temporarily
        temp_path = f"temp_text_{file.filename}"
        file.save(temp_path)

        try:
            # Use chunked processor for smart PDF processing
            logger.info(f"Starting chunked text extraction for: {file.filename}")
            results = chunked_processor.process_pdf(temp_path)

            # Extract only text from the results
            text_data = {
                "pages": results.get("pages", []),
                "full_text": results.get("full_text", ""),
                "metadata": {
                    "total_pages": results.get("metadata", {}).get("total_pages", 0),
                    "processing_method": results.get("metadata", {}).get(
                        "processing_method", "unknown"
                    ),
                    "word_count": len(results.get("full_text", "").split()),
                },
            }

            logger.info(
                f"Text extraction completed successfully. {text_data['metadata']['word_count']} words extracted"
            )
            return jsonify(
                {"success": True, "text": text_data, "filename": file.filename}
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/extract-tables", methods=["POST"])
def extract_tables_only():
    """Extract only tables from PDF using chunked processing"""
    try:
        logger.info("=== EXTRACT TABLES ENDPOINT CALLED ===")

        if not pdf_extractor:
            return jsonify(
                {"status": "error", "message": "PDF extractor not initialized"}
            ), 500

        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are supported"}), 400

        # Save uploaded file temporarily
        temp_path = f"temp_tables_{file.filename}"
        file.save(temp_path)

        try:
            # Use chunked processor for smart PDF processing
            logger.info(f"Starting chunked table extraction for: {file.filename}")
            results = chunked_processor.process_pdf(temp_path)

            # Extract only tables from the results
            tables_data = {
                "tables": results.get("tables", []),
                "metadata": {
                    "total_tables": len(results.get("tables", [])),
                    "processing_method": results.get("metadata", {}).get(
                        "processing_method", "unknown"
                    ),
                    "total_pages": results.get("metadata", {}).get("total_pages", 0),
                },
            }

            logger.info(
                f"Table extraction completed successfully. Found {len(tables_data['tables'])} tables"
            )
            return jsonify(
                {"success": True, "tables": tables_data, "filename": file.filename}
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error extracting tables: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/extract-chunked", methods=["POST"])
def extract_pdf_chunked():
    """Force chunked processing for large PDFs"""
    try:
        logger.info("=== CHUNKED EXTRACT ENDPOINT CALLED ===")

        if not chunked_processor:
            return jsonify(
                {"status": "error", "message": "Chunked processor not initialized"}
            ), 500

        # Check if file is provided
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are supported"}), 400

        # Save uploaded file temporarily
        temp_path = f"temp_chunked_{file.filename}"
        file.save(temp_path)

        try:
            # Force chunked processing
            logger.info(f"Starting forced chunked processing for: {file.filename}")
            results = chunked_processor.process_large_pdf(temp_path)
            logger.info(f"Chunked processing completed successfully")

            return jsonify(
                {"success": True, "data": results, "filename": file.filename}
            )

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error in chunked processing: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    # Create necessary directories
    Config.create_directories()

    # Start the Flask app
    port = int(os.getenv("PORT", 5001))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    logger.info(f"Starting Flask PDF Extractor service on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
