from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from backend.app import pdf_extract
from scripts.generate_demo_data import draw_layout_one


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "demo_samples"


def evidence(value: str | None, page: int | None, snippet: str | None) -> dict[str, Any]:
    return {"value": value, "page": page, "snippet": snippet}


def draw_unfamiliar_invoice(path: Path, layout: str = "portrait", gross: str = "1180.00") -> None:
    page_size = landscape(A4) if layout == "landscape" else A4
    pdf = canvas.Canvas(str(path), pagesize=page_size)
    width, height = page_size
    pdf.setTitle("Unfamiliar synthetic billing statement")

    if layout == "portrait":
        pdf.setFillColor(colors.HexColor("#243447"))
        pdf.rect(0, height - 112, width, 112, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawString(42, height - 55, "ACME | BILLING RECORD")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, height - 77, "Synthetic test document - layout intentionally differs from known templates")
        lines = [
            "Merchant identity  Acme Office Systems",
            "Merchant code  VEND-ACME",
            "Document key  FLEX-2026-014",
            "Raised on  29 Oct 2026",
            "Order link  PO-1001",
            "Denomination  INR",
            "Tax handling  EXCLUSIVE",
            "Work supplied  Workspace configuration services",
            "Pre-tax value  1000.00",
            "GST levy  180.00",
            f"Settlement value  {gross}",
        ]
        pdf.setFillColor(colors.HexColor("#1F2937"))
        y = height - 165
        for index, line in enumerate(lines):
            if index == 8:
                y -= 22
                pdf.setStrokeColor(colors.HexColor("#CBD5E1"))
                pdf.line(42, y + 12, width - 42, y + 12)
            pdf.setFont("Helvetica-Bold" if index in {2, 10} else "Helvetica", 11)
            pdf.drawString(48, y, line)
            y -= 31
    else:
        pdf.setFillColor(colors.HexColor("#F3F0EA"))
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#60452E"))
        pdf.setFont("Times-Bold", 26)
        pdf.drawString(48, height - 58, "COMMERCIAL ACCOUNT MEMO")
        pdf.setFont("Helvetica", 11)
        metadata = [
            "Trading party: Acme Office Systems",
            "Account marker: VEND-ACME",
            "Record token: FLEX-2026-014",
            "Prepared: 29 Oct 2026",
            "Authorization link: PO-1001",
            "Book currency: INR",
            "Tax basis: EXCLUSIVE",
        ]
        y = height - 110
        for line in metadata:
            pdf.drawString(55, y, line)
            y -= 28
        pdf.showPage()
        pdf.setFillColor(colors.HexColor("#183B56"))
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(52, height - 60, "CHARGES AND SETTLEMENT")
        pdf.setFont("Helvetica", 12)
        totals = [
            "Activity supplied: Workspace configuration services",
            "Value before levy: 1000.00",
            "Indirect levy: 180.00",
            f"Amount for settlement: {gross}",
        ]
        y = height - 118
        for line in totals:
            pdf.drawString(58, y, line)
            y -= 38
    pdf.save()


def fallback_payload(layout: str = "portrait", gross: str = "1180.00") -> dict[str, Any]:
    metadata_page = 1
    amount_page = 2 if layout == "landscape" else 1
    labels = {
        "invoice_number": "Record token: FLEX-2026-014" if layout == "landscape" else "Document key FLEX-2026-014",
        "issue_date": "Prepared: 29 Oct 2026" if layout == "landscape" else "Raised on 29 Oct 2026",
        "vendor_name": "Trading party: Acme Office Systems" if layout == "landscape" else "Merchant identity Acme Office Systems",
        "vendor_id": "Account marker: VEND-ACME" if layout == "landscape" else "Merchant code VEND-ACME",
        "po_reference": "Authorization link: PO-1001" if layout == "landscape" else "Order link PO-1001",
        "currency": "Book currency: INR" if layout == "landscape" else "Denomination INR",
        "tax_treatment": "Tax basis: EXCLUSIVE" if layout == "landscape" else "Tax handling EXCLUSIVE",
        "net_amount": "Value before levy: 1000.00" if layout == "landscape" else "Pre-tax value 1000.00",
        "tax_amount": "Indirect levy: 180.00" if layout == "landscape" else "GST levy 180.00",
        "gross_total": f"Amount for settlement: {gross}" if layout == "landscape" else f"Settlement value {gross}",
    }
    return {
        "fields": {
            "invoice_number": evidence("FLEX-2026-014", metadata_page, labels["invoice_number"]),
            "issue_date": evidence("29 Oct 2026", metadata_page, labels["issue_date"]),
            "vendor_name": evidence("Acme Office Systems", metadata_page, labels["vendor_name"]),
            "vendor_id": evidence("VEND-ACME", metadata_page, labels["vendor_id"]),
            "po_reference": evidence("PO-1001", metadata_page, labels["po_reference"]),
            "currency": evidence("INR", metadata_page, labels["currency"]),
            "net_amount": evidence("1000.00", amount_page, labels["net_amount"]),
            "tax_amount": evidence("180.00", amount_page, labels["tax_amount"]),
            "gross_total": evidence(gross, amount_page, labels["gross_total"]),
            "tax_treatment": evidence("EXCLUSIVE", metadata_page, labels["tax_treatment"]),
        },
        "line_descriptions": [
            evidence(
                "Workspace configuration services",
                amount_page,
                "Activity supplied: Workspace configuration services" if layout == "landscape" else "Work supplied Workspace configuration services",
            )
        ],
    }


