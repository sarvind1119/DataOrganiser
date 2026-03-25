"""Tests for rule-based classifier."""

from pathlib import Path
from src.core.models import FileInfo, FileType, FileCategory
from src.classifiers.rule_based import RuleBasedClassifier


def make_file_info(name: str, file_type: FileType = FileType.PDF) -> FileInfo:
    """Helper to create a FileInfo without a real file."""
    fi = FileInfo.__new__(FileInfo)
    fi.path = Path(f"/fake/{name}")
    fi.name = name
    fi.extension = Path(name).suffix.lower()
    fi.file_type = file_type
    fi.size_bytes = 1000
    fi.modified_time = None
    fi.created_time = None
    fi.category = FileCategory.OTHER
    fi.confidence = 0.0
    fi.content_preview = ""
    fi.hash_md5 = ""
    fi.destination = None
    fi.is_duplicate = False
    fi.metadata = {}
    return fi


classifier = RuleBasedClassifier()


def test_whatsapp_image():
    fi = make_file_info("IMG-20240115-WA0012.jpg", FileType.IMAGE)
    cat, conf = classifier.classify(fi)
    assert cat == FileCategory.WHATSAPP_MEDIA
    assert conf >= 0.9


def test_screenshot():
    fi = make_file_info("Screenshot_2024-01-15.png", FileType.IMAGE)
    cat, conf = classifier.classify(fi)
    assert cat == FileCategory.SCREENSHOT
    assert conf >= 0.9


def test_resume():
    fi = make_file_info("My_Resume_2024.pdf")
    cat, conf = classifier.classify(fi)
    assert cat == FileCategory.RESUME
    assert conf >= 0.9


def test_aadhaar_content():
    fi = make_file_info("document.pdf")
    text = "UNIQUE IDENTIFICATION AUTHORITY OF INDIA Aadhaar No: 1234 5678 9012 Government of India"
    cat, conf = classifier.classify(fi, text)
    assert cat == FileCategory.AADHAAR
    assert conf >= 0.8


def test_pan_card_content():
    fi = make_file_info("card.pdf")
    text = "INCOME TAX DEPARTMENT Permanent Account Number ABCDE1234F Government of India"
    cat, conf = classifier.classify(fi, text)
    assert cat == FileCategory.PAN_CARD
    assert conf >= 0.8


def test_bank_statement_content():
    fi = make_file_info("statement.pdf")
    text = (
        "Account Statement for the period Jan-Mar 2024. "
        "Account Number: 1234567890. Opening Balance: 50000. "
        "Transaction details: Debit Credit IFSC Code: SBIN0001234"
    )
    cat, conf = classifier.classify(fi, text)
    assert cat == FileCategory.BANK_STATEMENT
    assert conf >= 0.8


def test_salary_slip_content():
    fi = make_file_info("payslip.pdf")
    text = (
        "Salary Slip for December 2024. Employee ID: 12345. "
        "Basic Salary: 50000. HRA: 20000. Provident Fund: 6000. "
        "Net Pay: 64000. Deductions: 12000. Gross Salary: 76000."
    )
    cat, conf = classifier.classify(fi, text)
    assert cat == FileCategory.SALARY_SLIP
    assert conf >= 0.8


def test_study_material_content():
    fi = make_file_info("notes.pdf")
    text = (
        "Chapter 5: Data Structures. Lecture Notes. "
        "Exercise 5.1: Implement a binary search tree. "
        "Assignment due date: 15th March. Tutorial session on Thursday."
    )
    cat, conf = classifier.classify(fi, text)
    assert cat == FileCategory.STUDY_MATERIAL
    assert conf >= 0.7


def test_executable_software():
    fi = make_file_info("installer.exe", FileType.EXECUTABLE)
    cat, conf = classifier.classify(fi)
    assert cat == FileCategory.SOFTWARE
    assert conf >= 0.7


def test_fallback_image():
    fi = make_file_info("random_photo.jpg", FileType.IMAGE)
    cat, conf = classifier.classify(fi)
    # Should fall back to PERSONAL_PHOTO with low confidence
    assert cat == FileCategory.PERSONAL_PHOTO
    assert conf < 0.5
