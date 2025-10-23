from __future__ import annotations
import json
import time
import csv
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime

from pydantic import ValidationError
from core.logger import get_logger
from models.schema import ParsedStatement, StatementItem
from ingestion.pdf_reader import read_pdf

# Vertex AI
from google.cloud import aiplatform
from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel

log = get_logger("parser_vertex")

# Configuration constants
DEFAULT_VERTEX_MODEL = "gemini-2.5-pro"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_RETRIES = 2
MAX_OUTPUT_TOKENS = 16384
EXPECTED_CSV_COLUMNS = ["date", "amount", "type", "description", "balance"]
SUPPORTED_DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"]

SYSTEM_INSTRUCTIONS = (
    "You are a finance statement extraction engine. "
    "Extract fields in strict JSON per the provided schema. "
    "Dates must be ISO (YYYY-MM-DD). Amounts are numbers. "
    "Extract page number"
    "Only return JSON, no explanations."
)

PROMPT_TEMPLATE = """
Parse the following bank statement text into this JSON schema:

{{
  "accountName": string,
  "accountNo": string,
  "accountType": string | null,
  "statementFrom": "YYYY-MM-DD",
  "statementTo": "YYYY-MM-DD",
  "bankName": string,
  "pages": [
    {{
        "pageNumber": number,
        "statements": [
            {{
            "statementDate": "YYYY-MM-DD",
            "statementAmount": number,
            "statementType": "credit" | "debit",
            "statementDescription": string,
            "statementBalance": number,
            "statementNotes": string | null
            "statementPage": number | null
            }}
        ]
    }}
  ]
  
}}

Constraints:
- Use detected currency amounts as numbers (no symbols).
- Infer accountType if present; otherwise null.
- Do NOT hallucinate: if unknown, use null or empty string.
- Output ONLY valid JSON.
- Each page should be a separate object in the "pages" array.
- Each page should have a "pageNumber" property.
- If a descriptiption move to separate page, consider it part of the previous page.

TEXT (may include multiple pages):
---
{statement_text}
---
"""

def _init_vertex(project_id: str, location: str, model_name: str = DEFAULT_VERTEX_MODEL) -> GenerativeModel:
    """
    Initialize Vertex AI and create a GenerativeModel instance.
    
    Args:
        project_id: GCP project ID
        location: GCP region (e.g., 'us-central1')
        model_name: Vertex AI model name (default: gemini-1.5-pro)
        
    Returns:
        GenerativeModel instance ready for content generation
        
    Raises:
        Exception: If Vertex AI initialization fails
    """
    log.debug(f"Initializing Vertex AI: project={project_id} location={location} model={model_name}")
    
    try:
        vertex_init(project=project_id, location=location)
        model = GenerativeModel(model_name)
        log.info(f"Vertex AI initialized successfully: model={model_name}")
        return model
        
    except Exception as e:
        log.error(
            f"Failed to initialize Vertex AI: project={project_id} location={location} "
            f"model={model_name} error={type(e).__name__}: {e}",
            exc_info=True
        )
        raise


