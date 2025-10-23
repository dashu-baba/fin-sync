"""Parsing and indexing business logic service."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple

from core.config import config
from core.logger import get_logger
from core.utils import make_id
from ingestion import parse_pdf_to_json
from ingestion.parser_vertex import parse_csv_to_json
from elastic import embed_texts, start_transform, wait_for_first_checkpoint, ensure_transform_monthly
from elastic.indexer import ensure_statements_index, ensure_transactions_index, bulk_index

log = get_logger("ui/services/parse_service")


class ParseService:
    """Handles parsing and indexing business logic."""
    
    @staticmethod
    def validate_config() -> Tuple[bool, Optional[str]]:
        """
        Validate that necessary configuration is present.
        
        Returns:
            (is_valid, error_message)
        """
        gcp_project = config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
        if not gcp_project:
            return False, "GCP project is not configured."
        
        if not (os.getenv("ELASTIC_CLOUD_ENDPOINT") and os.getenv("ELASTIC_API_KEY")):
            return False, "Elastic Cloud credentials are not configured."
        
        return True, None
    
    @staticmethod
    def parse_file(
        file_path: str,
        file_ext: str,
        password: Optional[str] = None,
        gcp_project: Optional[str] = None,
        gcp_location: Optional[str] = None
    ) -> Optional[Any]:
        """
        Parse a single file (PDF or CSV) using Vertex AI.
        
        Returns:
            Parsed statement object or None if parsing failed.
        """
        gcp_project = gcp_project or config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
        gcp_location = gcp_location or config.gcp_location or os.getenv("GCP_LOCATION", "us-central1")
        
        try:
            if file_ext == "pdf":
                return parse_pdf_to_json(
                    file_path,
                    password,
                    gcp_project=gcp_project,
                    gcp_location=gcp_location,
                    vertex_model=config.vertex_model
                )
            else:
                return parse_csv_to_json(file_path)
        except Exception as e:
            log.error(f"Failed to parse {Path(file_path).name}: {e!r}")
            raise
    
    @staticmethod
    def create_statement_doc(
        parsed,
        source_file: str,
        summary_vector: List[float]
    ) -> Dict:
        """
        Create a statement document for indexing.
        
        Args:
            parsed: Parsed statement object
            source_file: Source filename
            summary_vector: Embedding vector for the summary
            
        Returns:
            Statement document dict
        """
        statement_id = make_id(
            str(parsed.accountNo),
            str(parsed.statementFrom),
            str(parsed.statementTo)
        )
        
        head_txn = "\n".join(
            f"{it.statementDate} {it.statementType} {it.statementAmount} {it.statementDescription}"
            for it in parsed.statements[:200]
        )
        
        summary_text = (
            f"Account: {parsed.accountName}\n"
            f"Bank: {parsed.bankName}\n"
            f"Range: {parsed.statementFrom}..{parsed.statementTo}\n"
            f"Transactions:\n{head_txn}"
        )
        
        return {
            "id": statement_id,
            "accountNo": str(parsed.accountNo),
            "bankName": parsed.bankName,
            "accountName": parsed.accountName,
            "statementFrom": str(parsed.statementFrom),
            "statementTo": str(parsed.statementTo),
            "summary_text": summary_text,
            "summary_vector": summary_vector,
            "meta": {"sourceFile": source_file},
        }
    
    @staticmethod
    def create_transaction_docs(
        parsed,
        statement_id: str,
        source_file: str,
        embed_descriptions: bool = False,
        gcp_project: Optional[str] = None,
        gcp_location: Optional[str] = None
    ) -> List[Dict]:
        """
        Create transaction documents for indexing.
        
        Args:
            parsed: Parsed statement object
            statement_id: Parent statement ID
            source_file: Source filename
            embed_descriptions: Whether to generate embeddings for descriptions
            gcp_project: GCP project ID
            gcp_location: GCP location
            
        Returns:
            List of transaction document dicts
        """
        gcp_project = gcp_project or config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
        gcp_location = gcp_location or config.gcp_location or os.getenv("GCP_LOCATION", "us-central1")
        
        tx_docs = []
        for i, txn in enumerate(parsed.statements):
            txn_id = make_id(
                str(parsed.accountNo),
                str(txn.statementDate),
                str(i),
                str(txn.statementAmount),
                txn.statementDescription or ""
            )
            
            vec = None
            if embed_descriptions:
                vec = embed_texts(
                    [txn.statementDescription or ""],
                    project_id=gcp_project,
                    location=gcp_location,
                    model_name=config.vertex_model_embed
                )[0]
            
            tx_doc = {
                "id": txn_id,
                "accountNo": str(parsed.accountNo),
                "bankName": parsed.bankName,
                "accountName": parsed.accountName,
                "type": txn.statementType,
                "amount": float(txn.statementAmount),
                "description": txn.statementDescription or "",
                "category": None,
                "currency": None,
                "sourceStatementId": statement_id,
                "sourceFile": source_file,
                "timestamp": str(txn.statementDate),
                "@timestamp": str(txn.statementDate),
            }
            
            # Add balance if present
            if txn.statementBalance is not None:
                tx_doc["balance"] = float(txn.statementBalance)
            
            # Add vector if generated
            if vec is not None:
                tx_doc["desc_vector"] = vec
            
            tx_docs.append(tx_doc)
        
        return tx_docs
    
    @staticmethod
    def index_documents(
        stmt_docs: List[Dict],
        txn_docs: List[Dict]
    ) -> None:
        """
        Index statement and transaction documents to Elasticsearch.
        
        Args:
            stmt_docs: Statement documents
            txn_docs: Transaction documents
        """
        idx_statements = config.elastic_index_statements
        idx_transactions = config.elastic_index_transactions
        
        if stmt_docs:
            bulk_index(idx_statements, stmt_docs, id_field="id")
            log.info(f"Indexed {len(stmt_docs)} statement(s)")
        
        if txn_docs:
            bulk_index(idx_transactions, txn_docs, id_field="id")
            log.info(f"Indexed {len(txn_docs)} transaction(s)")
    
    @staticmethod
    def setup_aggregation_transform(wait_for_checkpoint: bool = False) -> None:
        """
        Setup and start the monthly aggregation transform.
        
        Args:
            wait_for_checkpoint: Whether to wait for initial backfill
        """
        src = config.elastic_index_transactions
        dest = config.elastic_index_aggregates_monthly
        transform_id = config.elastic_transform_id
        
        try:
            ensure_transform_monthly(
                transform_id,
                source_index=f"{src}*",
                dest_index=dest,
                calendar_interval="1M",
                frequency="1h"
            )
            start_transform(transform_id)
            log.info(f"Started transform: {transform_id}")
            
            if wait_for_checkpoint:
                wait_for_first_checkpoint(transform_id, timeout_sec=180)
                log.info("Transform initial checkpoint complete")
        except Exception as e:
            log.error(f"Transform setup failed: {e!r}")
            raise

