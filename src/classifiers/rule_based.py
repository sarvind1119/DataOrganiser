"""Rule-based classifier using keywords, regex patterns, and file metadata."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.models import FileCategory, FileInfo, FileType


class RuleBasedClassifier:
    """
    Classifies files using pattern matching on filenames, paths, and content.
    Returns (category, confidence) tuple.
    """

    def __init__(self, config=None):
        self.custom_rules: list[dict] = []
        if config and hasattr(config, "custom_rules"):
            self.custom_rules = config.custom_rules or []

    def classify(self, file_info: FileInfo, text: str = "") -> tuple[FileCategory, float]:
        """Classify a file. Returns (category, confidence 0.0-1.0)."""

        # 0. Try custom user rules first (highest priority)
        cat, conf = self._classify_by_custom_rules(file_info, text)
        if conf >= 0.8:
            return cat, conf

        # 1. Try filename/path based rules first
        cat, conf = self._classify_by_path(file_info)
        if conf >= 0.8:
            return cat, conf

        # 2. Try content-based rules for documents
        if text:
            cat2, conf2 = self._classify_by_content(text, file_info)
            if conf2 > conf:
                cat, conf = cat2, conf2

        # 3. Fall back to file type based defaults
        if conf < 0.5:
            cat, conf = self._classify_by_type(file_info)

        return cat, conf

    def _classify_by_path(self, fi: FileInfo) -> tuple[FileCategory, float]:
        """Classify based on file path and name patterns."""
        name_lower = fi.name.lower()
        path_lower = str(fi.path).lower()

        # WhatsApp media detection
        if "whatsapp" in path_lower or re.match(r"img-\d{8}-wa\d+", name_lower):
            if fi.file_type == FileType.IMAGE:
                return FileCategory.WHATSAPP_MEDIA, 0.95
            if fi.file_type == FileType.VIDEO:
                return FileCategory.WHATSAPP_MEDIA, 0.95
            if fi.file_type in (FileType.PDF, FileType.WORD):
                return FileCategory.WHATSAPP_MEDIA, 0.85

        # Screenshot detection
        if any(kw in name_lower for kw in ("screenshot", "screen shot", "snip", "capture")):
            return FileCategory.SCREENSHOT, 0.9

        # Camera photo detection (DCIM, IMG_, DSC_)
        if "dcim" in path_lower or re.match(r"(img_|dsc_|dscn|p\d{7})", name_lower):
            if fi.file_type == FileType.IMAGE:
                return FileCategory.CAMERA_PHOTO, 0.85

        # Resume/CV detection
        if any(kw in name_lower for kw in ("resume", "cv ", "curriculum", "biodata")):
            return FileCategory.RESUME, 0.9

        # Certificate detection
        if any(kw in name_lower for kw in ("certificate", "cert_", "diploma")):
            return FileCategory.CERTIFICATE, 0.85

        # Salary/payslip detection
        if any(kw in name_lower for kw in ("salary", "payslip", "pay_slip", "pay slip")):
            return FileCategory.SALARY_SLIP, 0.9

        # Invoice / receipt
        if any(kw in name_lower for kw in ("invoice", "receipt", "bill_", "payment")):
            return FileCategory.INVOICE, 0.85

        # Installer / software
        if fi.file_type == FileType.EXECUTABLE:
            return FileCategory.SOFTWARE, 0.9

        return FileCategory.OTHER, 0.0

    def _classify_by_content(self, text: str, fi: FileInfo) -> tuple[FileCategory, float]:
        """Classify based on extracted text content."""
        text_lower = text.lower()

        # --- Indian Identity Documents ---

        # Aadhaar card
        aadhaar_patterns = [
            r"\b\d{4}\s?\d{4}\s?\d{4}\b",  # 12-digit Aadhaar number
            r"unique identification",
            r"aadhaar",
            r"uidai",
            r"आधार",
        ]
        if self._match_patterns(text_lower, aadhaar_patterns, threshold=2):
            return FileCategory.AADHAAR, 0.9

        # PAN card
        pan_patterns = [
            r"\b[a-z]{5}\d{4}[a-z]\b",  # PAN format: ABCDE1234F
            r"permanent account number",
            r"income tax",
            r"pan card",
        ]
        if self._match_patterns(text_lower, pan_patterns, threshold=2):
            return FileCategory.PAN_CARD, 0.9

        # Passport
        if any(kw in text_lower for kw in ("passport", "republic of india", "nationality")):
            if any(kw in text_lower for kw in ("date of birth", "place of issue", "date of expiry")):
                return FileCategory.PASSPORT, 0.85

        # Driving License
        if any(kw in text_lower for kw in ("driving licence", "driving license", "transport")):
            if any(kw in text_lower for kw in ("valid", "class of vehicle", "blood group")):
                return FileCategory.DRIVING_LICENSE, 0.85

        # Voter ID
        if any(kw in text_lower for kw in ("election commission", "voter", "electors photo")):
            return FileCategory.VOTER_ID, 0.85

        # --- Financial Documents ---

        # Bank statement
        bank_keywords = [
            "account statement", "bank statement", "transaction", "account number",
            "opening balance", "closing balance", "debit", "credit", "ifsc",
            "account summary", "passbook",
        ]
        if self._count_matches(text_lower, bank_keywords) >= 3:
            return FileCategory.BANK_STATEMENT, 0.85

        # Tax documents (ITR, Form 16, etc.)
        tax_keywords = [
            "income tax", "form 16", "form 26as", "itr", "tax return",
            "assessment year", "tds", "tax deducted",
        ]
        if self._count_matches(text_lower, tax_keywords) >= 2:
            return FileCategory.TAX_DOCUMENT, 0.85

        # Insurance
        insurance_keywords = [
            "insurance", "policy number", "premium", "sum assured",
            "nominee", "insured", "claim",
        ]
        if self._count_matches(text_lower, insurance_keywords) >= 3:
            return FileCategory.INSURANCE, 0.85

        # Salary slip
        salary_keywords = [
            "salary slip", "payslip", "basic salary", "gross salary",
            "net pay", "earnings", "deductions", "provident fund", "hra",
            "employee id", "pay period",
        ]
        if self._count_matches(text_lower, salary_keywords) >= 3:
            return FileCategory.SALARY_SLIP, 0.85

        # Invoice / Receipt
        invoice_keywords = [
            "invoice", "receipt", "bill to", "total amount", "gst",
            "tax invoice", "payment received", "order id", "₹",
        ]
        if self._count_matches(text_lower, invoice_keywords) >= 3:
            return FileCategory.INVOICE, 0.8

        # --- Education ---

        # Marksheet
        marksheet_keywords = [
            "marksheet", "marks obtained", "grade", "semester", "examination",
            "roll number", "cgpa", "sgpa", "result", "university",
        ]
        if self._count_matches(text_lower, marksheet_keywords) >= 3:
            return FileCategory.MARKSHEET, 0.85

        # Certificate
        cert_keywords = [
            "certificate", "certify", "awarded", "completion",
            "hereby", "course", "training", "achievement",
        ]
        if self._count_matches(text_lower, cert_keywords) >= 3:
            return FileCategory.CERTIFICATE, 0.8

        # Study material
        study_keywords = [
            "chapter", "lecture", "notes", "syllabus", "textbook",
            "exercise", "solution", "theorem", "assignment", "tutorial",
            "question paper", "previous year",
        ]
        if self._count_matches(text_lower, study_keywords) >= 3:
            return FileCategory.STUDY_MATERIAL, 0.75

        # Resume/CV
        resume_keywords = [
            "resume", "curriculum vitae", "objective", "experience",
            "education", "skills", "references", "linkedin",
        ]
        if self._count_matches(text_lower, resume_keywords) >= 4:
            return FileCategory.RESUME, 0.8

        # --- Work ---

        # Contract / Agreement
        contract_keywords = [
            "agreement", "contract", "terms and conditions", "whereas",
            "hereby", "clause", "party", "executed", "witness",
        ]
        if self._count_matches(text_lower, contract_keywords) >= 3:
            return FileCategory.CONTRACT, 0.75

        # Official letter
        letter_keywords = [
            "dear sir", "dear madam", "to whom it may concern",
            "yours faithfully", "yours sincerely", "regarding", "subject:",
        ]
        if self._count_matches(text_lower, letter_keywords) >= 2:
            return FileCategory.OFFICIAL_LETTER, 0.7

        return FileCategory.OTHER, 0.0

    def _classify_by_type(self, fi: FileInfo) -> tuple[FileCategory, float]:
        """Fallback classification based purely on file type."""
        type_map = {
            FileType.IMAGE: (FileCategory.PERSONAL_PHOTO, 0.4),
            FileType.VIDEO: (FileCategory.VIDEO, 0.5),
            FileType.AUDIO: (FileCategory.MUSIC, 0.5),
            FileType.PDF: (FileCategory.GENERAL_DOCUMENT, 0.3),
            FileType.WORD: (FileCategory.GENERAL_DOCUMENT, 0.3),
            FileType.EXCEL: (FileCategory.SPREADSHEET_DATA, 0.4),
            FileType.POWERPOINT: (FileCategory.PRESENTATION, 0.5),
            FileType.CODE: (FileCategory.CODE, 0.6),
            FileType.ARCHIVE: (FileCategory.ARCHIVE, 0.6),
            FileType.EXECUTABLE: (FileCategory.SOFTWARE, 0.7),
            FileType.EBOOK: (FileCategory.EBOOK, 0.7),
            FileType.TEXT: (FileCategory.GENERAL_DOCUMENT, 0.3),
        }
        return type_map.get(fi.file_type, (FileCategory.OTHER, 0.1))

    @staticmethod
    def _match_patterns(text: str, patterns: list[str], threshold: int = 1) -> bool:
        """Check if at least `threshold` patterns match."""
        matches = sum(1 for p in patterns if re.search(p, text))
        return matches >= threshold

    @staticmethod
    def _count_matches(text: str, keywords: list[str]) -> int:
        """Count how many keywords appear in the text."""
        return sum(1 for kw in keywords if kw in text)

    def _classify_by_custom_rules(self, fi: FileInfo, text: str) -> tuple[FileCategory, float]:
        """Apply user-defined custom rules. Each rule has keywords and a target category."""
        if not self.custom_rules:
            return FileCategory.OTHER, 0.0

        combined = (fi.name + " " + text).lower()
        for rule in self.custom_rules:
            keywords = [kw.strip().lower() for kw in rule.get("keywords", "").split(",") if kw.strip()]
            category_name = rule.get("category", "")
            if not keywords or not category_name:
                continue
            matched = sum(1 for kw in keywords if kw in combined)
            if matched >= max(1, len(keywords) // 2):
                try:
                    category = FileCategory(category_name)
                    return category, 0.9
                except ValueError:
                    continue

        return FileCategory.OTHER, 0.0
