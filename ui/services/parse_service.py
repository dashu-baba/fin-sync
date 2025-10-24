"""Parsing and indexing business logic service."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple

from core.config import config
from core.logger import get_logger
from core.utils import make_id
from core.storage import get_storage_backend
from ingestion import parse_pdf_to_json
from ingestion.parser_vertex import parse_csv_to_json
from elastic import embed_texts
from elastic.indexer import ensure_statements_index, ensure_transactions_index, bulk_index
from models.schema import ParsedStatement

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
    def _download_gcs_file_if_needed(file_path: str) -> Tuple[str, bool]:
        """
        Download file from GCS to a temporary location if it's a GCS path.
        
        Args:
            file_path: Path to file (local or gs:// URL)
            
        Returns:
            Tuple of (local_path, is_temporary)
            - local_path: Path to use for parsing (local file)
            - is_temporary: True if file was downloaded and should be cleaned up
        """
        # Check if it's a GCS path
        if file_path.startswith("gs://"):
            log.info(f"Downloading file from GCS: {file_path}")
            
            try:
                # Extract filename from GCS path
                filename = Path(file_path).name
                
                # Get storage backend and read file
                storage = get_storage_backend()
                
                # Extract the path within the bucket (remove gs://bucket-name/)
                # Format: gs://bucket-name/path/to/file.pdf -> path/to/file.pdf
                parts = file_path.replace("gs://", "").split("/", 1)
                if len(parts) == 2:
                    gcs_path = parts[1]  # Get the path within bucket
                else:
                    gcs_path = filename  # Just the filename
                
                file_content = storage.read_file(gcs_path)
                
                # Create temporary file
                temp_fd, temp_path = tempfile.mkstemp(suffix=f"_{filename}")
                try:
                    os.write(temp_fd, file_content)
                finally:
                    os.close(temp_fd)
                
                log.info(f"Downloaded to temporary file: {temp_path}")
                return temp_path, True
                
            except Exception as e:
                log.error(f"Failed to download file from GCS: {file_path}, error: {e!r}")
                raise
        else:
            # Local file path - use as-is
            return file_path, False
    
    @staticmethod
    def parse_file(
        file_path: str,
        file_ext: str,
        password: Optional[str] = None,
        gcp_project: Optional[str] = None,
        gcp_location: Optional[str] = None
    ) -> ParsedStatement:
        """
        Parse a single file (PDF or CSV) using Vertex AI.
        Automatically handles GCS paths by downloading first.
        
        Returns:
            Parsed statement object or None if parsing failed.
        """
        gcp_project = gcp_project or config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
        gcp_location = gcp_location or config.gcp_location or os.getenv("GCP_LOCATION", "us-central1")
        
        # Download from GCS if needed
        local_path, is_temp = ParseService._download_gcs_file_if_needed(file_path)
        
        try:
            # TODO: Add CSV support
            result = parse_pdf_to_json(
                    local_path,
                    password,
                    gcp_project=gcp_project,
                    gcp_location=gcp_location,
                    vertex_model=config.vertex_model
                )
            return result
        except Exception as e:
            log.error(f"Failed to parse {Path(file_path).name}: {e!r}")
            raise
        finally:
            # Clean up temporary file if we created one
            if is_temp:
                try:
                    os.unlink(local_path)
                    log.debug(f"Cleaned up temporary file: {local_path}")
                except Exception as e:
                    log.warning(f"Failed to clean up temporary file {local_path}: {e}")
    
    @staticmethod
    def create_statement_docs(
        parsed: ParsedStatement,
        source_file: str,
        gcp_project: Optional[str] = None,
        gcp_location: Optional[str] = None
    ) -> List[Dict]:
        """
        Create statements documents for indexing.
        
        Args:
            parsed: Parsed statement object
            source_file: Source filename
            gcp_project: GCP project ID
            gcp_location: GCP location
            
        Returns:
            List of statement document dicts
        """
        stmt_docs = []
        for i, page in enumerate(parsed.pages):
            statement_id = make_id(
                str(parsed.accountNo),
                str(parsed.statementFrom),
                str(parsed.statementTo),
                str(page.pageNumber),
            )
        
            head_txn = "\n".join(
                f"{statement.statementDate} {statement.statementType} {statement.statementAmount} {statement.statementDescription}"
                for statement in page.statements[:200]
            )
        
            summary_text = (
                f"Account: {parsed.accountName or 'Unknown'}\n"
                f"Bank: {parsed.bankName or 'Unknown'}\n"
                f"Range: {parsed.statementFrom}..{parsed.statementTo}\n"
                f"Page: {page.pageNumber}\n"
                f"Transactions:\n{head_txn}"
            )

            summary_vector = embed_texts(
                [summary_text],
                project_id=gcp_project,
                location=gcp_location,
                model_name=config.vertex_model_embed
            )[0]
        
            stmt_docs.append({
                "id": statement_id,
                "accountNo": str(parsed.accountNo),
                "bankName": parsed.bankName,
                "pageNumber": page.pageNumber,
                "accountName": parsed.accountName,
                "statementFrom": str(parsed.statementFrom),
                "statementTo": str(parsed.statementTo),
                "summary_text": summary_text,
                "summary_vector": summary_vector,
                "meta": {"sourceFile": source_file},
            })
        return stmt_docs
    
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
        # Flatten all transactions from all pages, preserving page information
        all_statements = []
        for page in parsed.pages:
            for stmt in page.statements:
                all_statements.append((page.pageNumber, stmt))
        
        for i, (page_num, txn) in enumerate(all_statements):
            txn_id = make_id(
                str(parsed.accountNo),
                str(txn.statementDate),
                str(txn.statementPage or page_num),
                str(txn.statementAmount),
                txn.statementDescription or "",
                str(statement_id)
            )
            
            # TODO: Embed descriptions if needed
            # vec = None
            # if embed_descriptions:
            #     vec = embed_texts(
            #         [txn.statementDescription or ""],
            #         project_id=gcp_project,
            #         location=gcp_location,
            #         model_name=config.vertex_model_embed
            #     )[0]
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
                "currency": parsed.currency,
                "sourceStatementId": statement_id,
                "sourceFile": source_file,
                "timestamp": str(txn.statementDate),
                "@timestamp": str(txn.statementDate),
                "pageNumber": txn.statementPage or page_num,
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

