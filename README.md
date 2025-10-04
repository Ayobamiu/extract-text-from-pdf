# PDF Extraction Microservice

A Python microservice for extracting text and tables from PDFs using Google Document AI, designed to work with Node.js applications.

## Features

- **Google Document AI**: Uses Google's advanced Document AI for high-accuracy extraction
- **High Accuracy**: Optimized for old PDFs, handwritten content, and complex tables
- **REST API**: Flask-based API for easy integration with Node.js
- **Robust Error Handling**: Graceful fallbacks and comprehensive logging
- **Page Limit Handling**: Smart processing for large documents (up to 30 pages)
- **Configurable**: Environment-based configuration

## Installation

1. Install Python dependencies:

```bash
cd extract
pip install -r requirements.txt
```

2. Set up Google Cloud Document AI:

Follow the detailed setup guide in `SETUP_GUIDE.md` to:

- Create a Google Cloud project
- Enable Document AI API
- Create a Document AI processor
- Download service account credentials

## Usage

### Start the service:

```bash
python app.py
```

The service will run on `http://localhost:5001`

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
# Google Cloud Document AI settings
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_PROCESSOR_ID=your-processor-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/key.json
GOOGLE_LOCATION=us-central1

# Document AI Processing Options
MAX_PAGES_PER_REQUEST=15

# Server Configuration
HOST=0.0.0.0
PORT=5001
DEBUG=true

# File Upload Settings
MAX_FILE_SIZE=52428800
UPLOAD_FOLDER=uploads
TEMP_FOLDER=temp
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
    const response = await axios.post("http://localhost:5001/extract", form, {
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
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

## Troubleshooting

1. **Google Cloud credentials**: Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to a valid service account key
2. **Page limit errors**: Documents over 30 pages will be processed partially with warnings
3. **API errors**: Check your Google Cloud project ID and processor ID
4. **Permission errors**: Ensure the service has read access to PDF files and write access to temp directories

For detailed setup instructions, see `SETUP_GUIDE.md`.

# extract-text-from-pdf
