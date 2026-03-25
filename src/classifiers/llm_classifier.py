"""LLM-based classifier using Ollama for content classification."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.core.config import AppConfig
from src.core.models import FileCategory, FileInfo

logger = logging.getLogger(__name__)

# Map LLM output labels to our categories
LABEL_TO_CATEGORY: dict[str, FileCategory] = {
    "aadhaar": FileCategory.AADHAAR,
    "pan_card": FileCategory.PAN_CARD,
    "passport": FileCategory.PASSPORT,
    "voter_id": FileCategory.VOTER_ID,
    "driving_license": FileCategory.DRIVING_LICENSE,
    "bank_statement": FileCategory.BANK_STATEMENT,
    "tax_document": FileCategory.TAX_DOCUMENT,
    "invoice": FileCategory.INVOICE,
    "salary_slip": FileCategory.SALARY_SLIP,
    "insurance": FileCategory.INSURANCE,
    "study_material": FileCategory.STUDY_MATERIAL,
    "certificate": FileCategory.CERTIFICATE,
    "marksheet": FileCategory.MARKSHEET,
    "resume": FileCategory.RESUME,
    "official_letter": FileCategory.OFFICIAL_LETTER,
    "contract": FileCategory.CONTRACT,
    "report": FileCategory.REPORT,
    "general_document": FileCategory.GENERAL_DOCUMENT,
    "other": FileCategory.OTHER,
}

CLASSIFICATION_PROMPT = """You are a document classifier. Classify the following document based on its filename and content excerpt.

Filename: {filename}
Content (first ~2000 chars):
---
{content}
---

Classify into EXACTLY ONE of these categories:
- aadhaar (Indian Aadhaar card)
- pan_card (Indian PAN card)
- passport
- voter_id
- driving_license
- bank_statement
- tax_document (ITR, Form 16, TDS)
- invoice (bills, receipts, payment confirmations)
- salary_slip (payslip, salary statement)
- insurance (insurance policy, claim)
- study_material (notes, textbook, lecture, assignment)
- certificate (course certificate, achievement, diploma)
- marksheet (exam results, grades)
- resume (CV, biodata)
- official_letter (formal correspondence)
- contract (agreement, terms)
- report (business report, analysis)
- general_document (anything else)
- other

Respond with ONLY a JSON object: {{"category": "<label>", "confidence": <0.0-1.0>}}
No explanation."""


class LLMClassifier:
    """Classifies documents using a local LLM via Ollama."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        if self._available is not None:
            return self._available

        try:
            import ollama
            client = ollama.Client(host=self.config.ollama_host)
            models = client.list()
            model_names = [m.model for m in models.models]
            self._available = any(
                self.config.ollama_model in name for name in model_names
            )
            if not self._available:
                logger.warning(
                    f"Model '{self.config.ollama_model}' not found. "
                    f"Available: {model_names}. "
                    f"Run: ollama pull {self.config.ollama_model}"
                )
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False

        return self._available

    def classify(self, file_info: FileInfo, text: str) -> tuple[FileCategory, float]:
        """
        Classify a document using the LLM.
        Returns (category, confidence). Falls back to OTHER on failure.
        """
        if not text or not self.is_available():
            return FileCategory.OTHER, 0.0

        prompt = CLASSIFICATION_PROMPT.format(
            filename=file_info.name,
            content=text[:2000],
        )

        try:
            import ollama
            client = ollama.Client(host=self.config.ollama_host)
            response = client.chat(
                model=self.config.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": 100},
            )

            result_text = response.message.content.strip()
            return self._parse_response(result_text)

        except Exception as e:
            logger.warning(f"LLM classification failed for {file_info.name}: {e}")
            return FileCategory.OTHER, 0.0

    def _parse_response(self, text: str) -> tuple[FileCategory, float]:
        """Parse JSON response from LLM."""
        try:
            # Try to extract JSON from response
            # Handle cases where LLM wraps in markdown code blocks
            text = text.strip().strip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()

            data = json.loads(text)
            label = data.get("category", "other").lower().strip()
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            category = LABEL_TO_CATEGORY.get(label, FileCategory.OTHER)
            return category, confidence

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Failed to parse LLM response: {text[:200]} - {e}")
            return FileCategory.OTHER, 0.0
