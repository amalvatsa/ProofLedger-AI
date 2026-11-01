#!/usr/bin/env python3
"""Generate genuine synthetic invoice PDFs used by the ProofLedger demo and tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4
NAVY = colors.HexColor("#102A43")
TEAL = colors.HexColor("#178C82")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#829AB1")


def money_lines(invoice: dict[str, str]) -> list[tuple[str, str]]:
    return [
        ("Subtotal (Net)", invoice["net"]),
        ("Tax Amount", invoice["tax"]),
        ("Total (Gross)", invoice["gross"]),
    ]


def draw_layout_one(path: Path, invoice: dict[str, str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(f"Synthetic invoice {invoice.get('invoice_number', 'missing')}")
    pdf.setFillColor(NAVY)
    pdf.rect(0, PAGE_HEIGHT - 125, PAGE_WIDTH, 125, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(48, PAGE_HEIGHT - 62, invoice.get("brand", "ACME"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, PAGE_HEIGHT - 84, "Synthetic business invoice · Demo data only")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawRightString(PAGE_WIDTH - 48, PAGE_HEIGHT - 66, "INVOICE")

    y = PAGE_HEIGHT - 175
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    metadata = [
        ("Vendor", invoice["vendor"]),
        ("Vendor ID", invoice["vendor_id"]),
        ("Invoice Number", invoice.get("invoice_number", "")),
        ("Invoice Date", invoice["date"]),
    ]
    if invoice.get("po"):
        metadata.append(("PO Reference", invoice["po"]))
    metadata.extend([("Currency", "INR"), ("Tax Treatment", invoice["tax_treatment"])])
    for label, value in metadata:
        pdf.setFillColor(MUTED)
        pdf.drawString(48, y, f"{label}:")
        pdf.setFillColor(INK)
        pdf.drawString(165, y, value)
        y -= 23

    y -= 24
    pdf.setFillColor(colors.HexColor("#E8F4F2"))
    pdf.roundRect(42, y - 70, PAGE_WIDTH - 84, 96, 8, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(58, y + 8, "Description:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(145, y + 8, invoice.get("description", "Professional services"))

    y -= 120
    for label, value in money_lines(invoice):
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(INK)
        pdf.drawString(310, y, f"{label}:")
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(PAGE_WIDTH - 48, y, f"INR {value}")
        y -= 28
    if invoice.get("note"):
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(MUTED)
        pdf.drawString(48, 80, f"Note: {invoice['note']}")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(48, 42, "Fictional invoice generated for the ProofLedger AI case-study prototype.")
    pdf.save()


def draw_layout_two(path: Path, invoice: dict[str, str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(f"Synthetic invoice {invoice.get('invoice_number', 'missing')}")
    pdf.setFillColor(colors.HexColor("#F4EEE5"))
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#6B3F2A"))
    pdf.setFont("Times-Bold", 26)
    pdf.drawString(42, PAGE_HEIGHT - 58, invoice.get("brand", "NOVA SUPPLY"))
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(43, PAGE_HEIGHT - 78, "Fictional industrial supplier · Demo data")
    pdf.setStrokeColor(colors.HexColor("#B97745"))
    pdf.setLineWidth(2)
    pdf.line(42, PAGE_HEIGHT - 98, PAGE_WIDTH - 42, PAGE_HEIGHT - 98)

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    left = [
        f"Supplier Name: {invoice['vendor']}",
        f"Supplier ID: {invoice['vendor_id']}",
        f"Invoice No.: {invoice.get('invoice_number', '')}",
        f"Date Issued: {invoice['date']}",
    ]
    right = [f"Currency: INR", f"Tax Treatment: {invoice['tax_treatment']}"]
    if invoice.get("po"):
        right.insert(0, f"Purchase Order: {invoice['po']}")
    y = PAGE_HEIGHT - 140
    for line in left:
        pdf.drawString(48, y, line)
        y -= 24
    y = PAGE_HEIGHT - 140
    for line in right:
        pdf.drawString(330, y, line)
        y -= 24

    y = PAGE_HEIGHT - 285
    pdf.setFillColor(colors.HexColor("#6B3F2A"))
    pdf.rect(42, y, PAGE_WIDTH - 84, 34, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(55, y + 12, "ITEM")
    pdf.drawRightString(PAGE_WIDTH - 55, y + 12, "AMOUNT")
    y -= 36
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(55, y + 10, f"Description: {invoice.get('description', 'Industrial components')}")
    pdf.drawRightString(PAGE_WIDTH - 55, y + 10, f"INR {invoice['net']}")

    y -= 62
    for label, value in money_lines(invoice):
        pdf.setFont("Helvetica", 11)
        pdf.drawString(315, y, f"{label}:")
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(PAGE_WIDTH - 55, y, f"INR {value}")
        y -= 27
    if invoice.get("note"):
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.drawString(48, 72, f"Note: {invoice['note']}")
    pdf.save()


def draw_layout_three(path: Path, invoice: dict[str, str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(f"Synthetic invoice {invoice.get('invoice_number', 'missing')}")
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    pdf.setFillColor(TEAL)
    pdf.circle(65, PAGE_HEIGHT - 66, 25, fill=1, stroke=0)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(105, PAGE_HEIGHT - 58, invoice.get("brand", "ORCHID"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(106, PAGE_HEIGHT - 76, "Synthetic service invoice · Demo data only")
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(PAGE_WIDTH - 42, PAGE_HEIGHT - 58, "TAX INVOICE")

    y = PAGE_HEIGHT - 140
    labels = [
        ("Vendor", invoice["vendor"]),
        ("Vendor ID", invoice["vendor_id"]),
        ("Invoice #", invoice.get("invoice_number", "")),
        ("Invoice Date", invoice["date"]),
    ]
    if invoice.get("po"):
        labels.append(("PO Number", invoice["po"]))
    labels.extend([("Currency", "INR"), ("Tax Treatment", invoice["tax_treatment"])])
    for index, (label, value) in enumerate(labels):
        column = index % 2
        row = index // 2
        x = 48 + column * 270
        row_y = y - row * 54
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x, row_y, label.upper())
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(x, row_y - 18, value)

    y = PAGE_HEIGHT - 365
    pdf.setFillColor(colors.HexColor("#F0F6F6"))
    pdf.roundRect(42, y - 36, PAGE_WIDTH - 84, 62, 10, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(58, y, f"Service: {invoice.get('description', 'Event services')}")

    y -= 92
    for label, value in money_lines(invoice):
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(295, y, f"{label}:")
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(PAGE_WIDTH - 52, y, f"INR {value}")
        y -= 29
    if invoice.get("note"):
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(48, 74, f"Note: {invoice['note']}")
    pdf.save()


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def draw_scanned_invoice(path: Path, invoice: dict[str, str]) -> None:
    width, height = 1654, 2339
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title = _load_font(62, bold=True)
    heading = _load_font(34, bold=True)
    body = _load_font(31)
    bold = _load_font(31, bold=True)
    draw.rectangle((0, 0, width, 260), fill="#143B52")
    draw.text((100, 76), invoice.get("brand", "KITE CREATIVE LABS"), fill="white", font=title)
    draw.text((105, 170), "SCANNED TAX INVOICE · SYNTHETIC DEMO", fill="#C5E8E4", font=body)
    draw.text((1120, 335), "INVOICE", fill="#178C82", font=heading)
    y = 410
    lines = [
        ("Vendor", invoice["vendor"]),
        ("Vendor ID", invoice["vendor_id"]),
        ("Invoice Number", invoice["invoice_number"]),
        ("Invoice Date", invoice["date"]),
        ("PO Reference", invoice["po"]),
        ("Currency", "INR"),
        ("Tax Treatment", invoice["tax_treatment"]),
    ]
    for label, value in lines:
        draw.text((120, y), f"{label}:", fill="#486581", font=bold)
        draw.text((550, y), value, fill="#102A43", font=body)
        y += 72
    y += 60
    draw.rounded_rectangle((100, y, width - 100, y + 170), radius=24, fill="#E8F4F2")
    draw.text((140, y + 50), f"Description: {invoice['description']}", fill="#102A43", font=body)
    y += 275
    for label, value in money_lines(invoice):
        draw.text((720, y), f"{label}:", fill="#486581", font=body)
        draw.text((1270, y), f"INR {value}", fill="#102A43", font=bold)
        y += 78
    draw.text((110, height - 150), "Rasterized source: this page intentionally contains no embedded PDF text.", fill="#829AB1", font=body)

    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle("Synthetic image-only invoice")
    pdf.drawImage(ImageReader(image), 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT, preserveAspectRatio=True, mask="auto")
    pdf.save()


def generate(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    draw_layout_one(
        output_dir / "happy_path.pdf",
        {
            "brand": "ACME OFFICE SYSTEMS",
            "vendor": "Acme Office Systems",
            "vendor_id": "VEND-ACME",
            "invoice_number": "PL-10001",
            "date": "2026-10-21",
            "po": "PO-1001",
            "tax_treatment": "EXCLUSIVE",
            "net": "25000.00",
            "tax": "4500.00",
            "gross": "29500.00",
            "description": "Ergonomic office equipment",
        },
    )
    draw_layout_one(
        output_dir / "duplicate_invoice.pdf",
        {
            "brand": "ACME OFFICE SYSTEMS",
            "vendor": "Acme Office Systems",
            "vendor_id": "VEND-ACME",
            "invoice_number": "inv 2048",
            "date": "2026-10-22",
            "po": "PO-1001",
            "tax_treatment": "EXCLUSIVE",
            "net": "12000.00",
            "tax": "2160.00",
            "gross": "14160.00",
            "description": "Replacement monitor arms",
        },
    )
    draw_layout_two(
        output_dir / "split_po_overspend.pdf",
        {
            "brand": "NOVA INDUSTRIAL SUPPLY",
            "vendor": "Nova Industrial Supplies",
            "vendor_id": "VEND-NOVA",
            "invoice_number": "NOV-3500",
            "date": "2026-10-23",
            "po": "PO-2002",
            "tax_treatment": "EXCLUSIVE",
            "net": "35000.00",
            "tax": "6300.00",
            "gross": "41300.00",
            "description": "Industrial components · shipment 3",
        },
    )
    draw_layout_two(
        output_dir / "split_po_within_balance.pdf",
        {
            "brand": "NOVA INDUSTRIAL SUPPLY",
            "vendor": "Nova Industrial Supplies",
            "vendor_id": "VEND-NOVA",
            "invoice_number": "NOV-3490",
            "date": "2026-10-20",
            "po": "PO-2002",
            "tax_treatment": "EXCLUSIVE",
            "net": "25000.00",
            "tax": "4500.00",
            "gross": "29500.00",
            "description": "Industrial components · shipment 2",
        },
    )
    draw_scanned_invoice(
        output_dir / "scanned_inclusive_tax.pdf",
        {
            "brand": "KITE CREATIVE LABS",
            "vendor": "Kite Creative Labs",
            "vendor_id": "VEND-KITE",
            "invoice_number": "KITE-118",
            "date": "2026-10-24",
            "po": "PO-3001",
            "tax_treatment": "INCLUSIVE",
            "net": "10000.00",
            "tax": "1800.00",
            "gross": "11800.00",
            "description": "Brand design sprint",
        },
    )
    draw_layout_three(
        output_dir / "ambiguous_po.pdf",
        {
            "brand": "ORCHID EVENTS",
            "vendor": "Orchid Events India",
            "vendor_id": "VEND-ORCHID",
            "invoice_number": "ORCH-500",
            "date": "2026-10-25",
            "tax_treatment": "EXCLUSIVE",
            "net": "8000.00",
            "tax": "1440.00",
            "gross": "9440.00",
            "description": "Workshop venue coordination",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "demo_samples")
    arguments = parser.parse_args()
    generate(arguments.output_dir)
    print(f"Generated ProofLedger demo PDFs in {arguments.output_dir.resolve()}")
