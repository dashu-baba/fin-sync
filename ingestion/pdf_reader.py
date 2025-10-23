from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import time

from PyPDF2 import PdfReader, errors as pypdf_errors
from pdfminer.high_level import extract_text as pdfminer_extract_text, extract_pages
from pdfminer.layout import LTTextContainer
from pdfminer.pdfparser import PDFSyntaxError

from core.logger import get_logger

log = get_logger("pdf_reader")


# Configuration constants
MIN_TEXT_LEN_PER_PAGE = 20  # Minimum characters per page before triggering fallback
DEFAULT_EMPTY_PASSWORD = ""  # Default password to try for encrypted PDFs


@dataclass(frozen=True)
class PDFMeta:
    """PDF metadata extracted from document properties."""
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    producer: Optional[str]
    creator: Optional[str]


@dataclass(frozen=True)
class PDFReadResult:
    """
    Complete result from PDF reading operation.
    
    Attributes:
        path: Absolute path to the PDF file
        encrypted: Whether the PDF was encrypted
        num_pages: Total number of pages extracted
        meta: PDF metadata (title, author, etc.)
        pages: List of extracted text, one string per page
    """
    path: str
    encrypted: bool
    num_pages: int
    meta: PDFMeta
    pages: List[str]


def _pypdf2_extract(path: Path, password: Optional[str]) -> PDFReadResult:
    """
    Primary, fast extractor using PyPDF2. Handles decryption if needed.
    
    Args:
        path: Path to the PDF file
        password: Optional password for encrypted PDFs
        
    Returns:
        PDFReadResult with extracted text and metadata
        
    Raises:
        pypdf_errors.PdfReadError: If PDF is malformed or unreadable
        pypdf_errors.FileNotDecryptedError: If PDF is encrypted and password is wrong/missing
    """
    log.debug(f"Starting PyPDF2 extraction: path={path.name}")
    
    try:
        reader = PdfReader(str(path))
    except pypdf_errors.PdfReadError as e:
        log.error(f"PyPDF2 failed to open PDF: path={path.name} error={e!r}")
        raise
    except Exception as e:
        log.error(f"Unexpected error opening PDF with PyPDF2: path={path.name} error={e!r}")
        raise

    encrypted = bool(reader.is_encrypted)
    
    # Handle encrypted PDFs
    if encrypted:
        log.info(f"PDF is encrypted: path={path.name}")
        trial_passwords = [password] if password else [DEFAULT_EMPTY_PASSWORD]
        
        decryption_success = False
        for pwd_idx, pwd in enumerate(trial_passwords):
            try:
                log.debug(f"Attempting decryption (attempt {pwd_idx + 1}/{len(trial_passwords)}): path={path.name}")
                decrypt_result = reader.decrypt(pwd)
                
                # PyPDF2 returns 0 for wrong password, non-zero for success
                if decrypt_result == 0 or decrypt_result is False:
                    log.warning(f"Decryption failed - wrong password: path={path.name}")
                    continue
                    
                log.info(f"PDF decrypted successfully: path={path.name}")
                decryption_success = True
                break
                
            except pypdf_errors.WrongPasswordError:
                log.warning(f"Wrong password provided for encrypted PDF: path={path.name}")
                continue
            except pypdf_errors.FileNotDecryptedError as e:
                log.warning(f"Decryption error: path={path.name} error={e!r}")
                continue
        
        if not decryption_success:
            error_msg = f"Failed to decrypt PDF - incorrect or missing password: path={path.name}"
            log.error(error_msg)
            raise pypdf_errors.FileNotDecryptedError(error_msg)
    else:
        log.debug(f"PDF is not encrypted: path={path.name}")

    # Extract text from all pages
    pages_text: List[str] = []
    failed_pages = 0
    
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
            pages_text.append(txt)
            
            if len(txt) == 0:
                log.debug(f"Page {page_num} extracted with no text: path={path.name}")
                
        except Exception as e:
            # PyPDF2 can throw various exceptions for malformed pages
            log.warning(
                f"Failed to extract text from page {page_num}: path={path.name} error={type(e).__name__}: {e}"
            )
            pages_text.append("")
            failed_pages += 1
    
    if failed_pages > 0:
        log.warning(
            f"PyPDF2 failed on {failed_pages}/{len(pages_text)} pages: path={path.name}"
        )

    # Extract metadata
    log.debug(f"Extracting metadata: path={path.name}")
    meta = _extract_metadata(reader, path)
    
    total_chars = sum(len(p) for p in pages_text)
    log.debug(
        f"PyPDF2 extraction complete: path={path.name} pages={len(pages_text)} "
        f"total_chars={total_chars} avg_chars_per_page={total_chars / max(len(pages_text), 1):.1f}"
    )

    return PDFReadResult(
        path=str(path),
        encrypted=encrypted,
        num_pages=len(pages_text),
        meta=meta,
        pages=pages_text,
    )


