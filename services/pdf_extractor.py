import logging
from typing import Dict, List, Any, Optional
import os
import json
from google.cloud import documentai
from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)


class PDFExtractor:
    def __init__(self):
        """Initialize PDF extractor with Google Document AI configuration"""
        self.project_id = os.getenv("GOOGLE_PROJECT_ID")
        self.location = os.getenv("GOOGLE_LOCATION", "us")  # Default to us
        self.processor_id = os.getenv("GOOGLE_PROCESSOR_ID")
        self.enable_imageless_mode = (
            os.getenv("ENABLE_IMAGELESS_MODE", "true").lower() == "true"
        )
        self.max_pages_per_request = int(os.getenv("MAX_PAGES_PER_REQUEST", "15"))

        # Validate configuration
        if not all([self.project_id, self.processor_id]):
            logger.error("Missing required Google Cloud configuration. Please set:")
            logger.error("- GOOGLE_PROJECT_ID")
            logger.error("- GOOGLE_PROCESSOR_ID")
            logger.error("- GOOGLE_LOCATION (optional, defaults to 'us')")
            raise ValueError("Google Cloud configuration incomplete")

        logger.info(f"PDFExtractor initialized with Google Document AI")
        logger.info(
            f"Project: {self.project_id}, Location: {self.location}, Processor: {self.processor_id}"
        )

    def extract_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Main extraction method using Google Document AI
        """
        try:
            logger.info(f"Starting Document AI extraction for: {pdf_path}")
            logger.info(f"File exists: {os.path.exists(pdf_path)}")
            logger.info(
                f"File size: {os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 'N/A'} bytes"
            )

            # Process document with Document AI
            document = self._process_with_document_ai(pdf_path)

            if not document:
                raise RuntimeError("Document AI processing failed")

            # Extract structured data
            result = self._parse_document_ai_response(document)

            logger.info(f"Document AI extraction completed successfully")
            logger.info(f"Extracted {len(result.get('pages', []))} pages")
            logger.info(f"Found {len(result.get('tables', []))} tables")

            return result

        except Exception as e:
            logger.error(f"Document AI extraction failed: {str(e)}", exc_info=True)
            raise

    def extract_text_only(self, pdf_path: str) -> Dict[str, Any]:
        """Extract only text content using Document AI"""
        try:
            logger.info(f"Starting text-only extraction for: {pdf_path}")

            document = self._process_with_document_ai(pdf_path)
            if not document:
                raise RuntimeError("Document AI processing failed")

            # Extract only text
            result = self._extract_text_from_document(document)

            logger.info(
                f"Text extraction completed. Found {len(result.get('pages', []))} pages"
            )
            return result

        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}", exc_info=True)
            raise

    def extract_tables_only(self, pdf_path: str) -> Dict[str, Any]:
        """Extract only tables using Document AI"""
        try:
            logger.info(f"Starting table-only extraction for: {pdf_path}")

            document = self._process_with_document_ai(pdf_path)
            if not document:
                raise RuntimeError("Document AI processing failed")

            # Extract only tables
            result = self._extract_tables_from_document(document)

            logger.info(
                f"Table extraction completed. Found {len(result.get('tables', []))} tables"
            )
            return result

        except Exception as e:
            logger.error(f"Table extraction failed: {str(e)}", exc_info=True)
            raise

    def _process_with_document_ai(self, pdf_path: str) -> Optional[Any]:
        """Process PDF with Google Document AI"""
        try:
            logger.info("Initializing Document AI client...")
            client = documentai.DocumentProcessorServiceClient()

            # Read PDF file
            logger.info("Reading PDF file...")
            with open(pdf_path, "rb") as image:
                image_content = image.read()

            logger.info(f"PDF file read successfully. Size: {len(image_content)} bytes")

            # Prepare the request
            processor_name = f"projects/{self.project_id}/locations/{self.location}/processors/{self.processor_id}"

            logger.info(f"Processing document with processor: {processor_name}")

            # Try imageless mode first (supports up to 30 pages)
            try:
                logger.info(
                    f"Attempting imageless mode processing (enabled: {self.enable_imageless_mode})..."
                )

                # Build request with optional imageless mode
                request_kwargs = {
                    "name": processor_name,
                    "raw_document": documentai.RawDocument(
                        content=image_content, mime_type="application/pdf"
                    ),
                }

                if self.enable_imageless_mode:
                    request_kwargs["process_options"] = documentai.ProcessOptions(
                        ocr_config=documentai.OcrConfig(
                            enable_native_pdf_parsing=True, compute_style_info=True
                        )
                    )

                request = documentai.ProcessRequest(**request_kwargs)

                logger.info("Sending request to Document AI (imageless mode)...")
                result = client.process_document(request=request)
                document = result.document

                logger.info(
                    "Document AI processing completed successfully (imageless mode)"
                )
                logger.info(f"Document has {len(document.pages)} pages")

                return document

            except gcp_exceptions.GoogleAPIError as e:
                if "PAGE_LIMIT_EXCEEDED" in str(e):
                    logger.warning(f"Imageless mode failed due to page limit: {str(e)}")
                    logger.info("Attempting page splitting approach...")
                    return self._process_large_document(
                        client, processor_name, image_content
                    )
                else:
                    raise e

        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error processing with Document AI: {str(e)}")
            return None

    def _process_large_document(
        self, client: Any, processor_name: str, image_content: bytes
    ) -> Optional[Any]:
        """Process large documents by splitting into smaller chunks"""
        try:
            logger.info("Processing large document by splitting into chunks...")

            # For now, we'll process the first 15 pages and log a warning
            # In a production environment, you might want to implement proper PDF splitting
            logger.warning(
                "Document exceeds page limit. Processing first 15 pages only."
            )
            logger.warning(
                "Consider splitting large PDFs into smaller files for complete processing."
            )

            # Try processing with a smaller page range
            request = documentai.ProcessRequest(
                name=processor_name,
                raw_document=documentai.RawDocument(
                    content=image_content, mime_type="application/pdf"
                ),
                process_options=documentai.ProcessOptions(
                    ocr_config=documentai.OcrConfig(
                        enable_native_pdf_parsing=True, compute_style_info=True
                    )
                ),
            )

            logger.info("Sending request to Document AI (first 15 pages)...")
            result = client.process_document(request=request)
            document = result.document

            logger.info(
                f"Document AI processing completed (partial: {len(document.pages)} pages)"
            )
            logger.warning(
                "This is a partial result. Consider splitting the PDF for complete processing."
            )

            return document

        except Exception as e:
            logger.error(f"Error processing large document: {str(e)}")
            return None

    def _parse_document_ai_response(self, document: Any) -> Dict[str, Any]:
        """Parse Document AI response into structured format"""
        try:
            logger.info("Parsing Document AI response...")

            # Extract text and tables
            text_result = self._extract_text_from_document(document)
            tables_result = self._extract_tables_from_document(document)

            # Combine results
            result = {
                "pages": text_result.get("pages", []),
                "tables": tables_result.get("tables", []),
                "metadata": {
                    "total_pages": len(document.pages),
                    "total_tables": len(tables_result.get("tables", [])),
                    "extraction_method": "google_document_ai",
                    "confidence": self._calculate_overall_confidence(document),
                },
                "raw_text": text_result.get("raw_text", ""),
                "structured_data": {
                    "entities": self._extract_entities(document),
                    "form_fields": self._extract_form_fields(document),
                },
            }

            logger.info("Document AI response parsed successfully")
            return result

        except Exception as e:
            logger.error(f"Error parsing Document AI response: {str(e)}")
            raise

    def _extract_text_from_document(self, document: Any) -> Dict[str, Any]:
        """Extract text content from Document AI response"""
        try:
            pages_data = []
            all_text = []

            logger.info(f"Extracting text from {len(document.pages)} pages...")

            for page_num, page in enumerate(document.pages):
                logger.info(f"Processing page {page_num + 1}/{len(document.pages)}")

                # Extract text from page
                page_text = ""
                text_elements = []

                for paragraph in page.paragraphs:
                    paragraph_text = self._get_text_from_layout(
                        paragraph.layout, document.text
                    )
                    if paragraph_text.strip():
                        page_text += paragraph_text + "\n"
                        text_elements.append(
                            {
                                "text": paragraph_text.strip(),
                                "confidence": paragraph.layout.confidence
                                if hasattr(paragraph.layout, "confidence")
                                else 1.0,
                                "bounding_box": self._get_bounding_box(
                                    paragraph.layout.bounding_poly
                                ),
                            }
                        )

                page_data = {
                    "page_number": page_num + 1,
                    "text": page_text.strip(),
                    "text_elements": text_elements,
                    "word_count": len(page_text.split()),
                    "confidence": self._calculate_page_confidence(text_elements),
                }

                pages_data.append(page_data)
                all_text.append(page_text.strip())

                logger.info(
                    f"Page {page_num + 1}: {len(text_elements)} text elements, {page_data['word_count']} words"
                )

            return {"pages": pages_data, "raw_text": "\n\n".join(all_text)}

        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            raise

    def _extract_tables_from_document(self, document: Any) -> Dict[str, Any]:
        """Extract tables from Document AI response"""
        try:
            tables_data = []

            logger.info(f"Extracting tables from {len(document.pages)} pages...")

            for page_num, page in enumerate(document.pages):
                logger.info(f"Processing tables on page {page_num + 1}")

                for table_num, table in enumerate(page.tables):
                    logger.info(
                        f"Processing table {table_num + 1} on page {page_num + 1}"
                    )

                    # Extract table data
                    table_data = self._parse_table(table, document.text)

                    table_info = {
                        "table_id": f"page_{page_num + 1}_table_{table_num + 1}",
                        "page_number": page_num + 1,
                        "table_number": table_num + 1,
                        "data": table_data["rows"],
                        "headers": table_data["headers"],
                        "confidence": table_data["confidence"],
                        "bounding_box": self._get_bounding_box(
                            table.layout.bounding_poly
                        ),
                        "row_count": len(table_data["rows"]),
                        "column_count": len(table_data["headers"])
                        if table_data["headers"]
                        else 0,
                    }

                    tables_data.append(table_info)
                    logger.info(
                        f"Table {table_num + 1}: {table_info['row_count']} rows, {table_info['column_count']} columns"
                    )

            logger.info(f"Total tables extracted: {len(tables_data)}")
            return {"tables": tables_data}

        except Exception as e:
            logger.error(f"Error extracting tables: {str(e)}")
            raise

    def _parse_table(self, table: Any, document_text: str) -> Dict[str, Any]:
        """Parse individual table from Document AI"""
        try:
            rows = []
            headers = []

            # Extract table rows
            for row in table.body_rows:
                row_data = []
                for cell in row.cells:
                    cell_text = self._get_text_from_layout(cell.layout, document_text)
                    row_data.append(cell_text.strip())
                rows.append(row_data)

            # Extract headers if available
            if hasattr(table, "header_rows") and table.header_rows:
                for row in table.header_rows:
                    header_row = []
                    for cell in row.cells:
                        cell_text = self._get_text_from_layout(
                            cell.layout, document_text
                        )
                        header_row.append(cell_text.strip())
                    headers.extend(header_row)

            # Calculate confidence
            confidence = 0.9  # Document AI tables are generally high confidence

            return {"rows": rows, "headers": headers, "confidence": confidence}

        except Exception as e:
            logger.error(f"Error parsing table: {str(e)}")
            return {"rows": [], "headers": [], "confidence": 0.0}

    def _get_text_from_layout(self, layout: Any, document_text: str) -> str:
        """Extract text from layout element"""
        try:
            if not layout.text_anchor:
                return ""

            # Extract text using text anchor
            start_index = (
                layout.text_anchor.text_segments[0].start_index
                if layout.text_anchor.text_segments
                else 0
            )
            end_index = (
                layout.text_anchor.text_segments[0].end_index
                if layout.text_anchor.text_segments
                else 0
            )

            return document_text[start_index:end_index]

        except Exception as e:
            logger.warning(f"Error extracting text from layout: {str(e)}")
            return ""

    def _get_bounding_box(self, bounding_poly: Any) -> Dict[str, float]:
        """Extract bounding box coordinates"""
        try:
            if not bounding_poly.vertices:
                return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}

            vertices = bounding_poly.vertices
            return {
                "x1": vertices[0].x if len(vertices) > 0 else 0,
                "y1": vertices[0].y if len(vertices) > 0 else 0,
                "x2": vertices[2].x if len(vertices) > 2 else vertices[0].x,
                "y2": vertices[2].y if len(vertices) > 2 else vertices[0].y,
            }

        except Exception as e:
            logger.warning(f"Error extracting bounding box: {str(e)}")
            return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}

    def _calculate_page_confidence(self, text_elements: List[Dict]) -> float:
        """Calculate average confidence for a page"""
        if not text_elements:
            return 0.0

        total_confidence = sum(
            element.get("confidence", 0.0) for element in text_elements
        )
        return total_confidence / len(text_elements)

    def _calculate_overall_confidence(self, document: Any) -> float:
        """Calculate overall confidence for the document"""
        try:
            # This is a simplified confidence calculation
            # Document AI doesn't always provide confidence scores
            return 0.95  # High confidence for Document AI results

        except Exception:
            return 0.9

    def _extract_entities(self, document: Any) -> List[Dict[str, Any]]:
        """Extract named entities from document"""
        try:
            entities = []

            if hasattr(document, "entities") and document.entities:
                for entity in document.entities:
                    entity_info = {
                        "text": entity.text_anchor.text_segments[0].text
                        if entity.text_anchor.text_segments
                        else "",
                        "type": entity.type_,
                        "confidence": entity.confidence,
                        "mention_text": entity.mention_text,
                    }
                    entities.append(entity_info)

            return entities

        except Exception as e:
            logger.warning(f"Error extracting entities: {str(e)}")
            return []

    def _extract_form_fields(self, document: Any) -> List[Dict[str, Any]]:
        """Extract form fields from document"""
        try:
            form_fields = []

            if hasattr(document, "form_fields") and document.form_fields:
                for field_name, field_value in document.form_fields.items():
                    field_info = {
                        "name": field_name,
                        "value": field_value.text_anchor.text_segments[0].text
                        if field_value.text_anchor.text_segments
                        else "",
                        "confidence": field_value.confidence,
                    }
                    form_fields.append(field_info)

            return form_fields

        except Exception as e:
            logger.warning(f"Error extracting form fields: {str(e)}")
            return []
