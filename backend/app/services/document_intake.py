"""The route-facing side of upload screening: reads the configured mode,
applies app/services/document_validation.py to an incoming file, and turns
the outcome into either an HTTP 422 (refuse) or the fields to store on the
document row.

Used by both the insurance-application and financing upload paths so the
two behave identically.
"""

import asyncio
from dataclasses import dataclass
from typing import Iterable, Protocol

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.document_requirements import SPECS
from app.services.document_validation import STATUS_OK, STATUS_REVIEW, validate_document


class _ExistingDoc(Protocol):
    document_type: str
    file_hash: str | None


@dataclass
class IntakeOutcome:
    status: str
    notes: str | None
    file_hash: str | None


def _label(document_type: str) -> str:
    spec = SPECS.get(document_type)
    return spec.label if spec else document_type.replace("_", " ")


async def screen_upload(
    document_type: str, filename: str, content: bytes, existing: Iterable[_ExistingDoc]
) -> IntakeOutcome:
    """Raises HTTPException(422) in strict mode when the file should be
    refused; otherwise returns what to store.

    The checks (PDF parsing, image analysis, optional OCR) are CPU-bound and
    can take seconds, so they run in a worker thread - otherwise one
    customer's upload would freeze every other request the server is
    handling."""
    mode = (get_settings().document_validation or "strict").lower()
    if mode == "off":
        return IntakeOutcome(STATUS_OK, None, None)

    result = await asyncio.to_thread(validate_document, document_type, filename, content)
    problem = result.message if not result.ok else None
    notes = result.notes
    new_status = result.status

    # The same file under two different document types is almost always a
    # mistake (one scan uploaded for both the ID and the logbook).
    if problem is None:
        for doc in existing:
            if doc.file_hash and doc.file_hash == result.file_hash and doc.document_type != document_type:
                problem = (
                    f"This exact file was already uploaded as your {_label(doc.document_type)}. "
                    f"Each document needs its own file - please upload your {_label(document_type)} here."
                )
                notes = "Duplicate of a file already uploaded as a different document type."
                break

    if problem is not None:
        if mode == "strict":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
        # lenient: keep it, but flag it for staff
        return IntakeOutcome(STATUS_REVIEW, (notes or problem)[:500], result.file_hash)

    return IntakeOutcome(new_status, (notes[:500] if notes else None), result.file_hash)
