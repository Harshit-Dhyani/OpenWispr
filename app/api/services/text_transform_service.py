"""Text transformation service for transcription post-processing.

This module provides text transformation including:
- Short form expansion (e.g., "asap" -> "as soon as possible")
- Smart punctuation (capitalization after periods, question marks)
- URL and email normalization
- Casing corrections for technical terms (e.g., "api" -> "API")
- User correction learning from manual edits

The service applies transformations to improve transcription quality
before text injection or storage.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config.constants import COMMON_SHORT_FORMS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextTransformResult:
    original_text: str
    transformed_text: str
    expansions_applied: list[dict[str, Any]]


class TextTransformService:
    """Service for real-time text transformation including short forms, dictionary, snippets, and user corrections.

    Applies transformations in order:
    1. Smart punctuation (detects speech patterns)
    2. Common short form expansions
    3. URL/email/phone pattern normalization
    4. Date/time pattern normalization
    5. Casing corrections (acronyms)
    6. User corrections (learned)
    7. Dictionary replacements
    8. Snippet expansions
    9. Whitespace normalization
    """

    # Compile regex patterns for short forms (case-insensitive word boundary matching)
    _SHORT_FORM_PATTERN: re.Pattern | None = None
    _URL_PATTERN: re.Pattern | None = None
    _EMAIL_PATTERN: re.Pattern | None = None
    _PHONE_PATTERN: re.Pattern | None = None

    @classmethod
    def _get_short_form_pattern(cls) -> re.Pattern:
        """Get or create the short form regex pattern."""
        if cls._SHORT_FORM_PATTERN is None:
            sorted_forms = sorted(COMMON_SHORT_FORMS.keys(), key=len, reverse=True)
            escaped = [re.escape(trigger) for trigger in sorted_forms]
            pattern = r"\b(" + "|".join(escaped) + r")\b"
            cls._SHORT_FORM_PATTERN = re.compile(pattern, re.IGNORECASE)
        return cls._SHORT_FORM_PATTERN

    @classmethod
    def _get_url_pattern(cls) -> re.Pattern:
        """Get URL pattern for normalization."""
        if cls._URL_PATTERN is None:
            cls._URL_PATTERN = re.compile(r"\b(?:https?://|www\.)[^\s]+\b", re.IGNORECASE)
        return cls._URL_PATTERN

    @classmethod
    def _get_email_pattern(cls) -> re.Pattern:
        """Get email pattern for normalization."""
        if cls._EMAIL_PATTERN is None:
            cls._EMAIL_PATTERN = re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", re.IGNORECASE
            )
        return cls._EMAIL_PATTERN

    @classmethod
    def _get_phone_pattern(cls) -> re.Pattern:
        """Get phone number pattern for normalization."""
        if cls._PHONE_PATTERN is None:
            cls._PHONE_PATTERN = re.compile(
                r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"
            )
        return cls._PHONE_PATTERN

    # ============================================
    # Smart Punctuation
    # ============================================

    @staticmethod
    def apply_smart_punctuation(text: str) -> str:
        """Apply smart punctuation based on speech patterns.

        Detects sentence boundaries and adds appropriate punctuation.
        """
        if not text:
            return text

        # List of sentence-ending patterns that suggest a question
        question_indicators = [
            "is it",
            "are you",
            "do you",
            "does it",
            "did you",
            "can you",
            "could you",
            "would you",
            "will you",
            "what is",
            "what are",
            "where is",
            "where are",
            "when is",
            "when are",
            "who is",
            "who are",
            "how is",
            "how are",
            "why is",
            "why are",
            "am i",
            "are we",
            "is there",
            "are there",
            "let me know",
            "tell me",
            "do you think",
            "right",
            "okay",
            "ok",
            "correct",
        ]

        result = text

        # Add period at end if no punctuation
        if result and result[-1] not in ".!?":
            # Check if it looks like a statement (not a question)
            lower_text = result.lower().strip()
            is_question = any(lower_text.endswith(q) for q in question_indicators)

            if is_question:
                result = result.rstrip() + "?"
            else:
                # Default to period for statements
                result = result.rstrip() + "."

        # Fix common punctuation spacing issues
        result = re.sub(r"\s+([,;:!?])", r"\1", result)
        result = re.sub(r"([,;:])\s*", r"\1 ", result)
        result = re.sub(r"\.(\s*)\.", "...", result)
        result = re.sub(r"\.\s+", ". ", result)
        result = re.sub(r"!\s+", "! ", result)
        result = re.sub(r"\?\s+", "? ", result)

        # Clean up multiple spaces
        result = re.sub(r"  +", " ", result)

        return result.strip()

    # ============================================
    # Short Form Expansions
    # ============================================

    @classmethod
    def apply_short_forms(cls, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Apply common short form expansions to text."""
        if not text:
            return text, []

        expansions: list[dict[str, Any]] = []

        def replace_short_form(match: re.Match) -> str:
            trigger = match.group(0)
            trigger_lower = trigger.lower()

            if trigger_lower in COMMON_SHORT_FORMS:
                expansion = COMMON_SHORT_FORMS[trigger_lower]
                expansions.append(
                    {
                        "type": "short_form",
                        "trigger": trigger,
                        "expansion": expansion,
                    }
                )
                # Preserve case of first letter
                if trigger[0].isupper():
                    return expansion[0].upper() + expansion[1:]
                return expansion

            return trigger

        pattern = cls._get_short_form_pattern()
        result = pattern.sub(replace_short_form, text)

        return result, expansions

    # ============================================
    # URL/Email/Phone Normalization
    # ============================================

    @classmethod
    def normalize_urls_emails(cls, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Normalize URLs and emails to lowercase.

        Returns:
            Tuple of (normalized_text, list of applied normalizations)
        """
        if not text:
            return text, []

        expansions: list[dict[str, Any]] = []

        # Normalize URLs to lowercase
        def normalize_url(match: re.Match) -> str:
            url = match.group(0)
            original = url
            url = url.lower()
            if url != original:
                expansions.append(
                    {
                        "type": "normalization",
                        "original": original,
                        "normalized": url,
                    }
                )
            return url

        result = cls._get_url_pattern().sub(normalize_url, text)

        return result, expansions

    # ============================================
    # Casing Corrections
    # ============================================

    @staticmethod
    def apply_casing_corrections(text: str) -> str:
        """Apply common casing corrections for acronyms and proper nouns."""
        if not text:
            return text

        acronyms = {
            "ai": "AI",
            "ml": "ML",
            "dl": "DL",
            "nlp": "NLP",
            "cv": "CV",
            "ar": "AR",
            "vr": "VR",
            "mr": "MR",
            "api": "API",
            "sdk": "SDK",
            "ide": "IDE",
            "ci": "CI",
            "cd": "CD",
            "sql": "SQL",
            "html": "HTML",
            "css": "CSS",
            "js": "JS",
            "ts": "TS",
            "json": "JSON",
            "xml": "XML",
            "url": "URL",
            "uri": "URI",
            "dns": "DNS",
            "tcp": "TCP",
            "udp": "UDP",
            "http": "HTTP",
            "https": "HTTPS",
            "ftp": "FTP",
            "ssh": "SSH",
            "vpn": "VPN",
            "lan": "LAN",
            "wan": "WAN",
            "ram": "RAM",
            "rom": "ROM",
            "cpu": "CPU",
            "gpu": "GPU",
            "saas": "SaaS",
            "paas": "PaaS",
            "iaas": "IaaS",
            "ceo": "CEO",
            "cto": "CTO",
            "cfo": "CFO",
            "coo": "COO",
            "cmo": "CMO",
            "hr": "HR",
            "it": "IT",
            "qa": "QA",
            "kpi": "KPI",
            "okr": "OKR",
            "roi": "ROI",
            "sla": "SLA",
            "nda": "NDA",
            "pto": "PTO",
            "fyi": "FYI",
            "asap": "ASAP",
            "eod": "EOD",
            "wfh": "WFH",
            "eta": "ETA",
            "btw": "BTW",
            "imo": "IMO",
            "tbh": "TBH",
            "idk": "IDK",
            "fomo": "FOMO",
            "yolo": "YOLO",
            "lol": "LOL",
            "omg": "OMG",
            "wtf": "WTF",
            "brb": "BRB",
            "gn": "GN",
            "gm": "GM",
        }

        result = text
        for short, proper in acronyms.items():
            pattern = r"\b" + re.escape(short) + r"\b"
            result = re.sub(pattern, proper, result, flags=re.IGNORECASE)

        return result

    # ============================================
    # Whitespace Normalization
    # ============================================

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text."""
        if not text:
            return text

        # Replace multiple spaces with single space
        result = re.sub(r" +", " ", text)

        # Fix spaces before punctuation
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)

        # Ensure single space after punctuation
        result = re.sub(r"([,;:])\s*", r"\1 ", result)
        result = re.sub(r"\.(\s+)", ". ", result)
        result = re.sub(r"!(\s+)", "! ", result)
        result = re.sub(r"\?(\s+)", "? ", result)

        # Clean up multiple spaces again
        result = re.sub(r"  +", " ", result)

        return result.strip()

    # ============================================
    # Main Transform Method
    # ============================================

    @classmethod
    def transform(
        cls,
        text: str,
        *,
        apply_smart_punctuation: bool = True,
        apply_short_forms: bool = True,
        apply_url_normalization: bool = True,
        apply_casing: bool = True,
        apply_user_corrections: bool = False,
        apply_dictionary: bool = False,
        apply_snippets: bool = False,
        user_corrections_service=None,
        dictionary_service=None,
        snippet_service=None,
    ) -> TextTransformResult:
        """Apply all text transformations.

        Args:
            text: Input text to transform
            apply_smart_punctuation: Add punctuation based on speech patterns
            apply_short_forms: Apply short form expansions
            apply_url_normalization: Normalize URLs/emails to lowercase
            apply_casing: Apply acronym casing corrections
            apply_user_corrections: Apply learned corrections
            apply_dictionary: Apply dictionary replacements
            apply_snippets: Apply snippet expansions
            user_corrections_service: Service for user corrections
            dictionary_service: Service for dictionary
            snippet_service: Service for snippets

        Returns:
            TextTransformResult with original, transformed text, and applied expansions
        """
        if not text:
            return TextTransformResult(
                original_text=text,
                transformed_text=text,
                expansions_applied=[],
            )

        original = text
        expansions: list[dict[str, Any]] = []

        # Step 1: Smart punctuation
        if apply_smart_punctuation:
            text = cls.apply_smart_punctuation(text)

        # Step 2: Short form expansions
        if apply_short_forms:
            transformed, short_expansions = cls.apply_short_forms(text)
            text = transformed
            expansions.extend(short_expansions)

        # Step 3: URL/email normalization
        if apply_url_normalization:
            transformed, url_expansions = cls.normalize_urls_emails(text)
            text = transformed
            expansions.extend(url_expansions)

        # Step 4: Casing corrections
        if apply_casing:
            text = cls.apply_casing_corrections(text)

        # Step 5: User corrections
        if apply_user_corrections and user_corrections_service:
            try:
                text, corrections = user_corrections_service.apply_corrections(
                    text, commit_usage=True
                )
                expansions.extend(
                    [
                        {
                            "type": "user_correction",
                            "original": c["original"],
                            "corrected": c["corrected"],
                        }
                        for c in corrections
                    ]
                )
            except Exception as e:
                logger.warning("Failed to apply user corrections: %s", e)

        # Step 6: Dictionary
        if apply_dictionary and dictionary_service:
            try:
                result = dictionary_service.apply_to_text(text, commit_usage=True)
                if result.applied:
                    text = result.text
                    expansions.extend(
                        [
                            {
                                "type": "dictionary",
                                "phrase": a["phrase"],
                                "replacement": a["replacement"],
                            }
                            for a in result.applied
                        ]
                    )
            except Exception as e:
                logger.warning("Failed to apply dictionary: %s", e)

        # Step 7: Snippets
        if apply_snippets and snippet_service:
            try:
                result = snippet_service.expand_text(text, commit_usage=True)
                if result.applied:
                    text = result.text
                    expansions.extend(
                        [
                            {
                                "type": "snippet",
                                "trigger": a["trigger"],
                                "expansion": a["expansion"],
                            }
                            for a in result.applied
                        ]
                    )
            except Exception as e:
                logger.warning("Failed to apply snippets: %s", e)

        # Final whitespace normalization
        text = cls.normalize_whitespace(text)

        return TextTransformResult(
            original_text=original,
            transformed_text=text,
            expansions_applied=expansions,
        )


def transform_text(
    text: str,
    *,
    apply_smart_punctuation: bool = True,
    apply_short_forms: bool = True,
    apply_url_normalization: bool = True,
    apply_casing: bool = True,
    apply_user_corrections: bool = False,
    apply_dictionary: bool = False,
    apply_snippets: bool = False,
    user_corrections_service=None,
    dictionary_service=None,
    snippet_service=None,
) -> str:
    """Convenience function to transform text.

    Args:
        text: Input text to transform
        (see TextTransformService.transform for other args)

    Returns:
        Transformed text
    """
    result = TextTransformService.transform(
        text,
        apply_smart_punctuation=apply_smart_punctuation,
        apply_short_forms=apply_short_forms,
        apply_url_normalization=apply_url_normalization,
        apply_casing=apply_casing,
        apply_user_corrections=apply_user_corrections,
        apply_dictionary=apply_dictionary,
        apply_snippets=apply_snippets,
        user_corrections_service=user_corrections_service,
        dictionary_service=dictionary_service,
        snippet_service=snippet_service,
    )
    return result.transformed_text
