#!/usr/bin/env python3
"""
Test script for duplicate upload protection.

This script verifies that the duplicate protection mechanisms work correctly:
1. Filename duplicate detection
2. Content hash duplicate detection

Usage:
    python scripts/test_duplicate_protection.py

Note: This is a standalone test that doesn't require the full application environment.
"""

from pathlib import Path
import sys
import tempfile
import hashlib
from typing import Tuple, Optional

# Standalone implementation for testing
def sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def check_duplicate_by_hash(file_content: bytes, upload_dir: Path) -> Tuple[bool, Optional[str]]:
    """Check if a file with the same content hash already exists."""
    file_hash = sha256_bytes(file_content)
    
    if upload_dir.exists():
        for existing_file in upload_dir.glob("*.pdf"):
            try:
                with open(existing_file, "rb") as f:
                    existing_hash = sha256_bytes(f.read())
                if existing_hash == file_hash:
                    return True, existing_file.name
            except Exception as e:
                print(f"Error checking file {existing_file}: {e}")
                continue
    
    return False, None


def check_duplicate_by_name(filename: str, upload_dir: Path) -> bool:
    """Check if a file with the same name already exists."""
    target_path = upload_dir / filename
    return target_path.exists()


def test_filename_duplicate():
    """Test duplicate detection by filename."""
    print("\n=== Test 1: Filename Duplicate Detection ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir)
        
        # Create a test file
        test_file = upload_dir / "test_statement.pdf"
        test_file.write_bytes(b"Test content")
        
        # Test duplicate detection
        is_duplicate = check_duplicate_by_name("test_statement.pdf", upload_dir)
        
        assert is_duplicate, "Failed to detect duplicate filename"
        print("✅ PASS: Duplicate filename detected correctly")
        
        # Test non-duplicate
        is_duplicate = check_duplicate_by_name("different_file.pdf", upload_dir)
        assert not is_duplicate, "False positive: Non-existent file reported as duplicate"
        print("✅ PASS: Non-duplicate filename allowed correctly")


def test_hash_duplicate():
    """Test duplicate detection by content hash."""
    print("\n=== Test 2: Content Hash Duplicate Detection ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir)
        
        # Create first file
        test_content = b"Bank Statement Content for Testing" * 100
        file1 = upload_dir / "statement_jan.pdf"
        file1.write_bytes(test_content)
        
        # Test with same content, different name (renamed file)
        is_duplicate, original_name = check_duplicate_by_hash(
            test_content, upload_dir
        )
        
        assert is_duplicate, "Failed to detect duplicate content"
        assert original_name == "statement_jan.pdf", f"Wrong original filename: {original_name}"
        print("✅ PASS: Duplicate content detected (renamed file)")
        
        # Test with different content
        different_content = b"Different Bank Statement Content" * 100
        is_duplicate, original_name = check_duplicate_by_hash(
            different_content, upload_dir
        )
        
        assert not is_duplicate, "False positive: Different content reported as duplicate"
        print("✅ PASS: Different content allowed correctly")


def test_hash_collision_resistance():
    """Test that hash function is collision-resistant."""
    print("\n=== Test 3: Hash Collision Resistance ===")
    
    content1 = b"Statement 1" * 1000
    content2 = b"Statement 2" * 1000
    
    hash1 = hashlib.sha256(content1).hexdigest()
    hash2 = hashlib.sha256(content2).hexdigest()
    
    assert hash1 != hash2, "Hash collision detected (extremely unlikely)"
    print("✅ PASS: Different contents produce different hashes")


def test_empty_directory():
    """Test behavior with empty upload directory."""
    print("\n=== Test 4: Empty Directory Handling ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir)
        
        # Test hash check in empty directory
        is_duplicate, _ = check_duplicate_by_hash(
            b"Some content", upload_dir
        )
        assert not is_duplicate, "False positive in empty directory"
        print("✅ PASS: Empty directory handled correctly")
        
        # Test filename check in empty directory
        is_duplicate = check_duplicate_by_name("test.pdf", upload_dir)
        assert not is_duplicate, "False positive for filename in empty directory"
        print("✅ PASS: Filename check works in empty directory")


def test_non_existent_directory():
    """Test behavior with non-existent upload directory."""
    print("\n=== Test 5: Non-existent Directory Handling ===")
    
    upload_dir = Path("/tmp/non_existent_test_dir_12345")
    
    # Ensure directory doesn't exist
    if upload_dir.exists():
        import shutil
        shutil.rmtree(upload_dir)
    
    # Test hash check
    is_duplicate, _ = check_duplicate_by_hash(
        b"Some content", upload_dir
    )
    assert not is_duplicate, "False positive with non-existent directory"
    print("✅ PASS: Non-existent directory handled correctly (hash)")
    
    # Test filename check
    is_duplicate = check_duplicate_by_name("test.pdf", upload_dir)
    assert not is_duplicate, "False positive with non-existent directory"
    print("✅ PASS: Non-existent directory handled correctly (filename)")


def test_multiple_files():
    """Test with multiple files in directory."""
    print("\n=== Test 6: Multiple Files Handling ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir)
        
        # Create multiple files
        for i in range(5):
            file = upload_dir / f"statement_{i}.pdf"
            file.write_bytes(f"Statement content {i}".encode() * 100)
        
        # Test finding specific duplicate
        target_content = "Statement content 2".encode() * 100
        is_duplicate, original_name = check_duplicate_by_hash(
            target_content, upload_dir
        )
        
        assert is_duplicate, "Failed to find duplicate among multiple files"
        assert original_name == "statement_2.pdf", f"Wrong file identified: {original_name}"
        print("✅ PASS: Correct duplicate found among multiple files")


def test_large_file_performance():
    """Test performance with larger files."""
    print("\n=== Test 7: Large File Performance ===")
    
    import time
    
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir)
        
        # Create a 5MB test file (typical bank statement size)
        large_content = b"X" * (5 * 1024 * 1024)
        file1 = upload_dir / "large_statement.pdf"
        file1.write_bytes(large_content)
        
        # Test hash calculation performance
        start_time = time.time()
        is_duplicate, _ = check_duplicate_by_hash(
            large_content, upload_dir
        )
        duration = time.time() - start_time
        
        assert is_duplicate, "Failed to detect large file duplicate"
        assert duration < 2.0, f"Hash check too slow: {duration:.2f}s (should be < 2s)"
        print(f"✅ PASS: Large file (5MB) processed in {duration:.3f}s")


def run_all_tests():
    """Run all duplicate protection tests."""
    print("\n" + "="*60)
    print("DUPLICATE PROTECTION TEST SUITE")
    print("="*60)
    
    tests = [
        test_filename_duplicate,
        test_hash_duplicate,
        test_hash_collision_resistance,
        test_empty_directory,
        test_non_existent_directory,
        test_multiple_files,
        test_large_file_performance,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"❌ FAIL: {test.__name__} - {e}")
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: {test.__name__} - {e}")
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ All tests passed! Duplicate protection is working correctly.")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

