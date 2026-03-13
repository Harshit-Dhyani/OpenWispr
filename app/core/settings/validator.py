"""Settings validation pipeline.

Provides comprehensive validation for settings with detailed reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.config.settings import (
    SETTINGS_REGISTRY,
    get_all_categories,
    get_settings_by_category,
    validate_setting,
)


@dataclass
class ValidationError:
    """A single validation error."""

    setting: str
    category: str
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass
class ValidationResult:
    """Result of validating settings."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    unknown_settings: list[str] = field(default_factory=list)
    missing_settings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def get_errors_for_category(self, category: str) -> list[ValidationError]:
        """Get all errors for a specific category."""
        return [e for e in self.errors if e.category == category]

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "errors": [
                {"setting": e.setting, "category": e.category, "message": e.message}
                for e in self.errors
            ],
            "warnings": [
                {"setting": w.setting, "category": w.category, "message": w.message}
                for w in self.warnings
            ],
            "unknown_settings": self.unknown_settings,
            "missing_settings": self.missing_settings,
        }


class SettingsValidator:
    """Comprehensive settings validator with detailed reporting."""

    def __init__(self, strict: bool = False) -> None:
        """Initialize validator.

        Args:
            strict: If True, warnings are treated as errors
        """
        self.strict = strict

    def validate(
        self,
        settings: dict[str, Any],
        check_unknown: bool = True,
        check_missing: bool = False,
    ) -> ValidationResult:
        """Validate a complete settings dictionary.

        Args:
            settings: Nested dict of category -> setting -> value
            check_unknown: Whether to flag unknown settings as errors
            check_missing: Whether to flag missing settings as warnings

        Returns:
            ValidationResult with all errors and warnings
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []
        unknown_settings: list[str] = []
        missing_settings: list[str] = []

        # Get valid categories
        valid_categories = get_all_categories()

        # 1. Check unknown settings and validate known ones
        for category, cat_settings in settings.items():
            # Skip non-category keys (like 'version')
            if category not in valid_categories:
                if check_unknown and category != "version":
                    unknown_settings.append(category)
                    errors.append(
                        ValidationError(
                            setting="",
                            category=category,
                            message=f"Unknown category '{category}'",
                            severity="error",
                        )
                    )
                continue

            # Validate category is a dict
            if not isinstance(cat_settings, dict):
                continue

            category_defns = get_settings_by_category(category)

            # Check for unknown settings in category
            if check_unknown:
                for name in cat_settings:
                    if name not in category_defns:
                        unknown_settings.append(f"{category}.{name}")
                        errors.append(
                            ValidationError(
                                setting=name,
                                category=category,
                                message=f"Unknown setting '{name}' in category '{category}'",
                                severity="error",
                            )
                        )

            # Validate known settings
            for name, value in cat_settings.items():
                if name not in category_defns:
                    continue  # Already flagged as unknown

                valid, error_msg = validate_setting(name, value)
                if not valid:
                    errors.append(
                        ValidationError(
                            setting=name,
                            category=category,
                            message=error_msg,
                            severity="error",
                        )
                    )

        # 3. Check for missing settings
        if check_missing:
            all_categories = {defn.category for defn in SETTINGS_REGISTRY.values()}
            for category in all_categories:
                if category not in settings:
                    missing_settings.append(category)
                    warnings.append(
                        ValidationError(
                            setting="",
                            category=category,
                            message=f"Missing category '{category}'",
                            severity="warning",
                        )
                    )
                else:
                    category_defns = get_settings_by_category(category)
                    for name in category_defns:
                        if name not in settings.get(category, {}):
                            missing_settings.append(f"{category}.{name}")
                            warnings.append(
                                ValidationError(
                                    setting=name,
                                    category=category,
                                    message=f"Missing setting '{name}' in category '{category}'",
                                    severity="warning",
                                )
                            )

        # 4. Check dependencies and cross-setting constraints
        dep_errors = self._check_dependencies(settings)
        errors.extend(dep_errors)

        is_valid = len(errors) == 0
        if self.strict:
            is_valid = is_valid and len(warnings) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            unknown_settings=unknown_settings,
            missing_settings=missing_settings,
        )

    def validate_category(
        self,
        category: str,
        settings: dict[str, Any],
        check_unknown: bool = True,
    ) -> ValidationResult:
        """Validate settings for a single category.

        Args:
            category: Category name
            settings: Dictionary of setting names to values
            check_unknown: Whether to flag unknown settings as errors

        Returns:
            ValidationResult for the category
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []
        unknown_settings: list[str] = []

        category_defns = get_settings_by_category(category)

        # Check unknown settings
        if check_unknown:
            for name in settings:
                if name not in category_defns:
                    unknown_settings.append(name)
                    errors.append(
                        ValidationError(
                            setting=name,
                            category=category,
                            message=f"Unknown setting '{name}'",
                            severity="error",
                        )
                    )

        # Validate known settings
        for name, value in settings.items():
            if name not in category_defns:
                continue

            valid, error_msg = validate_setting(name, value)
            if not valid:
                errors.append(
                    ValidationError(
                        setting=name,
                        category=category,
                        message=error_msg,
                        severity="error",
                    )
                )

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            unknown_settings=unknown_settings,
            missing_settings=[],
        )

    def validate_setting(self, name: str, value: Any) -> ValidationResult:
        """Validate a single setting.

        Args:
            name: Setting name
            value: Value to validate

        Returns:
            ValidationResult for the setting
        """
        errors: list[ValidationError] = []

        if name not in SETTINGS_REGISTRY:
            errors.append(
                ValidationError(
                    setting=name,
                    category="",
                    message=f"Unknown setting: {name}",
                    severity="error",
                )
            )
            return ValidationResult(is_valid=False, errors=errors)

        defn = SETTINGS_REGISTRY[name]
        valid, error_msg = validate_setting(name, value)

        if not valid:
            errors.append(
                ValidationError(
                    setting=name,
                    category=defn.category,
                    message=error_msg,
                    severity="error",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
            unknown_settings=[],
            missing_settings=[],
        )

    def _check_dependencies(
        self,
        settings: dict[str, dict[str, Any]],
    ) -> list[ValidationError]:
        """Check cross-setting dependencies and constraints.

        Args:
            settings: Complete settings dictionary

        Returns:
            List of validation errors for dependency violations
        """
        errors: list[ValidationError] = []

        # Check: chunk_duration should be reasonable with overlap_ratio
        transcription = settings.get("transcription", {})
        chunk_duration = transcription.get("chunk_duration")
        overlap_ratio = transcription.get("overlap_ratio")

        if chunk_duration is not None and overlap_ratio is not None:
            effective_chunk = chunk_duration * (1 - overlap_ratio)
            if effective_chunk < 0.3:
                errors.append(
                    ValidationError(
                        setting="overlap_ratio",
                        category="transcription",
                        message=(
                            f"Effective chunk size ({effective_chunk:.2f}s) is too small. "
                            f"Increase chunk_duration or decrease overlap_ratio."
                        ),
                        severity="warning",
                    )
                )

        # Check: VAD threshold consistency between transcription and audio
        audio = settings.get("audio", {})
        trans_vad_threshold = transcription.get("vad_threshold_db")
        audio_vad_threshold = audio.get("vadThresholdDb")

        if trans_vad_threshold is not None and audio_vad_threshold is not None:
            if abs(trans_vad_threshold - audio_vad_threshold) > 5:
                errors.append(
                    ValidationError(
                        setting="vad_threshold_db",
                        category="transcription",
                        message=(
                            f"VAD threshold mismatch: transcription={trans_vad_threshold}dB, "
                            f"audio={audio_vad_threshold}dB. Consider keeping them consistent."
                        ),
                        severity="warning",
                    )
                )

        return errors

    def sanitize(
        self,
        settings: dict[str, Any],
        fill_defaults: bool = True,
        remove_unknown: bool = False,
    ) -> dict[str, Any]:
        """Sanitize settings by validating and optionally fixing issues.

        Args:
            settings: Settings to sanitize
            fill_defaults: Whether to add missing settings with defaults
            remove_unknown: Whether to remove unknown settings

        Returns:
            Sanitized settings dictionary
        """
        result: dict[str, Any] = {}
        valid_categories = get_all_categories()

        for category, cat_settings in settings.items():
            # Preserve non-category keys (like 'version')
            if category not in valid_categories:
                result[category] = cat_settings
                continue

            # Skip non-dict category values
            if not isinstance(cat_settings, dict):
                continue

            result[category] = {}
            category_defns = get_settings_by_category(category)

            for name, value in cat_settings.items():
                if name not in category_defns:
                    if not remove_unknown:
                        result[category][name] = value
                    continue

                valid, _ = validate_setting(name, value)
                if valid:
                    result[category][name] = value
                else:
                    # Use default if invalid
                    result[category][name] = category_defns[name].default

            # Fill missing settings with defaults
            if fill_defaults:
                for name, defn in category_defns.items():
                    if name not in result[category]:
                        result[category][name] = defn.default

        return result


# Global validator instance
_validator: SettingsValidator | None = None


def get_validator(strict: bool = False) -> SettingsValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = SettingsValidator(strict=strict)
    return _validator
