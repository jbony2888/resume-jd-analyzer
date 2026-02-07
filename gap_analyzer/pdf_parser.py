"""PDF parsing utilities for extracting text from résumés."""

from pathlib import Path
from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extract text from a PDF file (e.g., résumé).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text content. Returns empty string if extraction fails.

    Note:
        Scanned PDFs (image-only) will return minimal or empty text.
        Use OCR (e.g., Tesseract) for scanned documents.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    reader = PdfReader(path)
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    return "\n\n".join(text_parts).strip()
