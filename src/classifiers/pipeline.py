"""Classification pipeline - combines rule-based and LLM classifiers."""

from __future__ import annotations

import logging
from typing import Callable

from src.core.config import AppConfig
from src.core.models import FileCategory, FileInfo, FileType
from src.classifiers.rule_based import RuleBasedClassifier
from src.classifiers.llm_classifier import LLMClassifier
from src.utils.extractors import extract_text, extract_image_metadata

logger = logging.getLogger(__name__)

# File types that benefit from text extraction
TEXT_EXTRACTABLE = {FileType.PDF, FileType.WORD, FileType.EXCEL, FileType.POWERPOINT, FileType.TEXT}

# Confidence threshold above which we skip LLM
RULE_CONFIDENCE_THRESHOLD = 0.8


class ClassificationPipeline:
    """
    Two-stage classification pipeline:
    1. Rule-based classifier (fast, pattern matching)
    2. LLM classifier (slower, used for ambiguous files)
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.rule_classifier = RuleBasedClassifier()
        self.llm_classifier = LLMClassifier(config) if config.use_llm else None

    def classify_files(
        self,
        files: list[FileInfo],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[FileInfo]:
        """
        Classify all files in the list.

        Args:
            files: List of FileInfo objects to classify.
            progress_callback: Called with (current, total, status_message).
        """
        total = len(files)
        llm_available = self.llm_classifier and self.llm_classifier.is_available()

        for i, fi in enumerate(files):
            if progress_callback and i % 10 == 0:
                progress_callback(i, total, f"Classifying: {fi.name}")

            self._classify_single(fi, llm_available)

        if progress_callback:
            progress_callback(total, total, "Classification complete")

        return files

    def _classify_single(self, fi: FileInfo, llm_available: bool):
        """Classify a single file through the pipeline."""

        # Step 1: Extract text if applicable
        text = ""
        if fi.file_type in TEXT_EXTRACTABLE:
            text = extract_text(fi)

        # Step 1b: Extract image metadata
        if fi.file_type == FileType.IMAGE:
            fi.metadata = extract_image_metadata(fi)

        # Step 2: Rule-based classification
        category, confidence = self.rule_classifier.classify(fi, text)

        # Step 3: If rule-based isn't confident enough, try LLM
        if confidence < RULE_CONFIDENCE_THRESHOLD and text and llm_available:
            llm_category, llm_confidence = self.llm_classifier.classify(fi, text)
            if llm_confidence > confidence:
                category = llm_category
                confidence = llm_confidence
                logger.debug(f"LLM override for {fi.name}: {category.value} ({confidence:.2f})")

        fi.category = category
        fi.confidence = confidence
