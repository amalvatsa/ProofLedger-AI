from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import ConfirmedInvoice, PurchaseOrder, Vendor, normalize_invoice_number


MONEY = Decimal("0.01")
ROUNDING_TOLERANCE = Decimal("0.50")


def money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "")).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def money_text(value: Decimal | None) -> str | None:
    return f"{value:.2f}" if value is not None else None


def check(rule_id: str, title: str, outcome: str, detail: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "title": title,
        "outcome": outcome,
        "detail": detail,
        "evidence": evidence or {},
    }


def _find_vendor(session: Session, fields: dict[str, Any]) -> Vendor | None:
    if fields.get("vendor_id"):
        vendor = session.query(Vendor).filter(func.upper(Vendor.vendor_id) == fields["vendor_id"].upper()).first()
        if vendor:
            return vendor
    if fields.get("vendor_name"):
        target = " ".join(fields["vendor_name"].upper().split())
        for vendor in session.query(Vendor).all():
            if " ".join(vendor.name.upper().split()) == target:
                return vendor
    return None


def _committed_net(session: Session, po_number: str) -> Decimal:
    value = (
        session.query(func.coalesce(func.sum(ConfirmedInvoice.net_amount), 0))
        .filter(ConfirmedInvoice.po_number == po_number)
        .scalar()
    )
    return money(value) or Decimal("0.00")


def _field_supported(extraction: dict[str, Any], *field_names: str) -> bool:
    sources = extraction.get("sources") or {}
    for field_name in field_names:
        source = sources.get(field_name)
        if not isinstance(source, dict) or not source.get("page") or not source.get("snippet"):
            return False
    return True


@dataclass
class PolicyResult:
    decision: str
    checks: list[dict[str, Any]]
    explanation: str
    next_action: str
    matched_po_number: str | None
    money: dict[str, str | None]
    vendor_id: str | None
    candidate_pos: list[str]


