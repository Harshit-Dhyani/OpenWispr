"""Text transformation and correction API endpoints.

Provides APIs for applying text transformations including short form expansions,
user corrections, dictionary lookups, and snippet expansion to transcripts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.services.dictionary_service import DictionaryService
from app.api.services.snippet_service import SnippetService
from app.api.services.text_transform_service import TextTransformService
from app.api.services.user_corrections_service import UserCorrectionsService
from app.api.deps import get_dictionary_service, get_snippet_service, get_history_db
from app.storage.history_db import HistoryDatabase

router = APIRouter()


def get_user_corrections_service(
    db: HistoryDatabase = Depends(get_history_db),
) -> UserCorrectionsService:
    """Get user corrections service."""
    return UserCorrectionsService(db)


@router.post("/api/text/transform")
def transform_text(
    text: str = Query(..., min_length=0, max_length=10000),
    apply_smart_punctuation: bool = Query(True),
    apply_short_forms: bool = Query(True),
    apply_url_normalization: bool = Query(True),
    apply_casing: bool = Query(True),
    apply_user_corrections: bool = Query(True),
    apply_dictionary: bool = Query(True),
    apply_snippets: bool = Query(True),
    svc_dictionary: DictionaryService | None = Depends(get_dictionary_service),
    svc_snippets: SnippetService | None = Depends(get_snippet_service),
    svc_corrections: UserCorrectionsService | None = Depends(get_user_corrections_service),
) -> dict:
    """Apply text transformations including short forms, dictionary, snippets, and user corrections.

    This endpoint transforms text in real-time by applying:
    1. Smart punctuation (adds punctuation based on speech patterns)
    2. Short form expansions (e.g., "asap" -> "as soon as possible")
    3. URL/email normalization (lowercase URLs and emails)
    4. Casing corrections (e.g., "api" -> "API")
    5. User corrections (learned from previous corrections)
    6. Dictionary replacements (user-defined word substitutions)
    7. Snippet expansions (user-defined trigger expansions)

    Args:
        text: Input text to transform
        apply_smart_punctuation: Add smart punctuation
        apply_short_forms: Apply common short form expansions
        apply_url_normalization: Normalize URLs/emails to lowercase
        apply_casing: Apply acronym casing corrections
        apply_user_corrections: Apply learned corrections
        apply_dictionary: Apply dictionary replacements
        apply_snippets: Apply snippet expansions

    Returns:
        Transformed text with list of applied expansions
    """
    if not text:
        return {
            "original": text,
            "transformed": text,
            "expansions": [],
        }

    result = TextTransformService.transform(
        text,
        apply_smart_punctuation=apply_smart_punctuation,
        apply_short_forms=apply_short_forms,
        apply_url_normalization=apply_url_normalization,
        apply_casing=apply_casing,
        apply_user_corrections=apply_user_corrections,
        apply_dictionary=apply_dictionary,
        apply_snippets=apply_snippets,
        user_corrections_service=svc_corrections,
        dictionary_service=svc_dictionary,
        snippet_service=svc_snippets,
    )

    return {
        "original": result.original_text,
        "transformed": result.transformed_text,
        "expansions": result.expansions_applied,
    }


@router.post("/api/corrections")
def record_correction(
    original_text: str = Query(..., min_length=1),
    corrected_text: str = Query(..., min_length=1),
    context: str | None = Query(None),
    correction_type: str = Query("manual"),
    svc: UserCorrectionsService = Depends(get_user_corrections_service),
) -> dict:
    """Record a user correction for future auto-application.

    Use this to teach the system corrections you make frequently.

    Args:
        original_text: The original (incorrect) text
        corrected_text: The corrected version
        context: Optional context (e.g., "code", "email")
        correction_type: Type of correction ("manual", "dictionary", "snippet")

    Returns:
        The created correction record
    """
    if correction_type not in ("manual", "dictionary", "snippet"):
        raise HTTPException(
            status_code=400, detail="correction_type must be 'manual', 'dictionary', or 'snippet'"
        )

    correction = svc.record_correction(
        original_text=original_text,
        corrected_text=corrected_text,
        context=context,
        correction_type=correction_type,
    )

    return {
        "id": correction.id,
        "original_text": correction.original_text,
        "corrected_text": correction.corrected_text,
        "context": correction.context,
        "correction_type": correction.correction_type,
        "apply_count": correction.apply_count,
        "created_at": correction.created_at,
    }


@router.get("/api/corrections")
def list_corrections(
    search: str | None = Query(None),
    correction_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    svc: UserCorrectionsService = Depends(get_user_corrections_service),
) -> dict:
    """List user corrections with optional filtering."""
    corrections = svc.list_corrections(
        search=search,
        correction_type=correction_type,
        limit=limit,
    )

    return {
        "corrections": [
            {
                "id": c.id,
                "original_text": c.original_text,
                "corrected_text": c.corrected_text,
                "context": c.context,
                "correction_type": c.correction_type,
                "apply_count": c.apply_count,
                "last_applied_at": c.last_applied_at,
                "created_at": c.created_at,
            }
            for c in corrections
        ]
    }


@router.delete("/api/corrections/{correction_id}")
def delete_correction(
    correction_id: str,
    svc: UserCorrectionsService = Depends(get_user_corrections_service),
) -> dict:
    """Delete a specific correction."""
    deleted = svc.delete_correction(correction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Correction not found")
    return {"deleted": correction_id}


@router.delete("/api/corrections")
def clear_corrections(
    svc: UserCorrectionsService = Depends(get_user_corrections_service),
) -> dict:
    """Clear all manual corrections."""
    count = svc.clear_all_corrections()
    return {"cleared": count}


@router.get("/api/corrections/export")
def export_corrections(
    svc: UserCorrectionsService = Depends(get_user_corrections_service),
) -> str:
    """Export corrections as JSON."""
    return svc.export_corrections()


@router.post("/api/corrections/import")
def import_corrections(
    json_data: str = Query(...),
    svc: UserCorrectionsService = Depends(get_user_corrections_service),
) -> dict:
    """Import corrections from JSON."""
    try:
        result = svc.import_corrections(json_data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
