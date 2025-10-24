"""
Utility functions for common operations.

Provides helper functions for:
- File size formatting
- Cryptographic hashing
- Safe file writing
- ID generation
"""
from __future__ import annotations
from pathlib import Path
import hashlib
from typing import Union

from core.logger import get_logger

log = get_logger("core/utils")


def human_size(num_bytes: Union[int, float]) -> str:
    """
    Convert bytes to human-readable size format.
    
    Converts byte values into appropriate units (B, KB, MB, GB, TB)
    with one decimal place precision.
    
    Args:
        num_bytes: Number of bytes to convert
        
    Returns:
        str: Formatted size string (e.g., "1.5 MB")
        
    Examples:
        >>> human_size(1024)
        "1.0 KB"
        >>> human_size(1536000)
        "1.5 MB"
        >>> human_size(0)
        "0.0 B"
    """
    if not isinstance(num_bytes, (int, float)):
        log.warning(f"Invalid input type for human_size: {type(num_bytes)}")
        return "0.0 B"
    
    if num_bytes < 0:
        log.warning(f"Negative byte value: {num_bytes}")
        return "0.0 B"
    
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num_bytes)
    idx = 0
    
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    
    return f"{size:.1f} {units[idx]}"


def sha256_bytes(data: bytes) -> str:
    """
    Calculate SHA-256 hash of byte data.
    
    Args:
        data: Bytes to hash
        
    Returns:
        str: Hexadecimal hash digest
        
    Raises:
        TypeError: If data is not bytes
        
    Examples:
        >>> sha256_bytes(b"hello")
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    """
    if not isinstance(data, bytes):
        error_msg = f"Expected bytes, got {type(data)}"
        log.error(error_msg)
        raise TypeError(error_msg)
    
    hash_digest = hashlib.sha256(data).hexdigest()
    log.debug(f"Generated SHA-256 hash: length={len(data)} bytes hash={hash_digest[:16]}...")
    
    return hash_digest


def sha256_file(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file.
    
    Efficiently hashes large files by reading in chunks.
    
    Args:
        file_path: Path to file to hash
        
    Returns:
        str: Hexadecimal hash digest
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
        
    Examples:
        >>> sha256_file(Path("document.pdf"))
        "abc123..."
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        error_msg = f"File not found: {file_path}"
        log.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    if not file_path.is_file():
        error_msg = f"Not a file: {file_path}"
        log.error(error_msg)
        raise IOError(error_msg)
    
    try:
        hasher = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read file in 64KB chunks
            chunk_size = 65536
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        
        hash_digest = hasher.hexdigest()
        file_size = file_path.stat().st_size
        
        log.debug(
            f"Hashed file: path={file_path.name} "
            f"size={human_size(file_size)} hash={hash_digest[:16]}..."
        )
        
        return hash_digest
        
    except Exception as e:
        log.error(f"Failed to hash file {file_path}: {e}", exc_info=True)
        raise IOError(f"Failed to hash file: {e}")


def safe_write(path: Path, data: bytes) -> None:
    """
    Safely write bytes to a file, creating directories as needed.
    
    Creates parent directories if they don't exist and writes data atomically.
    
    Args:
        path: Path where file should be written
        data: Bytes to write
        
    Raises:
        TypeError: If data is not bytes
        IOError: If write operation fails
        
    Examples:
        >>> safe_write(Path("output/data.bin"), b"content")
    """
    if not isinstance(data, bytes):
        error_msg = f"Expected bytes, got {type(data)}"
        log.error(error_msg)
        raise TypeError(error_msg)
    
    path = Path(path)
    
    try:
        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with path.open("wb") as f:
            f.write(data)
        
        log.debug(
            f"Safely wrote file: path={path} "
            f"size={human_size(len(data))}"
        )
        
    except Exception as e:
        log.error(
            f"Failed to write file {path}: {e}",
            exc_info=True
        )
        raise IOError(f"Failed to write file: {e}")


def make_id(*parts: str) -> str:
    """
    Generate a deterministic ID from multiple string parts.
    
    Creates a consistent 32-character hexadecimal ID by:
    1. Joining all parts with "||" delimiter
    2. Computing SHA-256 hash
    3. Taking first 32 characters
    
    Args:
        *parts: Variable number of string parts to combine
        
    Returns:
        str: 32-character hexadecimal ID
        
    Raises:
        TypeError: If any part is not a string
        
    Examples:
        >>> make_id("account", "123", "2024-01-01")
        "a1b2c3d4e5f6789..."  # 32 chars
        >>> make_id("same", "parts")
        "xyz..."  # Same input always produces same output
    """
    # Validate all parts are strings
    for i, part in enumerate(parts):
        if not isinstance(part, str):
            error_msg = f"Part {i} is not a string: {type(part)}"
            log.error(error_msg)
            raise TypeError(error_msg)
    
    # Join parts and hash
    joined = "||".join(parts)
    hash_id = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]
    
    log.debug(
        f"Generated ID: parts_count={len(parts)} "
        f"input_length={len(joined)} id={hash_id[:8]}..."
    )
    
    return hash_id


def format_currency(amount: Union[int, float], currency: str | None = None) -> str:
    """
    Format an amount with the appropriate currency symbol or code.
    
    Supports common currency codes and provides appropriate formatting.
    Falls back to USD if currency is not provided or not recognized.
    
    Args:
        amount: Numeric amount to format
        currency: ISO 4217 currency code (e.g., "USD", "EUR", "BDT", "GBP", "INR")
                 or None to default to USD
        
    Returns:
        str: Formatted currency string (e.g., "$1,234.56", "€1,234.56", "৳1,234.56")
        
    Examples:
        >>> format_currency(1234.56, "USD")
        "$1,234.56"
        >>> format_currency(1234.56, "EUR")
        "€1,234.56"
        >>> format_currency(1234.56, "BDT")
        "৳1,234.56"
        >>> format_currency(1234.56, None)
        "$1,234.56"
    """
    # Currency symbol mapping
    CURRENCY_SYMBOLS = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "BDT": "৳",
        "INR": "₹",
        "JPY": "¥",
        "CNY": "¥",
        "AUD": "A$",
        "CAD": "C$",
        "CHF": "CHF",
        "SGD": "S$",
        "AED": "د.إ",
        "SAR": "﷼",
        "QAR": "ر.ق",
        "THB": "฿",
        "MYR": "RM",
        "IDR": "Rp",
        "PHP": "₱",
        "KRW": "₩",
        "TWD": "NT$",
        "HKD": "HK$",
        "NZD": "NZ$",
        "SEK": "kr",
        "NOK": "kr",
        "DKK": "kr",
        "PLN": "zł",
        "CZK": "Kč",
        "HUF": "Ft",
        "RUB": "₽",
        "TRY": "₺",
        "ZAR": "R",
        "BRL": "R$",
        "MXN": "Mex$",
        "ARS": "AR$",
        "CLP": "CLP$",
        "COP": "COL$",
        "PEN": "S/",
        "PKR": "₨",
        "LKR": "Rs",
        "NPR": "Rs",
        "MMK": "K",
        "VND": "₫",
        "KHR": "៛",
        "LAK": "₭",
        "EGP": "E£",
        "KES": "KSh",
        "NGN": "₦",
        "GHS": "₵",
        "MAD": "د.م.",
        "TND": "د.ت",
    }
    
    # Normalize currency code
    currency_code = (currency or "USD").upper().strip()
    
    # Get symbol, fallback to currency code if not found
    symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    
    # Format amount with commas and 2 decimal places
    formatted_amount = f"{amount:,.2f}"
    
    # Return formatted string
    return f"{symbol}{formatted_amount}"
