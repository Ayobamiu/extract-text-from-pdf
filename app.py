from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from services.pdf_extractor import PDFExtractor
from utils.config import Config

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate Google Cloud configuration
try:
    Config.validate_google_config()
    logger.info("Google Cloud configuration validated successfully")
except ValueError as e:
    logger.error(f"Google Cloud configuration error: {str(e)}")
    logger.error("Please set the following environment variables:")
    logger.error("- GOOGLE_PROJECT_ID")
    logger.error("- GOOGLE_PROCESSOR_ID")
    logger.error("- GOOGLE_APPLICATION_CREDENTIALS (path to service account JSON)")
    logger.error("- GOOGLE_LOCATION (optional, defaults to 'us')")
    logger.error("")
    logger.error(
        "For testing without Google Cloud, you can temporarily comment out the validation."
    )
    raise

app = Flask(__name__)
CORS(app)  # Enable CORS for Node.js communication

# Initialize PDF extractor
pdf_extractor = PDFExtractor()


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "pdf-extractor"})


@app.route("/extract", methods=["POST"])
def extract_pdf():
    """Main PDF extraction endpoint"""
    try:
        # Check if file is provided
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Save uploaded file temporarily
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)

        try:
            # Extract data from PDF
            logger.info(f"Processing PDF: {file.filename}")
            results = pdf_extractor.extract_from_pdf(temp_path)

            return jsonify(
                {"success": True, "data": results, "filename": file.filename}
            )

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/extract-text", methods=["POST"])
def extract_text_only():
    """Extract only text content (no tables)"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        temp_path = f"temp_text_{file.filename}"
        file.save(temp_path)

        try:
            results = pdf_extractor.extract_text_only(temp_path)
            return jsonify(
                {"success": True, "text": results, "filename": file.filename}
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/extract-tables", methods=["POST"])
def extract_tables_only():
    """Extract only tables from PDF"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        temp_path = f"temp_tables_{file.filename}"
        file.save(temp_path)

        try:
            results = pdf_extractor.extract_tables_only(temp_path)
            return jsonify(
                {"success": True, "tables": results, "filename": file.filename}
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error extracting tables: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
