# AI Defect Detection Report Generator

This project is a Streamlit-based application that automatically generates a structured Defect Detection Report (DDR) from inspection and thermal inspection PDFs.

Inspection reports are often long and unstructured, making it time-consuming to manually review issues and produce structured reports. This system automates that process by extracting information from inspection documents, analyzing it using a large language model, and generating a professionally formatted DDR report.

---

## How It Works

The application follows a multi-stage processing pipeline:

1. **File Upload**
   - Users upload an inspection report PDF and a thermal inspection report PDF using the Streamlit interface.

2. **Document Extraction**
   - Text and images are extracted from both PDFs using **PyMuPDF (fitz)**.
   - Page boundaries are preserved and embedded images are collected with metadata such as page number and dimensions.

3. **LLM Analysis**
   - The extracted text is sent to **Groq’s Llama 3.3 70B model**.
   - The prompt includes a strict JSON schema that defines the structure of the Defect Detection Report.
   - The model converts the raw document content into structured data including:
     - Property information
     - Issue summaries
     - Area-wise observations
     - Root causes
     - Severity levels
     - Recommended actions

4. **Report Generation**
   - The structured data is used to generate a formatted DDR PDF using **ReportLab**.
   - The final report includes tables, summaries, severity classifications, and recommended actions.

5. **User Output**
   - The Streamlit interface shows a quick summary of findings.
   - Users can download the generated DDR report as a PDF.

---

## Tech Stack

- **Frontend / UI:** Streamlit
- **LLM:** Groq API (Llama 3.3 70B Versatile)
- **PDF Processing:** PyMuPDF (fitz)
- **Image Handling:** Pillow
- **Report Generation:** ReportLab
- **Language:** Python

---

## Features

- Upload inspection and thermal PDFs
- Automatic text and image extraction
- AI-powered defect analysis
- Structured DDR report generation
- Downloadable professional PDF report
- Simple Streamlit interface

---

## Limitations

- Very large reports are truncated before being sent to the model to stay within context limits.
- Image matching to report sections currently uses simple heuristics.
- The system relies on the LLM returning correctly formatted JSON.

---

## Future Improvements

- Implement retrieval-based document processing using embeddings instead of truncation.
- Improve image-to-text alignment using vision models.
- Separate the architecture into frontend and backend services for production deployment.
