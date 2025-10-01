# PDF Extraction Microservice

A Python microservice for extracting text and tables from PDFs, designed to work with Node.js applications.

## Features

- **Hybrid Extraction**: Combines Camelot for table extraction and Tesseract OCR for text
- **High Accuracy**: Optimized preprocessing for old PDFs and handwritten content
- **REST API**: Flask-based API for easy integration with Node.js
- **Robust Error Handling**: Graceful fallbacks and comprehensive logging
- **Configurable**: Environment-based configuration

## Installation

1. Install Python dependencies:

```bash
cd extract
pip install -r requirements.txt
```

2. Install system dependencies:

```bash
# macOS
brew install tesseract ghostscript

# Ubuntu/Debian
sudo apt-get install tesseract-ocr ghostscript

# Windows
# Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
```

## Usage

### Start the service:

```bash
python app.py
```

The service will run on `http://localhost:5000`

### API Endpoints:

#### 1. Health Check

```bash
GET /health
```

#### 2. Extract Everything (Text + Tables)

```bash
POST /extract
Content-Type: multipart/form-data
Body: file (PDF file)
```

#### 3. Extract Text Only

```bash
POST /extract-text
Content-Type: multipart/form-data
Body: file (PDF file)
```

#### 4. Extract Tables Only

```bash
POST /extract-tables
Content-Type: multipart/form-data
Body: file (PDF file)
```

### Example Response:

```json
{
  "success": true,
  "data": {
    "pages": [
      {
        "page_number": 1,
        "text": "Extracted text content...",
        "text_confidence": 0.87,
        "tables": [
          {
            "table_id": 1,
            "page": 1,
            "method": "lattice",
            "data": [
              ["Header1", "Header2"],
              ["Row1Col1", "Row1Col2"]
            ],
            "confidence": 0.95,
            "bbox": { "x1": 100, "y1": 200, "x2": 500, "y2": 400 }
          }
        ]
      }
    ],
    "metadata": {
      "total_pages": 1,
      "extraction_method": "hybrid",
      "has_tables": true
    }
  },
  "filename": "document.pdf"
}
```

## Configuration

Create a `.env` file in the extract directory:

```env
HOST=0.0.0.0
PORT=5000
DEBUG=False
TESSERACT_CMD=/usr/local/bin/tesseract
OCR_DPI=300
MAX_FILE_SIZE=52428800
UPLOAD_FOLDER=uploads
TEMP_FOLDER=temp
ENABLE_TABLE_EXTRACTION=True
ENABLE_OCR_EXTRACTION=True
LOG_LEVEL=INFO
```

## Integration with Node.js

### Using axios in your Node.js app:

```javascript
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");

async function extractPDF(pdfPath) {
  const form = new FormData();
  form.append("file", fs.createReadStream(pdfPath));

  try {
    const response = await axios.post("http://localhost:5000/extract", form, {
      headers: form.getHeaders(),
    });

    return response.data;
  } catch (error) {
    console.error(
      "PDF extraction failed:",
      error.response?.data || error.message
    );
    throw error;
  }
}

// Usage
extractPDF("./document.pdf")
  .then((result) => console.log(result))
  .catch((error) => console.error(error));
```

## Development

### Running in Development Mode:

```bash
export DEBUG=True
python app.py
```

### Running with Gunicorn (Production):

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Troubleshooting

1. **Tesseract not found**: Make sure Tesseract is installed and in your PATH
2. **Ghostscript errors**: Install Ghostscript for Camelot to work
3. **Memory issues**: Reduce OCR_DPI or process files in smaller batches
4. **Permission errors**: Ensure the service has write access to temp directories
# extract-text-from-pdf
