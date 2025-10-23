"""Intent classification models and schemas."""
from __future__ import annotations
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import date


class IntentFilters(BaseModel):
    """Filters extracted from user query."""
    accountNo: Optional[str] = None
    dateFrom: Optional[str] = None
    dateTo: Optional[str] = None
    counterparty: Optional[str] = None
    minAmount: Optional[float] = None
    maxAmount: Optional[float] = None


class IntentClassification(BaseModel):
    """Intent classification result from LLM."""
    
    intent: Literal[
        "aggregate",
        "text_qa",
        "aggregate_filtered_by_text",
        "listing",
        "trend",
        "provenance"
    ] = Field(..., description="The classified intent type")
    
    filters: IntentFilters = Field(
        default_factory=IntentFilters,
        description="Extracted filters from query"
    )
    
    metrics: List[str] = Field(
        default_factory=list,
        description="Metrics to compute: sum_income, sum_expense, net, count, avg, etc."
    )
    
    granularity: Literal["daily", "weekly", "monthly"] = Field(
        default="monthly",
        description="Time granularity for trends"
    )
    
    needsTable: bool = Field(
        default=False,
        description="Whether to display results as a table"
    )
    
    answerStyle: Literal["concise", "detailed"] = Field(
        default="concise",
        description="Preferred answer style"
    )
    
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0"
    )
    
    needsClarification: bool = Field(
        default=False,
        description="Whether the query needs clarification"
    )
    
    clarifyQuestion: Optional[str] = Field(
        default=None,
        description="Question to ask user for clarification"
    )
    
    provenance: bool = Field(
        default=False,
        description="Whether to include source citations"
    )
    
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief reasoning for classification (optional)"
    )


class IntentResponse(BaseModel):
    """Wrapper for intent classification response."""
    
    query: str = Field(..., description="Original user query")
    classification: IntentClassification = Field(..., description="Intent classification")
    timestamp: str = Field(..., description="Timestamp of classification")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


# Conversation context models for clarification flow

class ConversationTurn(BaseModel):
    """A single turn in the conversation."""
    
    type: Literal[
        "query",
        "clarification_request",
        "clarification_response",
        "confirmation",
        "system_message"
    ] = Field(..., description="Type of conversation turn")
    
    text: str = Field(..., description="Text content of the turn")
    
    timestamp: str = Field(..., description="ISO-8601 timestamp")
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the turn"
    )


class ConversationContext(BaseModel):
    """Full conversation context for intent classification."""
    
    turns: List[ConversationTurn] = Field(
        default_factory=list,
        description="List of conversation turns"
    )
    
    original_query: str = Field(..., description="The original user query")
    
    cumulative_query: str = Field(
        ...,
        description="Original query plus all clarifications combined"
    )
    
    iteration_count: int = Field(
        default=0,
        description="Number of clarification iterations"
    )
    
    def add_turn(self, turn_type: str, text: str, metadata: Optional[Dict] = None) -> None:
        """Add a turn to the conversation."""
        from datetime import datetime, timezone
        
        turn = ConversationTurn(
            type=turn_type,  # type: ignore
            text=text,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {}
        )
        self.turns.append(turn)
    
    def get_cumulative_query(self) -> str:
        """Build cumulative query from all relevant turns."""
        parts = [self.original_query]
        
        for turn in self.turns:
            if turn.type in ["clarification_response"]:
                parts.append(turn.text)
        
        return " ".join(parts)
    
    def to_prompt_context(self) -> str:
        """Format conversation context for LLM prompt."""
        if not self.turns:
            return ""
        
        lines = ["### Conversation History:"]
        for turn in self.turns:
            if turn.type == "query":
                lines.append(f"User asked: {turn.text}")
            elif turn.type == "clarification_request":
                lines.append(f"System asked: {turn.text}")
            elif turn.type == "clarification_response":
                lines.append(f"User clarified: {turn.text}")
            elif turn.type == "confirmation":
                lines.append(f"User confirmed: {turn.text}")
        
        return "\n".join(lines)