def evaluate_invoice(session: Session, fields: dict[str, Any], extraction: dict[str, Any]) -> PolicyResult:
    checks: list[dict[str, Any]] = []
    vendor = _find_vendor(session, fields)

    if vendor and vendor.status == "ACTIVE":
        checks.append(
            check(
                "V001_APPROVED_VENDOR",
                "Approved vendor",
                "PASS",
                f"{vendor.name} is active in the approved-vendor master.",
                {"vendor_id": vendor.vendor_id, "source": "vendor master"},
            )
        )
    elif vendor:
        vendor_supported = _field_supported(
            extraction,
            "vendor_name" if fields.get("vendor_name") else "vendor_id",
        )
        checks.append(
            check(
                "V001_APPROVED_VENDOR",
                "Approved vendor",
                "FAIL" if vendor_supported else "REVIEW",
                (
                    f"{vendor.name} is authoritatively marked {vendor.status}; company policy does not permit processing."
                    if vendor_supported
                    else f"{vendor.name} may be inactive, but the invoice identity evidence is not reliable enough to block automatically."
                ),
                {"vendor_id": vendor.vendor_id, "status": vendor.status},
            )
        )
    else:
        checks.append(
            check(
                "V001_APPROVED_VENDOR",
                "Approved vendor",
                "REVIEW",
                "The claimed supplier could not be matched to the approved-vendor master.",
                {"claimed_vendor": fields.get("vendor_name")},
            )
        )

    required = {
        "invoice_number": fields.get("invoice_number"),
        "issue_date": fields.get("issue_date"),
        "vendor": fields.get("vendor_name") or fields.get("vendor_id"),
        "amount": fields.get("gross_total") or fields.get("net_amount"),
        "currency": fields.get("currency"),
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    checks.append(
        check(
            "I001_REQUIRED_FIELDS",
            "Required invoice fields",
            "PASS" if not missing else "REVIEW",
            "All required fields were extracted." if not missing else f"Missing required fields: {', '.join(missing)}.",
            {"missing": missing},
        )
    )

    candidate_pos: list[str] = []
    matched_po: PurchaseOrder | None = None
    po_reference = fields.get("po_reference")
    if po_reference:
        matched_po = session.query(PurchaseOrder).filter(func.upper(PurchaseOrder.po_number) == po_reference.upper()).first()
        if not matched_po:
            po_outcome, po_detail = "REVIEW", f"PO {po_reference} does not exist in the confirmed PO ledger."
        elif not vendor:
            po_outcome, po_detail = "REVIEW", f"PO {matched_po.po_number} exists, but the supplier identity is not verified."
        elif matched_po.vendor_id != vendor.vendor_id:
            reliable_mismatch = _field_supported(
                extraction,
                "po_reference",
                "vendor_name" if fields.get("vendor_name") else "vendor_id",
            )
            po_outcome = "FAIL" if reliable_mismatch else "REVIEW"
            po_detail = (
                f"Verified supplier {vendor.name} conflicts with the authoritative owner of PO {matched_po.po_number}."
                if reliable_mismatch
                else f"PO {matched_po.po_number} may belong to another supplier, but the identity evidence is insufficient to block automatically."
            )
        elif fields.get("currency") != matched_po.currency:
            reliable_currency = _field_supported(extraction, "po_reference", "currency")
            po_outcome = "FAIL" if reliable_currency else "REVIEW"
            po_detail = (
                f"Verified invoice currency {fields.get('currency')} conflicts with {matched_po.currency} on PO {matched_po.po_number}."
                if reliable_currency
                else f"Invoice currency may not match PO {matched_po.po_number}, but the evidence is insufficient to block automatically."
            )
        elif matched_po.status != "OPEN":
            reliable_po = _field_supported(extraction, "po_reference")
            po_outcome = "FAIL" if reliable_po else "REVIEW"
            po_detail = (
                f"PO {matched_po.po_number} is authoritatively marked {matched_po.status} and cannot accept new invoices."
                if reliable_po
                else f"PO {matched_po.po_number} may be closed, but the reference is not reliable enough to block automatically."
            )
        else:
            po_outcome, po_detail = "PASS", f"Exact PO {matched_po.po_number} matches supplier and currency."
    else:
        if vendor:
            candidate_pos = [
                po.po_number
                for po in session.query(PurchaseOrder)
                .filter(PurchaseOrder.vendor_id == vendor.vendor_id, PurchaseOrder.status == "OPEN")
                .order_by(PurchaseOrder.po_number)
                .all()
            ]
        po_outcome = "REVIEW"
        po_detail = "No explicit PO reference was found; a buyer must confirm the matching order."

    checks.append(
        check(
            "P001_PO_MATCH",
            "Purchase order match",
            po_outcome,
            po_detail,
            {"claimed_po": po_reference, "candidate_pos": candidate_pos},
        )
    )

    net = money(fields.get("net_amount"))
    tax = money(fields.get("tax_amount"))
    gross = money(fields.get("gross_total"))
    treatment = (fields.get("tax_treatment") or "UNKNOWN").upper()
    total_outcome = "REVIEW"
    total_detail = "Tax treatment or monetary fields are insufficient for verification."
    difference: Decimal | None = None
    amount_evidence_reliable = _field_supported(extraction, "net_amount", "tax_amount", "gross_total")
    if net is not None and tax is not None and gross is not None and min(net, tax, gross) >= 0:
        difference = abs((net + tax) - gross)
        if treatment in {"EXCLUSIVE", "INCLUSIVE"} and difference <= ROUNDING_TOLERANCE:
            total_outcome = "PASS"
            qualifier = "exclusive tax" if treatment == "EXCLUSIVE" else "included tax"
            total_detail = f"Net plus {qualifier} reconciles to gross within INR {ROUNDING_TOLERANCE:.2f}."
        elif treatment not in {"EXCLUSIVE", "INCLUSIVE"}:
            total_detail = "Tax treatment is unknown, so the total cannot be verified safely."
        else:
            total_outcome = "FAIL" if amount_evidence_reliable else "REVIEW"
            total_detail = f"Net plus tax differs from gross by INR {difference:.2f}."
    elif any(value is not None and value < 0 for value in (net, tax, gross)):
        total_outcome = "FAIL" if amount_evidence_reliable else "REVIEW"
        total_detail = (
            "A source-supported negative monetary value violates invoice policy."
            if amount_evidence_reliable
            else "A possible negative monetary value needs source verification before it can be treated as a policy violation."
        )
    duplicate_supported = _field_supported(
        extraction,
        "invoice_number",
        "vendor_name" if fields.get("vendor_name") else "vendor_id",
    )
    checks.append(
        check(
            "T001_TOTAL_RECONCILIATION",
            "Invoice total reconciliation",
            total_outcome,
            total_detail,
            {
                "net": money_text(net),
                "tax": money_text(tax),
                "gross": money_text(gross),
                "tax_treatment": treatment,
                "difference": money_text(difference),
                "assumption": "Illustrative business check, not Indian tax advice",
            },
        )
    )

    duplicate: ConfirmedInvoice | None = None
    normalized = normalize_invoice_number(fields.get("invoice_number") or "")
    if vendor and normalized:
        duplicate = (
            session.query(ConfirmedInvoice)
            .filter(
                ConfirmedInvoice.vendor_id == vendor.vendor_id,
                ConfirmedInvoice.normalized_invoice_number == normalized,
            )
            .first()
        )
    checks.append(
        check(
            "D001_DUPLICATE",
            "Confirmed invoice duplicate",
            "FAIL" if duplicate and duplicate_supported else "REVIEW" if duplicate else "PASS",
            (
                f"Normalized invoice number matches confirmed {duplicate.invoice_number} from "
                f"{duplicate.confirmed_at.date().isoformat()}; posting again risks a double payment."
                if duplicate and duplicate_supported
                else "A possible ledger duplicate was found, but invoice identity evidence requires human confirmation."
                if duplicate
                else "No same-supplier confirmed invoice has this normalized invoice number."
            ),
            {
                "normalized_invoice_number": normalized or None,
                "previous_invoice": duplicate.invoice_number if duplicate else None,
                "previous_confirmed_at": duplicate.confirmed_at.isoformat() if duplicate else None,
            },
        )
    )

    authorized = committed = remaining = exceeded = None
    budget_outcome = "REVIEW"
    budget_detail = "PO capacity cannot be checked until an exact valid PO and net amount are available."
    if matched_po and po_outcome == "PASS" and net is not None and net >= 0:
        authorized = money(matched_po.authorized_net)
        committed = _committed_net(session, matched_po.po_number)
        remaining = (authorized - committed).quantize(MONEY)
        exceeded = max(net - remaining, Decimal("0.00")).quantize(MONEY)
        if net <= remaining:
            budget_outcome = "PASS"
            budget_detail = (
                f"PO authorizes INR {authorized:.2f}; INR {committed:.2f} is confirmed, leaving "
                f"INR {remaining:.2f} for this INR {net:.2f} net claim."
            )
        else:
            budget_outcome = "FAIL" if _field_supported(extraction, "po_reference", "net_amount") else "REVIEW"
            budget_detail = (
                f"Only INR {remaining:.2f} remains on the PO; the INR {net:.2f} net claim exceeds it by "
                f"INR {exceeded:.2f}."
            )
    checks.append(
        check(
            "B001_PO_REMAINING",
            "Remaining PO capacity",
            budget_outcome,
            budget_detail,
            {
                "authorized_net": money_text(authorized),
                "confirmed_net": money_text(committed),
                "remaining_net": money_text(remaining),
                "requested_net": money_text(net),
                "exceeded_by": money_text(exceeded),
            },
        )
    )

    impossible = any(value is not None and value < 0 for value in (net, tax, gross))
    verified = bool(extraction.get("verified")) and not impossible
    method = extraction.get("method", "unknown")
    diagnostics = extraction.get("diagnostics", [])
    quality_detail = (
        f"{method.upper()} extraction produced a verified field set with page-linked evidence."
        if verified
        else "Extraction evidence is insufficient or contains impossible values; manual review is required."
    )
    checks.append(
        check(
            "X001_EXTRACTION_QUALITY",
            "Extraction quality",
            "PASS" if verified else "REVIEW",
            quality_detail,
            {"method": method, "diagnostics": diagnostics},
        )
    )

    hard_failures = [item for item in checks if item["outcome"] == "FAIL"]
    if hard_failures:
        decision = "BLOCKED"
        failed_ids = {item["rule_id"] for item in hard_failures}
        if "D001_DUPLICATE" in failed_ids and duplicate:
            explanation = "BLOCKED: This supplier and normalized invoice number already exist in the confirmed ledger. Processing again risks a duplicate payment."
            next_action = f"Inspect confirmed invoice {duplicate.invoice_number} before taking any further action."
        elif "B001_PO_REMAINING" in failed_ids and exceeded and exceeded > 0:
            explanation = f"BLOCKED: Invoice exceeds the remaining approved PO budget by INR {exceeded:.2f}."
            next_action = "Request a corrected invoice or verify a formally approved PO amendment before reprocessing."
        elif "T001_TOTAL_RECONCILIATION" in failed_ids:
            explanation = "BLOCKED: Source-supported invoice amounts violate the configured monetary reconciliation policy."
            next_action = "Request a corrected invoice with consistent net, tax, and gross amounts before reprocessing."
        elif "V001_APPROVED_VENDOR" in failed_ids:
            explanation = "BLOCKED: The verified supplier is inactive or prohibited under the configured vendor policy."
            next_action = "Ask an authorized procurement or vendor-management owner to resolve the supplier status before reprocessing."
        else:
            explanation = f"BLOCKED: {hard_failures[0]['detail']}"
            next_action = "Resolve the confirmed policy violation before reprocessing this invoice."
    elif any(item["outcome"] == "REVIEW" for item in checks):
        decision = "NEEDS_REVIEW"
        if exceeded and exceeded > 0:
            explanation = (
                f"The invoice claims net INR {net:.2f}. PO {matched_po.po_number} has INR {remaining:.2f} remaining, "
                f"so this request exceeds authorized capacity by INR {exceeded:.2f}."
            )
            next_action = "Verify a buyer-approved PO increase or request a corrected invoice."
        elif not po_reference:
            explanation = "The invoice does not provide an explicit PO reference, so ProofLedger will not guess which authorization applies."
            next_action = "Ask the buyer to confirm the matching purchase order."
        elif not verified:
            explanation = "The document could not be interpreted with enough verified evidence for a posting recommendation."
            next_action = "Inspect the source document and request a clearer or corrected invoice if needed."
        else:
            failed_titles = [item["title"] for item in checks if item["outcome"] != "PASS"]
            explanation = f"The invoice needs human review because {', '.join(failed_titles).lower()} did not clear."
            next_action = "Resolve the flagged evidence checks before confirming this invoice."
    else:
        decision = "READY_FOR_POSTING"
        explanation = (
            f"The invoice claims net INR {net:.2f}. PO {matched_po.po_number} authorizes INR {authorized:.2f}, "
            f"of which INR {committed:.2f} is already confirmed. The remaining INR {remaining:.2f} covers this claim, "
            "and every required control passed."
        )
        next_action = "Review the evidence receipt, then confirm it in the synthetic demo ledger if appropriate."

    return PolicyResult(
        decision=decision,
        checks=checks,
        explanation=explanation,
        next_action=next_action,
        matched_po_number=matched_po.po_number if matched_po and po_outcome == "PASS" else None,
        money={
            "currency": fields.get("currency"),
            "net": money_text(net),
            "tax": money_text(tax),
            "gross": money_text(gross),
            "authorized": money_text(authorized),
            "committed": money_text(committed),
            "remaining": money_text(remaining),
            "exceeded": money_text(exceeded),
        },
        vendor_id=vendor.vendor_id if vendor else None,
        candidate_pos=candidate_pos,
    )
