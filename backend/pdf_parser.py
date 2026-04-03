"""
pdf_parser.py
-------------
Handles PDF text extraction using pdfplumber (preferred) with PyPDF2 as fallback.
Supports chunking for large documents to stay within LLM token limits.
"""

import io
import logging
from typing import List

try:
    import pdfplumber
    PDF_BACKEND = "pdfplumber"
except ImportError:
    pdfplumber = None
    PDF_BACKEND = None

try:
    import PyPDF2
    if PDF_BACKEND is None:
        PDF_BACKEND = "PyPDF2"
except ImportError:
    PyPDF2 = None

logger = logging.getLogger(__name__)

# Maximum characters per chunk sent to the LLM
CHUNK_SIZE = 4000
# Overlap between chunks to preserve context across boundaries
CHUNK_OVERLAP = 200


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF file given its raw bytes.

    Args:
        file_bytes: Raw bytes of the uploaded PDF.

    Returns:
        Extracted text as a single string.

    Raises:
        ValueError: If the PDF is empty or text could not be extracted.
        RuntimeError: If no PDF parsing library is available.
    """
    if pdfplumber is not None:
        return _extract_with_pdfplumber(file_bytes)
    elif PyPDF2 is not None:
        return _extract_with_pypdf2(file_bytes)
    else:
        raise RuntimeError(
            "No PDF parsing library found. "
            "Please install pdfplumber or PyPDF2: pip install pdfplumber PyPDF2"
        )


def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    """Extract text using pdfplumber (handles complex layouts better)."""
    text_pages: List[str] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        total_pages = len(pdf.pages)
        if total_pages == 0:
            raise ValueError("The PDF contains no pages.")

        logger.info(f"Extracting text from {total_pages} pages using pdfplumber.")

        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text_pages.append(page_text.strip())
            else:
                logger.debug(f"Page {i + 1} yielded no text (possibly image-only).")

    full_text = "\n\n".join(text_pages).strip()
    if not full_text:
        raise ValueError(
            "No extractable text found in the PDF. "
            "The file may consist entirely of scanned images."
        )

    logger.info(f"Extracted {len(full_text)} characters from PDF.")
    return full_text


def _extract_with_pypdf2(file_bytes: bytes) -> str:
    """Extract text using PyPDF2 as fallback."""
    text_pages: List[str] = []

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    total_pages = len(reader.pages)

    if total_pages == 0:
        raise ValueError("The PDF contains no pages.")

    logger.info(f"Extracting text from {total_pages} pages using PyPDF2.")

    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text_pages.append(page_text.strip())
        else:
            logger.debug(f"Page {i + 1} yielded no text.")

    full_text = "\n\n".join(text_pages).strip()
    if not full_text:
        raise ValueError(
            "No extractable text found in the PDF. "
            "The file may consist entirely of scanned images."
        )

    logger.info(f"Extracted {len(full_text)} characters from PDF.")
    return full_text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split a large text into overlapping chunks.

    Chunks are split on whitespace boundaries to avoid cutting mid-word.
    Overlap ensures context is preserved at chunk boundaries.

    Args:
        text:       Full document text.
        chunk_size: Target size in characters for each chunk.
        overlap:    Number of characters to repeat from the previous chunk.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Avoid cutting in the middle of a word
        if end < len(text):
            # Walk back to the nearest whitespace
            while end > start and not text[end].isspace():
                end -= 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward, keeping overlap from the end of this chunk
        start = end - overlap if end - overlap > start else end

    logger.info(f"Text split into {len(chunks)} chunks.")
    return chunks


def get_representative_chunks(
    text: str,
    num_chunks: int = 5,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    Return a representative subset of chunks spread evenly across the document.

    Useful when the document is very large and we only want a sample for MCQ generation.

    Args:
        text:       Full document text.
        num_chunks: Maximum number of chunks to return.
        chunk_size: Target chunk size in characters.
        overlap:    Overlap between chunks.

    Returns:
        Up to `num_chunks` evenly distributed text chunks.
    """
    all_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    if len(all_chunks) <= num_chunks:
        return all_chunks

    # Pick evenly spaced indices
    step = len(all_chunks) / num_chunks
    indices = [int(i * step) for i in range(num_chunks)]
    return [all_chunks[i] for i in indices]
