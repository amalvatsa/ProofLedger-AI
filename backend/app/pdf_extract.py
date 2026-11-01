from __future__ import annotations

import io
import re
import shutil
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pdfplumber
import pypdfium2 as pdfium
import pytesseract


class ExtractionError(ValueError):
    pass


@dataclass
class PageText:
    page: int
    text: str


FIELD_PATTERNS: dict[str, list[str]] = {
    "invoice_number": [
        r"INVOICE\s*#\s+INVOICE\s*DATE\s*\n([A-Z0-9._/-]+)\s+[0-9]",
        r"(?:invoice\s*(?:number|no\.?|#)|bill\s*number)\s*[:#-]?\s*([A-Z0-9][A-Z0-9 ._/-]{1,40}?)(?=\s+(?:tax\s*treatment|invoice\s*date|currency|po\s|purchase\s*order|date\s*issued)\b|$)",
    ],
    "issue_date": [
        r"INVOICE\s*#\s+INVOICE\s*DATE\s*\n[A-Z0-9._/-]+\s+([0-9]{4}-[0-9]{2}-[0-9]{2})",
        r"(?:invoice\s*date|issue\s*date|date\s*issued)\s*[:#-]?\s*([0-9]{1,4}[./-][0-9]{1,2}[./-][0-9]{1,4})",
    ],
    "vendor_name": [
        r"VENDOR\s+VENDOR\s+ID\s*\n([^\n]+?)\s+VEND-[A-Z0-9-]+",
        r"(?:vendor|supplier)\s*(?:name)?\s*[:#-]\s*([^\n\r]{2,80}?)(?=\s+(?:purchase\s*order|po\s*(?:reference|number|no\.?|#)|currency|vendor\s*id|supplier\s*id|invoice)\b|$)",
    ],
    "vendor_id": [
        r"VENDOR\s+VENDOR\s+ID\s*\n[^\n]+?\s+(VEND-[A-Z0-9-]+)",
        r"(?:vendor|supplier)\s*id\s*[:#-]?\s*([A-Z0-9_-]{3,40})",
    ],
    "po_reference": [
        r"(?:po\s*(?:reference|number|no\.?|#)|purchase\s*order)\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{2,40})",
    ],
    "currency": [
        r"CURRENCY\s+TAX\s+TREATMENT\s*\n([A-Z]{3})\s+",
        r"currency\s*[:#-]?\s*([A-Z]{3})",
    ],
    "tax_treatment": [
        r"CURRENCY\s+TAX\s+TREATMENT\s*\n[A-Z]{3}\s+(EXCLUSIVE|INCLUSIVE|UNKNOWN)",
        r"tax\s*treatment\s*[:#-]?\s*(EXCLUSIVE|INCLUSIVE|UNKNOWN)",
    ],
    "net_amount": [
        r"(?:subtotal\s*(?:\(\s*net\s*\))?|net\s*(?:amount|total|claim))\s*[:#-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]*\.\d{2})",
    ],
    "tax_amount": [
        r"(?:included\s*tax|tax\s*(?:amount|total)?|gst)\s*[:#-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]*\.\d{2})",
    ],
    "gross_total": [
        r"(?:total\s*(?:\(\s*gross\s*\))?|gross\s*total|amount\s*due)\s*[:#-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]*\.\d{2})",
    ],
}


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _clean_capture(value: str) -> str:
    value = value.strip().strip("|;")
    return re.sub(r"\s+", " ", value)


def _valid_amount(value: str | None) -> bool:
    if value is None:
        return False
    try:
        Decimal(value.replace(",", ""))
        return True
    except InvalidOperation:
        return False


def _extract_fields(pages: list[PageText]) -> tuple[dict[str, Any], dict[str, Any]]:
    fields: dict[str, Any] = {
        "invoice_number": None,
        "issue_date": None,
        "vendor_name": None,
        "vendor_id": None,
        "po_reference": None,
        "currency": None,
        "net_amount": None,
        "tax_amount": None,
        "gross_total": None,
        "tax_treatment": "UNKNOWN",
        "line_descriptions": [],
    }
    sources: dict[str, Any] = {}
    for field_name, patterns in FIELD_PATTERNS.items():
        for page in pages:
            for pattern in patterns:
                match = re.search(pattern, page.text, flags=re.IGNORECASE | re.MULTILINE)
                if not match:
                    continue
                value = _clean_capture(match.group(1))
                if field_name in {"currency", "tax_treatment", "vendor_id", "po_reference"}:
                    value = value.upper()
                if field_name in {"net_amount", "tax_amount", "gross_total"}:
                    value = value.replace(",", "")
                fields[field_name] = value
                source_line = next((line.strip() for line in page.text.splitlines() if value.lower() in line.lower()), match.group(0))
                sources[field_name] = {"page": page.page, "snippet": source_line[:180]}
                break
            if fields[field_name] not in (None, "UNKNOWN"):
                break

    descriptions: list[str] = []
    for page in pages:
        for match in re.finditer(r"(?:description|service|item)\s*[:#-]\s*([^\n\r]{3,100})", page.text, re.IGNORECASE):
            descriptions.append(_clean_capture(match.group(1)))
    fields["line_descriptions"] = descriptions[:8]
    return fields, sources


def extract_invoice(path: Path) -> dict[str, Any]:
    diagnostics: list[str] = []
    try:
        with pdfplumber.open(path) as document:
            if not document.pages:
                raise ExtractionError("The PDF contains no pages.")
            pages = [PageText(index + 1, page.extract_text(x_tolerance=2, y_tolerance=3) or "") for index, page in enumerate(document.pages)]
    except ExtractionError:
        raise
    except Exception as error:
        raise ExtractionError(f"The PDF could not be opened safely: {error}") from error

    machine_characters = sum(len(page.text.strip()) for page in pages)
    method = "machine_text"
    if machine_characters < 24:
        method = "ocr"
        if not ocr_available():
            diagnostics.append("OCR_UNAVAILABLE")
        else:
            try:
                pdf = pdfium.PdfDocument(str(path))
                ocr_pages: list[PageText] = []
                for index in range(len(pdf)):
                    image = pdf[index].render(scale=2.4).to_pil().convert("RGB")
                    text = pytesseract.image_to_string(image, config="--psm 6")
                    ocr_pages.append(PageText(index + 1, text))
                pages = ocr_pages
                diagnostics.append("OCR_EXECUTED")
            except Exception as error:
                diagnostics.extend(["OCR_FAILED", str(error)[:160]])

    fields, sources = _extract_fields(pages)
    if method == "ocr" and not any(page.text.strip() for page in pages):
        diagnostics.append("EXTRACTION_UNVERIFIED")

    required_for_verification = (
        fields.get("invoice_number"),
        fields.get("issue_date"),
        fields.get("vendor_name") or fields.get("vendor_id"),
        fields.get("currency"),
        fields.get("net_amount"),
        fields.get("tax_amount"),
        fields.get("gross_total"),
    )
    verified = all(required_for_verification) and all(
        _valid_amount(fields.get(field)) for field in ("net_amount", "tax_amount", "gross_total")
    )
    if not verified and "EXTRACTION_UNVERIFIED" not in diagnostics:
        diagnostics.append("EXTRACTION_UNVERIFIED")

    preview = "\n".join(page.text for page in pages)
    return {
        "method": method,
        "verified": verified,
        "fields": fields,
        "sources": sources,
        "diagnostics": diagnostics,
        "page_count": len(pages),
        "text_preview": preview[:1000],
    }
