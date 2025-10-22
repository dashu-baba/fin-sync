from __future__ import annotations
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel
from datetime import date

class TransactionDoc(BaseModel):
    id: str                       # deterministic
    accountNo: int
    bankName: str
    accountName: Optional[str] = None
    type: Literal["credit","debit"]
    amount: float
    balance: Optional[float] = None
    description: str = ""
    category: Optional[str] = None
    currency: Optional[str] = None
    sourceStatementId: str
    sourceFile: Optional[str] = None
    timestamp: date               # txn date
    desc_vector: Optional[List[float]] = None

class StatementDoc(BaseModel):
    id: str                       # deterministic
    accountNo: int
    bankName: str
    accountName: Optional[str] = None
    statementFrom: date
    statementTo: date
    summary_text: str
    summary_vector: List[float]
    meta: Dict[str, Any] = {}
