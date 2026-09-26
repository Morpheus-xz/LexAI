"""Pydantic validation tests — the shared validator, exercised through
each model that uses it."""

import pytest
from pydantic import ValidationError

from app.models import AskRequest, CompareRequest, DocumentInput, SimplifyRequest


def test_document_input_rejects_blank_text():
    with pytest.raises(ValidationError):
        DocumentInput(text="")


def test_document_input_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        DocumentInput(text="                    ")


def test_document_input_rejects_text_too_long():
    with pytest.raises(ValidationError):
        DocumentInput(text="x" * 50_001)


def test_ask_request_rejects_blank_question():
    with pytest.raises(ValidationError):
        AskRequest(
            text="This is a perfectly valid piece of legal document text for testing.",
            question="   ",
        )


def test_compare_request_rejects_blank_doc_a():
    with pytest.raises(ValidationError):
        CompareRequest(
            doc_a="   ",
            doc_b="This is a perfectly valid piece of legal document text for testing.",
        )


def test_simplify_focus_field_is_optional():
    req = SimplifyRequest(text="This is a perfectly valid piece of legal document text.")
    assert req.focus is None
