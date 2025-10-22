from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime

from pydantic import ValidationError
from core.logger import get_logger
from models.schema import ParsedStatement
from ingestion.pdf_reader import read_pdf

# Vertex AI
from google.cloud import aiplatform
from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel

log = get_logger("parser_vertex")

SYSTEM_INSTRUCTIONS = (
    "You are a finance statement extraction engine. "
    "Extract fields in strict JSON per the provided schema. "
    "Dates must be ISO (YYYY-MM-DD). Amounts are numbers. "
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
  "statements": [
    {{
      "statementDate": "YYYY-MM-DD",
      "statementAmount": number,
      "statementType": "credit" | "debit",
      "statementDescription": string,
      "statementBalance": number,
      "statementNotes": string | null
    }}
  ]
}}

Constraints:
- Use detected currency amounts as numbers (no symbols).
- Infer accountType if present; otherwise null.
- Do NOT hallucinate: if unknown, use null or empty string.
- Output ONLY valid JSON.

TEXT (may include multiple pages):
---
{statement_text}
---
"""

def _init_vertex(project_id: str, location: str, model_name: str = "gemini-2.5-pro") -> GenerativeModel:
    vertex_init(project=project_id, location=location)
    return GenerativeModel(model_name)


def _invoke_llm(model: GenerativeModel, text: str, temperature: float = 0.1, retries: int = 2) -> str:
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = model.generate_content(
                contents=f"{SYSTEM_INSTRUCTIONS}\n\n{PROMPT_TEMPLATE.format(statement_text=text)}",
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json",
                },
                safety_settings=None,
            )
            return resp.text.strip()
        except Exception as e:
            last_err = e
            log.warning(f"Vertex call failed (attempt {attempt+1}/{retries+1}): {e!r}")
    raise RuntimeError(f"Vertex AI generation failed after retries: {last_err!r}")


def _unwrap_json_fence(payload: str) -> str:
    p = payload.strip()
    if p.startswith("```"):
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
    return p


def _salvage_truncated_json(payload: str) -> Optional[str]:
    """
    Attempt to salvage truncated JSON by keeping content up to the last
    balanced brace/bracket position.
    """
    s = payload
    # Find the first '{' and last '}' occurrence
    if "{" not in s:
        return None
    start = s.find("{")
    # Track brace/bracket balance
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
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            return None
    return None


def _validate_and_fix_json(payload: str) -> ParsedStatement:
    """
    Ensure the LLM output is valid JSON and conforms to ParsedStatement.
    """
    cleaned = _unwrap_json_fence(payload)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error(f"JSON decode error: {e} | payload_head={payload[:200]}")
        salvaged = _salvage_truncated_json(cleaned)
        if not salvaged:
            raise
        data = json.loads(salvaged)
    try:
        return ParsedStatement.model_validate(data)
    except ValidationError as e:
        log.error(f"Pydantic validation error: {e.json()}")
        raise


def parse_pdf_to_json(
    pdf_path: Union[str, Path],
    password: Optional[str],
    *,
    gcp_project: str,
    gcp_location: str,
    vertex_model: str = "gemini-1.5-pro",
) -> ParsedStatement:
    """
    Read a PDF, extract text (with decryption if needed), call Vertex,
    and return a validated ParsedStatement.
    """
    pdf = read_pdf(pdf_path, password=password)
    text = "\n\n".join(pdf.pages).strip()
    if not text:
        raise ValueError(f"No extractable text found in PDF: {pdf_path}")

    log.info(f"Invoking Vertex for PDF: pages={pdf.num_pages} encrypted={pdf.encrypted}")
    model = _init_vertex(gcp_project, gcp_location, vertex_model)
    raw = _invoke_llm(model, text)
    parsed = _validate_and_fix_json(raw)
    log.info(f"Parsed statement: account={parsed.accountName} range={parsed.statementFrom}..{parsed.statementTo}")
    return parsed

# --- CSV path (optional simple parser) ---

import csv
from models.schema import StatementItem


def _normalize_account_no(value: Union[str, int]) -> str:
    s = str(value).strip()
    digits_only = "".join(ch for ch in s if ch.isdigit())
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
    Expect CSV with columns: date, amount, type(credit|debit), description, balance, notes?
    """
    items: List[StatementItem] = []
    dates: List[datetime] = []

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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

    if not items:
        raise ValueError(f"No rows parsed from CSV: {csv_path}")

    statement_from = min(dates).date()
    statement_to = max(dates).date()

    return ParsedStatement(
        accountName=account_name or "",
        accountNo=_normalize_account_no(account_no),
        accountType=account_type,
        statementFrom=statement_from,
        statementTo=statement_to,
        bankName=bank_name or "",
        statements=items,
    )


def _parse_date(s: Optional[str]) -> datetime:
    if not s:
        raise ValueError("Missing date in CSV row")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {s}")