def _invoke_llm(
    model: GenerativeModel, 
    text: str, 
    temperature: float = DEFAULT_TEMPERATURE, 
    retries: int = DEFAULT_MAX_RETRIES
) -> str:
    """
    Invoke Vertex AI LLM to extract structured data from bank statement text.
    
    Args:
        model: Initialized GenerativeModel instance
        text: Bank statement text to parse
        temperature: Generation temperature (0.0-1.0, lower = more deterministic)
        retries: Number of retry attempts on failure
        
    Returns:
        Generated JSON string response from the model
        
    Raises:
        RuntimeError: If all retry attempts fail
    """
    text_length = len(text)
    log.debug(
        f"Invoking Vertex AI LLM: text_length={text_length} chars "
        f"temperature={temperature} max_retries={retries}"
    )
    
    last_err = None
    start_time = time.time()
    
    for attempt in range(retries + 1):
        attempt_start = time.time()
        
        try:
            log.debug(f"LLM generation attempt {attempt + 1}/{retries + 1}")
            
            resp = model.generate_content(
                contents=f"{SYSTEM_INSTRUCTIONS}\n\n{PROMPT_TEMPLATE.format(statement_text=text)}",
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "response_mime_type": "application/json",
                },
                safety_settings=None,
            )
            
            attempt_elapsed = time.time() - attempt_start
            response_text = resp.text.strip()
            response_length = len(response_text)
            
            log.info(
                f"LLM generation successful: attempt={attempt + 1} "
                f"response_length={response_length} chars elapsed={attempt_elapsed:.2f}s"
            )
            log.debug(f"LLM response preview: {response_text[:200]}...")
            
            return response_text
            
        except Exception as e:
            last_err = e
            attempt_elapsed = time.time() - attempt_start
            log.warning(
                f"LLM generation failed (attempt {attempt + 1}/{retries + 1}): "
                f"error={type(e).__name__}: {e} elapsed={attempt_elapsed:.2f}s"
            )
            
            # Don't sleep after the last attempt
            if attempt < retries:
                retry_delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                log.debug(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    
    total_elapsed = time.time() - start_time
    error_msg = f"Vertex AI generation failed after {retries + 1} attempts: {last_err!r}"
    log.error(f"{error_msg} total_elapsed={total_elapsed:.2f}s")
    raise RuntimeError(error_msg)


def _unwrap_json_fence(payload: str) -> str:
    """
    Remove markdown code fences and language tags from JSON response.
    
    LLMs sometimes wrap JSON in markdown code blocks like:
    ```json
    {...}
    ```
    
    Args:
        payload: Raw LLM response string
        
    Returns:
        Cleaned JSON string without markdown artifacts
    """
    p = payload.strip()
    original_length = len(p)
    
    if p.startswith("```"):
        log.debug("Removing markdown code fences from LLM response")
        
        # Remove starting fence line
        lines = p.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        
        # Remove trailing fence if present
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        
        p = "\n".join(lines).strip()
        
        # Also strip leading json/language tags
        if p.lower().startswith("json"):
            p = p[4:].strip()
            log.debug("Removed 'json' language tag from response")
    
    cleaned_length = len(p)
    if cleaned_length != original_length:
        log.debug(
            f"Unwrapped JSON: original_length={original_length} "
            f"cleaned_length={cleaned_length} removed={original_length - cleaned_length} chars"
        )
    
    return p


def _salvage_truncated_json(payload: str) -> Optional[str]:
    """
    Attempt to salvage truncated JSON by finding the last balanced brace/bracket position.
    
    This is useful when LLM responses are cut off due to token limits.
    Tracks brace/bracket balance while respecting string boundaries.
    
    Args:
        payload: Potentially truncated JSON string
        
    Returns:
        Valid JSON string if salvageable, None otherwise
    """
    log.debug("Attempting to salvage truncated JSON")
    s = payload
    
    # Find the first '{' occurrence
    if "{" not in s:
        log.debug("No opening brace found, cannot salvage")
        return None
    
    start = s.find("{")
    log.debug(f"JSON starts at position {start}")
    
    # Track brace/bracket balance while respecting string boundaries
    balance = 0
    last_balanced_idx = -1
    in_string = False
    escape = False
    
    for i, ch in enumerate(s[start:], start):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        else:
            if ch == '"':
                in_string = True
            elif ch == "{" or ch == "[":
                balance += 1
            elif ch == "}" or ch == "]":
                balance -= 1
                if balance == 0:
                    last_balanced_idx = i
    
    if last_balanced_idx != -1:
        candidate = s[start:last_balanced_idx + 1]
        candidate_length = len(candidate)
        
        log.debug(
            f"Found balanced JSON candidate: length={candidate_length} "
            f"end_position={last_balanced_idx}"
        )
        
        try:
            json.loads(candidate)
            log.info(f"Successfully salvaged truncated JSON: length={candidate_length} chars")
            return candidate
        except Exception as e:
            log.debug(f"Balanced candidate is not valid JSON: {type(e).__name__}: {e}")
            return None
    
    log.debug("Could not find balanced JSON structure")
    return None


def _validate_and_fix_json(payload: str) -> ParsedStatement:
    """
    Clean, parse, and validate LLM output against ParsedStatement schema.
    
    Performs multiple recovery strategies:
    1. Remove markdown code fences
    2. Parse JSON
    3. Attempt to salvage truncated JSON if parsing fails
    4. Validate against Pydantic schema
    
    Args:
        payload: Raw LLM response string
        
    Returns:
        Validated ParsedStatement object
        
    Raises:
        json.JSONDecodeError: If JSON is malformed and cannot be salvaged
        ValidationError: If data doesn't match ParsedStatement schema
    """
    log.debug(f"Validating LLM output: payload_length={len(payload)} chars")
    
    # Step 1: Remove markdown artifacts
    cleaned = _unwrap_json_fence(payload)
    
    # Step 2: Parse JSON with fallback to salvage
    data = None
    try:
        data = json.loads(cleaned)
        log.debug("JSON parsed successfully")
        
    except json.JSONDecodeError as e:
        log.warning(
            f"JSON decode error at position {e.pos}: {e.msg} | "
            f"payload_preview={payload[:200]}..."
        )
        
        # Attempt salvage
        salvaged = _salvage_truncated_json(cleaned)
        if not salvaged:
            log.error("Failed to salvage truncated JSON, cannot recover")
            raise
        
        log.info("Using salvaged JSON after truncation recovery")
        data = json.loads(salvaged)
    
    # Step 3: Validate against Pydantic schema
    try:
        parsed = ParsedStatement.model_validate(data)
        
        # Log summary of parsed data - count statements from all pages
        statement_count = sum(len(page.statements) for page in parsed.pages)
        log.info(
            f"Statement validated successfully: account={parsed.accountName} "
            f"account_no={parsed.accountNo} bank={parsed.bankName} "
            f"period={parsed.statementFrom} to {parsed.statementTo} "
            f"transactions={statement_count}"
        )
        
        return parsed
        
    except ValidationError as e:
        error_count = len(e.errors())
        log.error(
            f"Pydantic validation failed: {error_count} errors | "
            f"errors={e.json()}"
        )
        raise


def parse_pdf_to_json(
    pdf_path: Union[str, Path],
    password: Optional[str],
    *,
    gcp_project: str,
    gcp_location: str,
    vertex_model: str = DEFAULT_VERTEX_MODEL,
) -> ParsedStatement:
    """
    Complete pipeline: Extract text from PDF and parse to structured bank statement.
    
    This is the main public API for PDF-based statement parsing. It:
    1. Reads and decrypts PDF (if needed)
    2. Extracts text from all pages
    3. Calls Vertex AI LLM for structured extraction
    4. Validates and returns ParsedStatement
    
    Args:
        pdf_path: Path to the PDF bank statement file
        password: Optional password for encrypted PDFs
        gcp_project: GCP project ID for Vertex AI
        gcp_location: GCP region (e.g., 'us-central1')
        vertex_model: Vertex AI model name (default: gemini-1.5-pro)
        
    Returns:
        Validated ParsedStatement with all transactions
        
    Raises:
        FileNotFoundError: If PDF doesn't exist
        ValueError: If PDF contains no extractable text
        RuntimeError: If Vertex AI generation fails
        ValidationError: If LLM output doesn't match schema
        
    Example:
        >>> statement = parse_pdf_to_json(
        ...     "statement.pdf",
        ...     password="secret",
        ...     gcp_project="my-project",
        ...     gcp_location="us-central1"
        ... )
        >>> print(f"Found {len(statement.statements)} transactions")
    """
    start_time = time.time()
    pdf_path_obj = Path(pdf_path)
    
    log.info(
        f"Starting PDF statement parsing: path={pdf_path_obj.name} "
        f"model={vertex_model} project={gcp_project}"
    )
    
    try:
        # Step 1: Extract text from PDF
        pdf = read_pdf(pdf_path, password=password)
        text = "\n\n".join(pdf.pages).strip()
        
        if not text:
            error_msg = f"No extractable text found in PDF: {pdf_path_obj.name}"
            log.error(error_msg)
            raise ValueError(error_msg)
        
        text_length = len(text)
        log.info(
            f"PDF text extracted: path={pdf_path_obj.name} pages={pdf.num_pages} "
            f"encrypted={pdf.encrypted} text_length={text_length} chars"
        )
        
        # Step 2: Initialize Vertex AI
        model = _init_vertex(gcp_project, gcp_location, vertex_model)
        
        # Step 3: Generate structured output
        raw = _invoke_llm(model, text)
        
        # Step 4: Validate and parse
        parsed = _validate_and_fix_json(raw)
        
        # Success logging
        elapsed = time.time() - start_time
        transaction_count = sum(len(page.statements) for page in parsed.pages)
        log.info(
            f"PDF statement parsing complete: path={pdf_path_obj.name} "
            f"account={parsed.accountName} bank={parsed.bankName} "
            f"period={parsed.statementFrom} to {parsed.statementTo} "
            f"transactions={transaction_count} elapsed={elapsed:.2f}s"
        )
        
        return parsed
        
    except (FileNotFoundError, ValueError, RuntimeError, ValidationError) as e:
        # Re-raise expected errors with context
        elapsed = time.time() - start_time
        log.error(
            f"PDF statement parsing failed: path={pdf_path_obj.name} "
            f"error={type(e).__name__}: {e} elapsed={elapsed:.2f}s"
        )
        raise
        
    except Exception as e:
        # Log unexpected errors with full traceback
        elapsed = time.time() - start_time
        log.error(
            f"Unexpected error during PDF parsing: path={pdf_path_obj.name} "
            f"error={type(e).__name__}: {e} elapsed={elapsed:.2f}s",
            exc_info=True
        )
        raise

# --- CSV path (optional simple parser) ---


def _normalize_account_no(value: Union[str, int]) -> str:
    """
    Normalize account number by extracting only digits.
    
    Args:
        value: Account number as string or integer
        
    Returns:
        String containing only digits from the input
        
    Example:
        >>> _normalize_account_no("ACC-12345-67")
        "1234567"
        >>> _normalize_account_no(123456)
        "123456"
    """
    s = str(value).strip()
    digits_only = "".join(ch for ch in s if ch.isdigit())
    
    log.debug(f"Normalized account number: original='{s}' normalized='{digits_only}'")
    
    return digits_only


def parse_csv_to_json(
    csv_path: Union[str, Path],
    *,
    account_name: str = "",
    account_no: Union[str, int] = "",
    account_type: Optional[str] = None,
    bank_name: str = "",
) -> ParsedStatement:
    """
    Parse CSV bank statement file to structured ParsedStatement.
    
    Expected CSV columns: date, amount, type, description, balance
    Optional column: notes
    
    Args:
        csv_path: Path to CSV file
        account_name: Account holder name
        account_no: Account number (will be normalized to digits only)
        account_type: Account type (e.g., "checking", "savings")
        bank_name: Bank name
        
    Returns:
        Validated ParsedStatement with all transactions
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV is empty or has invalid data
        KeyError: If required columns are missing
        
    Example:
        >>> statement = parse_csv_to_json(
        ...     "transactions.csv",
        ...     account_name="John Doe",
        ...     account_no="1234567890",
        ...     bank_name="Example Bank"
        ... )
    """
    start_time = time.time()
    csv_path_obj = Path(csv_path)
    
    log.info(
        f"Starting CSV statement parsing: path={csv_path_obj.name} "
        f"account={account_name} bank={bank_name}"
    )
    
    # Validate file exists
    if not csv_path_obj.exists():
        error_msg = f"CSV file not found: {csv_path_obj}"
        log.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        items: List[StatementItem] = []
        dates: List[datetime] = []
        row_count = 0
        error_count = 0

        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            # Validate headers
            if not reader.fieldnames:
                error_msg = f"CSV file has no headers: {csv_path_obj.name}"
                log.error(error_msg)
                raise ValueError(error_msg)
            
            missing_cols = set(EXPECTED_CSV_COLUMNS) - set(reader.fieldnames)
            if missing_cols:
                log.warning(
                    f"CSV missing expected columns: {missing_cols} | "
                    f"found_columns={list(reader.fieldnames)}"
                )
            
            log.debug(f"CSV headers: {list(reader.fieldnames)}")
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                row_count += 1
                
                try:
                    d = _parse_date(row.get("date"))
                    amt = float(row.get("amount", "0") or 0)
                    typ = (row.get("type", "") or "").strip().lower()
                    desc = row.get("description", "") or ""
                    bal = float(row.get("balance", "0") or 0)
                    notes = row.get("notes") if "notes" in row else None

                    item = StatementItem(
                        statementDate=d.date(),
                        statementAmount=amt,
                        statementType="credit" if typ == "credit" else "debit",
                        statementDescription=desc,
                        statementBalance=bal,
                        statementNotes=notes,
                    )
                    items.append(item)
                    dates.append(d)
                    
                    log.debug(
                        f"Parsed CSV row {row_num}: date={d.date()} "
                        f"amount={amt} type={typ} balance={bal}"
                    )
                    
                except Exception as e:
                    error_count += 1
                    log.warning(
                        f"Failed to parse CSV row {row_num}: {type(e).__name__}: {e} | "
                        f"row_data={row}"
                    )
                    # Continue processing other rows

        if not items:
            error_msg = f"No valid rows parsed from CSV: {csv_path_obj.name} (total_rows={row_count})"
            log.error(error_msg)
            raise ValueError(error_msg)
        
        if error_count > 0:
            log.warning(
                f"CSV parsing completed with errors: parsed={len(items)} "
                f"errors={error_count} total={row_count}"
            )

        statement_from = min(dates).date()
        statement_to = max(dates).date()
        
        parsed = ParsedStatement(
            accountName=account_name or "",
            accountNo=_normalize_account_no(account_no) if account_no else "",
            accountType=account_type,
            statementFrom=statement_from,
            statementTo=statement_to,
            bankName=bank_name or "",
            statements=items,
        )
        
        elapsed = time.time() - start_time
        log.info(
            f"CSV statement parsing complete: path={csv_path_obj.name} "
            f"transactions={len(items)} period={statement_from} to {statement_to} "
            f"elapsed={elapsed:.2f}s"
        )
        
        return parsed
        
    except (FileNotFoundError, ValueError, KeyError) as e:
        elapsed = time.time() - start_time
        log.error(
            f"CSV parsing failed: path={csv_path_obj.name} "
            f"error={type(e).__name__}: {e} elapsed={elapsed:.2f}s"
        )
        raise
        
    except Exception as e:
        elapsed = time.time() - start_time
        log.error(
            f"Unexpected error during CSV parsing: path={csv_path_obj.name} "
            f"error={type(e).__name__}: {e} elapsed={elapsed:.2f}s",
            exc_info=True
        )
        raise


def _parse_date(s: Optional[str]) -> datetime:
    """
    Parse date string using multiple common formats.
    
    Supported formats:
    - ISO: YYYY-MM-DD (2024-03-15)
    - DD-MM-YYYY (15-03-2024)
    - MM/DD/YYYY (03/15/2024)
    - DD/MM/YYYY (15/03/2024)
    
    Args:
        s: Date string to parse
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If date is missing or format is not recognized
    """
    if not s:
        raise ValueError("Missing date in CSV row")
    
    date_str = s.strip()
    
    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            parsed = datetime.strptime(date_str, fmt)
            log.debug(f"Parsed date '{date_str}' using format '{fmt}' -> {parsed.date()}")
            return parsed
        except ValueError:
            continue
    
    # None of the formats worked
    error_msg = f"Unrecognized date format: '{date_str}' (supported: {SUPPORTED_DATE_FORMATS})"
    log.warning(error_msg)
    raise ValueError(error_msg)
