"""
Endpoint tests. Gemini calls are mocked via the mock_gemini fixture —
these tests verify routing, validation, caching, and error handling,
not model output quality.
"""


def test_health_returns_200_with_correct_schema(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "model" in body
    assert "storage_backend" in body


def test_analyze_valid_document_returns_200(client, mock_gemini):
    mock_gemini.return_value = {"ai_summary": "This is a service agreement."}
    resp = client.post(
        "/analyze",
        json={"text": "This agreement shall commence on 01/01/2026 between the parties."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_summary"] == "This is a service agreement."
    assert "disclaimer" in body


def test_analyze_empty_text_rejected_422(client):
    resp = client.post("/analyze", json={"text": ""})
    assert resp.status_code == 422


def test_analyze_text_too_short_rejected_422(client):
    resp = client.post("/analyze", json={"text": "too short"})
    assert resp.status_code == 422


def test_analyze_text_too_long_rejected_422(client):
    resp = client.post("/analyze", json={"text": "x" * 50_001})
    assert resp.status_code == 422


def test_simplify_valid_returns_200(client, mock_gemini):
    mock_gemini.return_value = {
        "plain_english": "This means you must pay rent on time.",
        "key_points": ["Pay rent monthly", "Give 30 days notice to leave"],
    }
    resp = client.post(
        "/simplify",
        json={"text": "The tenant shall remit payment on the first day of each calendar month."},
    )
    assert resp.status_code == 200
    assert "plain_english" in resp.json()


def test_simplify_with_focus_returns_200(client, mock_gemini):
    mock_gemini.return_value = {
        "plain_english": "Focused explanation about payment terms.",
        "key_points": ["Point one"],
    }
    resp = client.post(
        "/simplify",
        json={
            "text": "The tenant shall remit payment via bank transfer within five business days.",
            "focus": "payment terms",
        },
    )
    assert resp.status_code == 200


def test_ask_valid_returns_200(client, mock_gemini):
    mock_gemini.return_value = {"answer": "Yes, the lease auto-renews.", "confidence": "high"}
    resp = client.post(
        "/ask",
        json={
            "text": "This lease automatically renews for successive one-year terms.",
            "question": "Does this lease auto-renew?",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["confidence"] == "high"


def test_ask_empty_question_rejected_422(client):
    resp = client.post(
        "/ask",
        json={"text": "This lease automatically renews for successive one-year terms.", "question": ""},
    )
    assert resp.status_code == 422


def test_compare_valid_returns_200(client, mock_gemini):
    mock_gemini.return_value = {
        "ai_comparison": "Document A is more favourable to the tenant.",
        "key_differences": ["A has lower penalties"],
        "recommendation": "Choose Document A.",
    }
    resp = client.post(
        "/compare",
        json={
            "doc_a": "This is the first agreement text regarding services rendered.",
            "doc_b": "This is the second agreement text regarding services rendered.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "doc_a_structural" in body
    assert "doc_b_structural" in body


def test_compare_missing_doc_b_rejected_422(client):
    resp = client.post(
        "/compare",
        json={"doc_a": "This is the first agreement text regarding services rendered."},
    )
    assert resp.status_code == 422


def test_summarize_valid_returns_200(client, mock_gemini):
    mock_gemini.return_value = {
        "executive_summary": "A standard NDA between two companies.",
        "key_points": ["Confidentiality lasts 5 years"],
        "important_clauses": ["Confidentiality"],
        "action_items": ["Sign and return by Friday"],
    }
    resp = client.post(
        "/summarize",
        json={"text": "This non-disclosure agreement is entered into by both parties on this date."},
    )
    assert resp.status_code == 200


def test_prepare_valid_returns_200(client, mock_gemini):
    mock_gemini.return_value = {
        "document_summary": "An employment contract.",
        "questions_for_lawyer": ["What happens if I am terminated early?"],
        "checklist": ["Bring a copy of your offer letter"],
        "red_flags": ["Non-compete clause is broad"],
    }
    resp = client.post(
        "/prepare",
        json={"text": "This employment agreement contains a non-compete clause lasting two years."},
    )
    assert resp.status_code == 200


def test_gemini_failure_returns_502(client, mock_gemini):
    mock_gemini.side_effect = Exception("upstream failure")
    resp = client.post(
        "/analyze",
        json={"text": "A unique document text used only for the failure test case here."},
    )
    assert resp.status_code == 502


def test_document_history_save_list_get_delete_roundtrip(client, mock_gemini):
    mock_gemini.return_value = {
        "plain_english": "History roundtrip test explanation.",
        "key_points": ["Point one"],
    }
    resp = client.post(
        "/simplify",
        json={"text": "This unique history-roundtrip document text is used only here."},
    )
    assert resp.status_code == 200

    listing = client.get("/documents")
    assert listing.status_code == 200
    docs = listing.json()
    assert any("history-roundtrip" in d["preview"] for d in docs)
    doc_id = next(d["id"] for d in docs if "history-roundtrip" in d["preview"])

    detail = client.get(f"/documents/{doc_id}")
    assert detail.status_code == 200
    assert "history-roundtrip" in detail.json()["text"]

    deleted = client.delete(f"/documents/{doc_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/documents/{doc_id}")
    assert missing.status_code == 404


def test_analyze_cached_on_second_call(client, mock_gemini):
    mock_gemini.return_value = {"ai_summary": "Cached summary test."}
    payload = {"text": "This unique cache-test document is used only in this test function."}
    first = client.post("/analyze", json=payload)
    assert first.status_code == 200
    assert mock_gemini.call_count == 1

    second = client.post("/analyze", json=payload)
    assert second.status_code == 200
    assert mock_gemini.call_count == 1  # no second Gemini call — served from cache
    assert second.json() == first.json()