def _pdfminer_extract(path: Path, password: Optional[str]) -> List[str]:
    """
    Fallback extractor using pdfminer.six when PyPDF2 produces poor results.
    
    Args:
        path: Path to the PDF file
        password: Optional password for encrypted PDFs
        
    Returns:
        List of extracted text, one string per page
        
    Raises:
        PDFSyntaxError: If PDF structure is malformed
        Exception: For other extraction errors
    """
    log.debug(f"Starting pdfminer extraction: path={path.name}")
    
    try:
        pages_text: List[str] = []
        page_count = 0
        
        for page_layout in extract_pages(str(path), password=password or ""):
            page_count += 1
            chunks: List[str] = []
            
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    chunks.append(element.get_text())
            
            page_text = "".join(chunks).strip()
            pages_text.append(page_text)
            log.debug(f"pdfminer extracted page {page_count}: chars={len(page_text)}")
        
        # Last resort: try whole-document extraction if no pages found
        if not pages_text:
            log.warning(f"pdfminer page extraction yielded no pages, trying whole-doc extraction: path={path.name}")
            text = pdfminer_extract_text(str(path), password=password or "") or ""
            pages_text = [text] if text else [""]
            
        total_chars = sum(len(p) for p in pages_text)
        log.debug(
            f"pdfminer extraction complete: path={path.name} pages={len(pages_text)} "
            f"total_chars={total_chars}"
        )
        
        return pages_text
        
    except PDFSyntaxError as e:
        log.error(f"pdfminer syntax error - PDF may be malformed: path={path.name} error={e!r}")
        raise
    except Exception as e:
        log.error(f"pdfminer extraction failed: path={path.name} error={type(e).__name__}: {e}")
        raise


def _needs_fallback(pages: List[str]) -> bool:
    """
    Determine if pdfminer fallback extraction is needed.
    
    Checks if PyPDF2 extraction produced insufficient text (below MIN_TEXT_LEN_PER_PAGE).
    
    Args:
        pages: List of extracted text from PyPDF2
        
    Returns:
        True if fallback is needed, False otherwise
    """
    if not pages:
        log.debug("Fallback needed: no pages extracted")
        return True
        
    total_chars = sum(len(p) for p in pages)
    avg_chars_per_page = total_chars / max(len(pages), 1)
    
    needs_fallback = avg_chars_per_page < MIN_TEXT_LEN_PER_PAGE
    
    if needs_fallback:
        log.debug(
            f"Fallback needed: avg {avg_chars_per_page:.1f} chars/page < {MIN_TEXT_LEN_PER_PAGE} threshold"
        )
    
    return needs_fallback


def _extract_metadata(reader: PdfReader, path: Path) -> PDFMeta:
    """
    Extract metadata from PDF reader object.
    
    Args:
        reader: PyPDF2 PdfReader instance
        path: Path to the PDF file (for logging)
        
    Returns:
        PDFMeta object with extracted metadata fields
    """
    info = reader.metadata or {}
    
    # PyPDF2 metadata can be accessed via properties or dict keys
    meta = PDFMeta(
        title=getattr(info, "title", None) or _safe_meta(info, "/Title"),
        author=getattr(info, "author", None) or _safe_meta(info, "/Author"),
        subject=getattr(info, "subject", None) or _safe_meta(info, "/Subject"),
        producer=getattr(info, "producer", None) or _safe_meta(info, "/Producer"),
        creator=getattr(info, "creator", None) or _safe_meta(info, "/Creator"),
    )
    
    # Log metadata extraction results
    metadata_fields = [k for k, v in meta.__dict__.items() if v is not None]
    if metadata_fields:
        log.debug(f"Extracted metadata fields: {metadata_fields} from {path.name}")
    else:
        log.debug(f"No metadata found in PDF: {path.name}")
    
    return meta


