from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

from PyPDF2 import PdfReader, errors as pypdf_errors
from pdfminer.high_level import extract_text as pdfminer_extract_text, extract_pages
from pdfminer.layout import LTTextContainer
from pdfminer.pdfparser import PDFSyntaxError

from core.logger import get_logger

log = get_logger("pdf_reader")


@dataclass(frozen=True)
class PDFMeta:
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    producer: Optional[str]
    creator: Optional[str]


@dataclass(frozen=True)
class PDFReadResult:
    path: str
    encrypted: bool
    num_pages: int
    meta: PDFMeta
    pages: List[str]  # one string per page (after best-effort extraction)


MIN_TEXT_LEN_PER_PAGE = 20  # heuristic: if PyPDF2 gives too little, fallback to pdfminer


def _pypdf2_extract(path: Path, password: Optional[str]) -> PDFReadResult:
    """
    Primary, fast extractor. Decrypts if needed and uses PyPDF2's extract_text().
    """
    try:
        reader = PdfReader(str(path))
    except pypdf_errors.PdfReadError as e:
        log.error(f"PyPDF2 failed to open PDF: path={path} err={e!r}")
        raise

    encrypted = bool(reader.is_encrypted)
    if encrypted:
        trial_passwords = [password] if password else [""]
        for pwd in trial_passwords:
            try:
                ok = reader.decrypt(pwd)
                if ok == 0 or ok is False:
                    raise pypdf_errors.WrongPasswordError("Incorrect PDF password.")
                break
            except (pypdf_errors.WrongPasswordError, pypdf_errors.FileNotDecryptedError) as e:
                log.warning(f"PyPDF2 decryption failed: path={path} reason={type(e).__name__}")
                continue
        else:
            raise pypdf_errors.FileNotDecryptedError("PDF is encrypted but no password was provided.")

    pages_text: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as e:  # PyPDF2 can throw for malformed pages
            log.warning(f"PyPDF2 extract_text failed on page {i}: {e!r}")
            txt = ""
        pages_text.append(txt)

    info = reader.metadata or {}
    meta = PDFMeta(
        title=getattr(info, "title", None) or _safe_meta(info, "/Title"),
        author=getattr(info, "author", None) or _safe_meta(info, "/Author"),
        subject=getattr(info, "subject", None) or _safe_meta(info, "/Subject"),
        producer=getattr(info, "producer", None) or _safe_meta(info, "/Producer"),
        creator=getattr(info, "creator", None) or _safe_meta(info, "/Creator"),
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
    Fallback extractor using pdfminer.six. Returns per-page texts to match PyPDF2 shape.
    """
    try:
        pages_text: List[str] = []
        for page_layout in extract_pages(str(path), password=password):
            chunks: List[str] = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    chunks.append(element.get_text())
            pages_text.append("".join(chunks).strip())
        # As a last resort, try whole-doc extract if pages_text is empty
        if not pages_text:
            text = pdfminer_extract_text(str(path), password=password) or ""
            pages_text = [text] if text else [""]
        return pages_text
    except PDFSyntaxError as e:
        log.error(f"pdfminer PDFSyntaxError: path={path} err={e!r}")
        raise
    except Exception as e:
        log.error(f"pdfminer failed: path={path} err={e!r}")
        raise


def _needs_fallback(pages: List[str]) -> bool:
    """
    Decide if pdfminer fallback is needed (too little text extracted).
    """
    if not pages:
        return True
    avg_len = (sum(len(p) for p in pages) / max(len(pages), 1))
    return avg_len < MIN_TEXT_LEN_PER_PAGE


def _safe_meta(info: Dict[str, Any] | Any, key: str) -> Optional[str]:
    try:
        if isinstance(info, dict):
            val = info.get(key)
            return str(val) if val else None
        # PyPDF2 metadata behaves like a dict-like object
        val = info.get(key, None) if hasattr(info, "get") else None
        return str(val) if val else None
    except Exception:
        return None


def read_pdf(path: str | Path, password: Optional[str] = None) -> PDFReadResult:
    """
    Public API: read a PDF from disk, optionally decrypt with password,
    return structured text and metadata.

    Raises:
        - WrongPasswordError / FileNotDecryptedError if password wrong or missing for encrypted PDF
        - PdfReadError / PDFSyntaxError for malformed PDFs
        - Generic Exception for unexpected issues
    """
    pdf_path = Path(path)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    log.info(f"Reading PDF: path={pdf_path} password_provided={bool(password)}")
    primary = _pypdf2_extract(pdf_path, password)

    if _needs_fallback(primary.pages):
        log.warning(
            f"PyPDF2 extraction sparse (avg chars/page < {MIN_TEXT_LEN_PER_PAGE}). "
            "Falling back to pdfminer for better text extraction."
        )
        fallback_pages = _pdfminer_extract(pdf_path, password)
        result = PDFReadResult(
            path=primary.path,
            encrypted=primary.encrypted,
            num_pages=len(fallback_pages),
            meta=primary.meta,  # keep PyPDF2 metadata (usually adequate)
            pages=fallback_pages,
        )
        log.info(f"pdfminer fallback used: pages={result.num_pages} total_chars={sum(len(p) for p in result.pages)}")
        return result

    log.info(f"PyPDF2 extraction used: pages={primary.num_pages} total_chars={sum(len(p) for p in primary.pages)}")
    return primary
