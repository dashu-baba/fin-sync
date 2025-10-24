from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date

class StatementItem(BaseModel):
    statementDate: date
    statementAmount: float = Field(gt=0, description="Absolute amount; sign captured by statementType")
    statementType: Literal["credit", "debit"]
    statementDescription: str = Field(default="")
    statementBalance: float
    statementNotes: str | None = None
    statementPage: int | None = None

    model_config = {
        "extra": "forbid",
    }

    @field_validator("statementDescription", mode="before")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else ""

    @field_validator("statementNotes", mode="before")
    @classmethod
    def _strip_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None


class Page(BaseModel):
    pageNumber: int
    statements: list[StatementItem]


    @field_validator("statements", mode="before")
    @classmethod
    def _ensure_list(cls, value):
        if value is None:
            return []
        return value

    model_config = {
        "extra": "forbid",
    }

class ParsedStatement(BaseModel):
    accountName: str | None = None
    accountNo: str
    accountType: str | None = None
    statementFrom: date
    statementTo: date
    bankName: str | None = None
    pages: list[Page]

    model_config = {
        "extra": "forbid",
    }

    @field_validator("accountName", "bankName", "accountType", mode="before")
    @classmethod
    def _strip_strings(cls, value):
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    @field_validator("accountNo", mode="before")
    @classmethod
    def _normalize_and_validate_account_no(cls, value) -> str:
        if value is None:
            raise ValueError("accountNo is required")
        s = str(value).strip()
        # Keep digits only (ignore spaces, hyphens)
        digits_only = "".join(ch for ch in s if ch.isdigit())
        if not digits_only:
            raise ValueError("accountNo must contain digits")
        if len(digits_only) < 6 or len(digits_only) > 20:
            raise ValueError("accountNo must be between 6 and 20 digits")
        return digits_only

    @model_validator(mode="after")
    def _validate_dates_and_items(self) -> "ParsedStatement":
        if self.statementFrom > self.statementTo:
            raise ValueError("statementFrom must be on or before statementTo")
        for page in self.pages:
            for item in page.statements:
                if item.statementDate < self.statementFrom or item.statementDate > self.statementTo:
                    raise ValueError("statementDate must be within the provided statementFrom and statementTo range")
        return self