def mock_gemini(monkeypatch, payload: dict[str, Any] | None = None, status_code: int = 200, raw_text: str | None = None):
    captured: dict[str, Any] = {}
    real_client = pdf_extract.httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("x-goog-api-key")
        if status_code != 200:
            return httpx.Response(status_code, request=request, json={"error": {"message": "synthetic failure"}})
        text = raw_text if raw_text is not None else json.dumps(payload)
        return httpx.Response(
            200,
            request=request,
            json={"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]},
        )

    monkeypatch.setattr(
        pdf_extract.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    return captured


@pytest.mark.parametrize("layout", ["portrait", "landscape"])
def test_structured_fallback_extracts_unfamiliar_multi_format_layouts(tmp_path, monkeypatch, layout):
    path = tmp_path / f"unfamiliar-{layout}.pdf"
    draw_unfamiliar_invoice(path, layout)
    deterministic = pdf_extract.extract_invoice(path)
    assert deterministic["verified"] is False
    assert deterministic["validation"]["fallback_attempted"] is False

    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-extraction-key")
    captured = mock_gemini(monkeypatch, fallback_payload(layout))
    stages: list[str] = []

    result = pdf_extract.extract_invoice(path, stages.append)

    assert result["method"] == "hybrid"
    assert result["verified"] is True
    assert result["fields"]["invoice_number"] == "FLEX-2026-014"
    assert result["fields"]["issue_date"] == "2026-10-29"
    assert result["fields"]["gross_total"] == "1180.00"
    assert result["sources"]["gross_total"]["method"] == "structured_fallback"
    assert result["validation"]["totals_reconciled"] is True
    assert result["validation"]["fallback_accepted_fields"] >= 9
    assert "STRUCTURED_FALLBACK_USED" in result["diagnostics"]
    assert any("unfamiliar layout" in stage for stage in stages)
    request = captured["request"]
    assert captured["api_key"] == "test-extraction-key"
    assert request["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "application/pdf"
    assert request["generationConfig"]["responseMimeType"] == "application/json"
    assert request["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
    assert request["generationConfig"]["maxOutputTokens"] == pdf_extract.GEMINI_MAX_OUTPUT_TOKENS
    assert request["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "MINIMAL"


def test_fallback_rejects_invented_values_without_source_evidence(tmp_path, monkeypatch):
    path = tmp_path / "invented.pdf"
    draw_unfamiliar_invoice(path)
    payload = fallback_payload()
    payload["fields"]["invoice_number"] = evidence("INVENTED-999", 1, "Document key FLEX-2026-014")
    payload["fields"]["net_amount"] = evidence("999999.00", 1, "Pre-tax value 1000.00")
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-extraction-key")
    mock_gemini(monkeypatch, payload)

    result = pdf_extract.extract_invoice(path)

    assert result["verified"] is False
    assert result["fields"]["invoice_number"] is None
    assert result["fields"]["net_amount"] is None
    assert "INVENTED-999" not in json.dumps(result)
    assert "STRUCTURED_FALLBACK_EVIDENCE_REJECTED_INVOICE_NUMBER" in result["diagnostics"]
    assert "EXTRACTION_UNVERIFIED" in result["diagnostics"]


@pytest.mark.parametrize(
    ("status_code", "raw_text", "diagnostic"),
    [
        (503, None, "STRUCTURED_FALLBACK_PROVIDER_UNAVAILABLE"),
        (200, "not valid json", "STRUCTURED_FALLBACK_INVALID_RESPONSE"),
    ],
)
def test_fallback_provider_and_output_failures_fail_closed(tmp_path, monkeypatch, status_code, raw_text, diagnostic):
    path = tmp_path / "provider-failure.pdf"
    draw_unfamiliar_invoice(path)
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-extraction-key")
    mock_gemini(monkeypatch, status_code=status_code, raw_text=raw_text)

    result = pdf_extract.extract_invoice(path)

    assert result["verified"] is False
    assert diagnostic in result["diagnostics"]
    assert "EXTRACTION_UNVERIFIED" in result["diagnostics"]


@pytest.mark.parametrize(
    ("status_code", "provider_error", "diagnostic"),
    [
        (401, {"status": "UNAUTHENTICATED"}, "STRUCTURED_FALLBACK_CREDENTIAL_REJECTED"),
        (404, {"status": "NOT_FOUND"}, "STRUCTURED_FALLBACK_MODEL_UNAVAILABLE"),
        (429, {"status": "RESOURCE_EXHAUSTED", "message": "Free tier quota exceeded"}, "STRUCTURED_FALLBACK_QUOTA_EXHAUSTED"),
        (429, {"status": "RATE_LIMITED", "message": "Too many requests"}, "STRUCTURED_FALLBACK_RATE_LIMITED"),
        (400, {"status": "INVALID_ARGUMENT"}, "STRUCTURED_FALLBACK_CONFIGURATION_REJECTED"),
    ],
)
def test_provider_http_failures_have_actionable_diagnostics(status_code, provider_error, diagnostic):
    request = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(status_code, request=request, json={"error": provider_error})
    error = httpx.HTTPStatusError("synthetic", request=request, response=response)

    assert pdf_extract._structured_fallback_http_diagnostic(error) == diagnostic


def test_malformed_provider_envelope_is_treated_as_invalid_output(tmp_path, monkeypatch):
    path = tmp_path / "malformed-envelope.pdf"
    draw_unfamiliar_invoice(path)
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-extraction-key")
    real_client = pdf_extract.httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"candidates": ["unexpected"]})

    monkeypatch.setattr(
        pdf_extract.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    result = pdf_extract.extract_invoice(path)

    assert result["verified"] is False
    assert "STRUCTURED_FALLBACK_INVALID_RESPONSE" in result["diagnostics"]
    assert "EXTRACTION_UNVERIFIED" in result["diagnostics"]


def test_structured_response_normalizes_omitted_null_fields_and_json_fence():
    partial = {
        "fields": {
            "invoice_number": evidence("INV-100", 1, "Document ref INV-100"),
        }
    }
    response = {
        "candidates": [
            {
                "content": {"parts": [{"text": f"```json\n{json.dumps(partial)}\n```"}]},
                "finishReason": "STOP",
            }
        ]
    }

    candidate, error = pdf_extract._parse_structured_candidate(response)

    assert error is None
    assert candidate is not None
    assert candidate["fields"]["invoice_number"]["value"] == "INV-100"
    assert candidate["fields"]["issue_date"] == {"value": None, "page": None, "snippet": None}
    assert candidate["line_descriptions"] == []


def test_structured_response_reports_output_truncation():
    candidate, error = pdf_extract._parse_structured_candidate(
        {"candidates": [{"content": {"parts": [{"text": "{"}]}, "finishReason": "MAX_TOKENS"}]}
    )

    assert candidate is None
    assert error == "STRUCTURED_FALLBACK_OUTPUT_TRUNCATED"


def test_tax_pattern_does_not_cross_from_treatment_label_to_net_amount(tmp_path):
    path = tmp_path / "tax-treatment-and-net.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(48, 760, "Tax treatment: EXCLUSIVE")
    pdf.drawString(48, 730, "Supply value before tax 8000.00")
    pdf.drawString(48, 700, "Tax component 1440.00")
    pdf.save()

    result = pdf_extract.extract_invoice(path)

    assert result["fields"]["tax_amount"] == "1440.00"
    assert result["sources"]["tax_amount"]["snippet"] == "Tax component 1440.00"


def test_gross_pattern_does_not_match_total_inside_subtotal(tmp_path):
    path = tmp_path / "subtotal-is-not-gross.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(48, 760, "Supplier subtotal 7000.00")
    pdf.drawString(48, 730, "Tax on supply 1260.00")
    pdf.drawString(48, 700, "Payable as stated 9650.00")
    pdf.save()

    result = pdf_extract.extract_invoice(path)

    assert result["fields"]["net_amount"] == "7000.00"
    assert result["fields"]["gross_total"] is None


def test_amount_evidence_accepts_ocr_joined_label_and_number():
    assert pdf_extract._amount_appears_in_snippet("6000.00", "Goods and services value6000.00") is True


def test_unreconciled_model_totals_are_never_marked_verified(tmp_path, monkeypatch):
    path = tmp_path / "bad-total.pdf"
    draw_unfamiliar_invoice(path, gross="1200.00")
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-extraction-key")
    mock_gemini(monkeypatch, fallback_payload(gross="1200.00"))

    result = pdf_extract.extract_invoice(path)

    assert result["fields"]["gross_total"] == "1200.00"
    assert result["validation"]["totals_reconciled"] is False
    assert result["verified"] is False
    assert "TOTALS_UNVERIFIED" in result["diagnostics"]


@pytest.mark.parametrize(
    ("failure_mode", "expected_decision", "expected_total_outcome"),
    [
        ("provider", "NEEDS_REVIEW", "REVIEW"),
        ("unreconciled", "BLOCKED", "FAIL"),
    ],
)
def test_fallback_failures_follow_evidence_aware_policy(
    client, tmp_path, monkeypatch, failure_mode, expected_decision, expected_total_outcome
):
    gross = "1200.00" if failure_mode == "unreconciled" else "1180.00"
    path = tmp_path / f"policy-{failure_mode}.pdf"
    draw_unfamiliar_invoice(path, gross=gross)
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-extraction-key")
    if failure_mode == "provider":
        mock_gemini(monkeypatch, status_code=503)
    else:
        mock_gemini(monkeypatch, fallback_payload(gross=gross))

    with path.open("rb") as handle:
        response = client.post(
            "/api/runs",
            files={"file": (path.name, handle, "application/pdf")},
            data={"source": "pytest-structured-fallback"},
        )
    assert response.status_code == 202
    run = client.get(f"/api/runs/{response.json()['run_id']}").json()

    assert run["status"] == "COMPLETED"
    assert run["decision"] == expected_decision
    extraction_check = next(item for item in run["checks"] if item["rule_id"] == "X001_EXTRACTION_QUALITY")
    assert extraction_check["outcome"] == "REVIEW"
    total_check = next(item for item in run["checks"] if item["rule_id"] == "T001_TOTAL_RECONCILIATION")
    assert total_check["outcome"] == expected_total_outcome
    validation_event = next(item for item in run["events"] if item["stage"] == "EVIDENCE_VALIDATED")
    assert validation_event["outcome"] == "ATTENTION"


def test_complete_deterministic_samples_do_not_call_fallback(monkeypatch):
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-used")

    class UnexpectedClient:
        def __init__(self, **_kwargs):
            raise AssertionError("Gemini must not run for a complete deterministic extraction")

    monkeypatch.setattr(pdf_extract.httpx, "Client", UnexpectedClient)
    for filename in (
        "happy_path.pdf",
        "duplicate_invoice.pdf",
        "split_po_overspend.pdf",
        "split_po_within_balance.pdf",
        "ambiguous_po.pdf",
    ):
        result = pdf_extract.extract_invoice(SAMPLES / filename)
        assert result["verified"] is True, filename
        assert result["method"] == "machine_text", filename
        assert result["validation"]["fallback_attempted"] is False, filename


def test_fallback_never_rewrites_complete_fields_to_fix_a_failed_financial_control(tmp_path, monkeypatch):
    path = tmp_path / "deterministic-total-mismatch.pdf"
    draw_layout_one(
        path,
        {
            "brand": "ACME OFFICE SYSTEMS",
            "vendor": "Acme Office Systems",
            "vendor_id": "VEND-ACME",
            "invoice_number": "CONTROL-FAIL-1",
            "date": "2026-10-29",
            "po": "PO-1001",
            "tax_treatment": "EXCLUSIVE",
            "net": "1000.00",
            "tax": "180.00",
            "gross": "1200.00",
            "description": "Control failure must remain deterministic",
        },
    )
    monkeypatch.setenv("PROOFLEDGER_GEMINI_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-used")

    class UnexpectedClient:
        def __init__(self, **_kwargs):
            raise AssertionError("Gemini must not repair a deterministic total mismatch")

    monkeypatch.setattr(pdf_extract.httpx, "Client", UnexpectedClient)

    result = pdf_extract.extract_invoice(path)

    assert result["fields"]["gross_total"] == "1200.00"
    assert result["validation"]["fallback_attempted"] is False
    assert result["validation"]["totals_reconciled"] is False
    assert result["verified"] is False


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("issue_date", "04/05/2026"),
        ("issue_date", "31/02/2026"),
        ("currency", "RUPEES"),
        ("tax_amount", "18.123"),
        ("gross_total", "not-a-number"),
        ("tax_treatment", "probably exclusive"),
    ],
)
def test_model_field_types_are_validated_before_policy(field_name, value):
    assert pdf_extract._normalize_field_value(field_name, value) is None


def test_negative_amount_is_preserved_for_source_supported_policy_blocking():
    assert pdf_extract._normalize_field_value("net_amount", "-100.00") == "-100.00"