def _safe_meta(info: Dict[str, Any] | Any, key: str) -> Optional[str]:
    """
    Safely extract metadata value from PyPDF2 metadata object.
    
    Handles both dict-like and object-like metadata structures.
    
    Args:
        info: Metadata object/dict from PyPDF2
        key: Metadata key to extract
        
    Returns:
        Metadata value as string, or None if not found/error
    """
    try:
        if isinstance(info, dict):
            val = info.get(key)
            return str(val).strip() if val else None
            
        # PyPDF2 metadata object with .get() method
        if hasattr(info, "get"):
            val = info.get(key, None)
            return str(val).strip() if val else None
            
        return None
        
    except Exception as e:
        log.debug(f"Failed to extract metadata key '{key}': {e}")
        return None


def read_pdf(path: str | Path, password: Optional[str] = None) -> PDFReadResult:
    """
    Public API to read and extract text from a PDF file.
    
    Automatically handles:
    - Encrypted PDFs (with optional password)
    - Multiple extraction strategies (PyPDF2 → pdfminer fallback)
    - Metadata extraction
    - Malformed or partially readable PDFs
    
    Args:
        path: Path to the PDF file (string or Path object)
        password: Optional password for encrypted PDFs
        
    Returns:
        PDFReadResult containing extracted text, metadata, and file info
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        pypdf_errors.FileNotDecryptedError: If PDF is encrypted and password is wrong/missing
        pypdf_errors.PdfReadError: If PDF is malformed or unreadable
        PDFSyntaxError: If PDF structure is invalid
        Exception: For other unexpected errors
        
    Example:
        >>> result = read_pdf("statement.pdf", password="secret123")
        >>> print(f"Extracted {result.num_pages} pages")
        >>> print(f"Title: {result.meta.title}")
        >>> for page_text in result.pages:
        ...     print(page_text[:100])
    """
    start_time = time.time()
    pdf_path = Path(path).resolve()
    
    # Validate file exists
    if not pdf_path.exists():
        error_msg = f"PDF file not found: {pdf_path}"
        log.error(error_msg)
        raise FileNotFoundError(error_msg)
        
    if not pdf_path.is_file():
        error_msg = f"Path is not a file: {pdf_path}"
        log.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    log.info(
        f"Starting PDF extraction: path={pdf_path.name} "
        f"size={file_size_mb:.2f}MB password_provided={bool(password)}"
    )
    
    try:
        # Primary extraction with PyPDF2
        primary = _pypdf2_extract(pdf_path, password)
        
        # Check if fallback to pdfminer is needed
        if _needs_fallback(primary.pages):
            log.warning(
                f"PyPDF2 extraction insufficient (avg chars/page < {MIN_TEXT_LEN_PER_PAGE}). "
                f"Attempting pdfminer fallback: path={pdf_path.name}"
            )
            
            try:
                fallback_pages = _pdfminer_extract(pdf_path, password)
                result = PDFReadResult(
                    path=str(pdf_path),
                    encrypted=primary.encrypted,
                    num_pages=len(fallback_pages),
                    meta=primary.meta,  # Keep PyPDF2 metadata
                    pages=fallback_pages,
                )
                
                elapsed = time.time() - start_time
                total_chars = sum(len(p) for p in result.pages)
                log.info(
                    f"PDF extraction complete (pdfminer): path={pdf_path.name} "
                    f"pages={result.num_pages} total_chars={total_chars} "
                    f"elapsed={elapsed:.2f}s"
                )
                return result
                
            except Exception as e:
                # If pdfminer also fails, log but return primary result anyway
                log.error(
                    f"pdfminer fallback failed, using PyPDF2 result: "
                    f"path={pdf_path.name} error={type(e).__name__}: {e}"
                )
                # Fall through to return primary result
        
        # Return PyPDF2 result
        elapsed = time.time() - start_time
        total_chars = sum(len(p) for p in primary.pages)
        log.info(
            f"PDF extraction complete (PyPDF2): path={pdf_path.name} "
            f"pages={primary.num_pages} total_chars={total_chars} "
            f"elapsed={elapsed:.2f}s"
        )
        return primary
        
    except (pypdf_errors.FileNotDecryptedError, 
            pypdf_errors.WrongPasswordError,
            pypdf_errors.PdfReadError,
            PDFSyntaxError) as e:
        # Re-raise expected PDF errors with context
        elapsed = time.time() - start_time
        log.error(
            f"PDF extraction failed: path={pdf_path.name} "
            f"error={type(e).__name__}: {e} elapsed={elapsed:.2f}s"
        )
        raise
        
    except Exception as e:
        # Log unexpected errors with full context
        elapsed = time.time() - start_time
        log.error(
            f"Unexpected error during PDF extraction: path={pdf_path.name} "
            f"error={type(e).__name__}: {e} elapsed={elapsed:.2f}s",
            exc_info=True
        )
        raise
