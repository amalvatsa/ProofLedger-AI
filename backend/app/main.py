from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .assistant import (
    AssistantProviderError,
    AssistantScopeError,
    AssistantUnavailable,
    assistant_status as get_assistant_status,
    build_invoice_context,
    evidence_references,
    generate_invoice_answer,
    validate_question,
)
from .db import (
    ConfirmedInvoice,
    PurchaseOrder,
    ReviewNote,
    Run,
    RunEvent,
    SessionLocal,
    UPLOAD_DIR,
    Vendor,
    get_db,
    initialize_database,
    normalize_invoice_number,
    utcnow,
)
from .pdf_extract import ExtractionError, extract_invoice, ocr_available
from .policy import evaluate_invoice, money


ROOT_DIR = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT_DIR / "demo_samples"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"application/pdf", "application/octet-stream", "binary/octet-stream"}
DEMO_SAMPLES = {
    "happy_path.pdf": {"label": "Clean happy path", "expected": "READY_FOR_POSTING", "description": "Approved Acme invoice with a valid PO and sufficient remaining balance."},
    "duplicate_invoice.pdf": {"label": "Normalized duplicate", "expected": "BLOCKED", "description": "Formatting variation of a previously confirmed invoice number."},
    "split_po_overspend.pdf": {"label": "Cumulative PO overspend", "expected": "NEEDS_REVIEW", "description": "INR 35,000 claim against only INR 30,000 remaining."},
    "split_po_within_balance.pdf": {"label": "Split PO within balance", "expected": "READY_FOR_POSTING", "description": "INR 25,000 claim that fits inside the remaining PO balance."},
    "scanned_inclusive_tax.pdf": {"label": "Scanned inclusive-tax invoice", "expected": "READY_FOR_POSTING or safe review", "description": "Image-only source that requires genuine local OCR."},
    "ambiguous_po.pdf": {"label": "Missing / ambiguous PO", "expected": "NEEDS_REVIEW", "description": "Supplier has two open POs and the invoice identifies neither."},
}


def json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize_event(event: RunEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "stage": event.stage,
        "outcome": event.outcome,
        "explanation": event.explanation,
        "duration_ms": event.duration_ms,
        "created_at": iso(event.created_at),
    }


def serialize_run(run: Run, include_document_url: bool = True) -> dict[str, Any]:
    extracted = json_load(run.extracted_json, {})
    return {
        "id": run.id,
        "status": run.status,
        "decision": run.decision,
        "original_filename": run.original_filename,
        "file_size": run.file_size,
        "document_hash": run.document_hash,
        "extraction_method": run.extraction_method,
        "extracted": extracted,
        "diagnostics": json_load(run.diagnostics_json, []),
        "checks": json_load(run.checks_json, []),
        "explanation": run.explanation,
        "next_action": run.next_action,
        "money": json_load(run.money_json, {}),
        "matched_po_number": run.matched_po_number,
        "confirmed_at": iso(run.confirmed_at),
        "created_at": iso(run.created_at),
        "updated_at": iso(run.updated_at),
        "events": [serialize_event(event) for event in sorted(run.events, key=lambda item: item.id)],
        "notes": [
            {"id": note.id, "note": note.note, "created_at": iso(note.created_at)}
            for note in sorted(run.notes, key=lambda item: item.id, reverse=True)
        ],
        "document_url": f"/api/runs/{run.id}/document" if include_document_url else None,
    }


def add_event(session: Session, run_id: str, stage: str, outcome: str, explanation: str, duration_ms: int = 0) -> None:
    session.add(
        RunEvent(
            run_id=run_id,
            stage=stage,
            outcome=outcome,
            explanation=explanation,
            duration_ms=max(duration_ms, 0),
        )
    )
    session.commit()


def set_event(session: Session, run_id: str, stage: str, outcome: str, explanation: str, duration_ms: int = 0) -> None:
    event = (
        session.query(RunEvent)
        .filter(RunEvent.run_id == run_id, RunEvent.stage == stage)
        .order_by(RunEvent.id.desc())
        .first()
    )
    if event is None:
        event = RunEvent(run_id=run_id, stage=stage)
        session.add(event)
    event.outcome = outcome
    event.explanation = explanation
    event.duration_ms = max(duration_ms, 0)
    session.commit()


def process_run(run_id: str) -> None:
    with SessionLocal() as session:
        run = session.get(Run, run_id)
        if not run:
            return
        try:
            started = time.perf_counter()
            set_event(
                session,
                run_id,
                "DOCUMENT_READING",
                "PROCESSING",
                "Opening the PDF and reading its page structure.",
            )
            extraction = extract_invoice(
                Path(run.stored_path),
                stage_callback=lambda message: set_event(
                    session,
                    run_id,
                    "DOCUMENT_READING",
                    "PROCESSING",
                    message,
                    int((time.perf_counter() - started) * 1000),
                ),
            )
            run.extraction_method = extraction["method"]
            run.extracted_json = json_dump(
                {
                    "fields": extraction["fields"],
                    "sources": extraction["sources"],
                    "page_count": extraction["page_count"],
                    "validation": extraction["validation"],
                }
            )
            run.diagnostics_json = json_dump(extraction["diagnostics"])
            run.updated_at = utcnow()
            session.commit()
            method_label = {
                "ocr": "local page-image text recognition",
                "hybrid": "layout-aware extraction with source-linked verification",
            }.get(extraction["method"], "embedded PDF text")
            set_event(
                session,
                run_id,
                "DOCUMENT_READING",
                "COMPLETED" if extraction["verified"] else "ATTENTION",
                f"Finished reading {extraction['page_count']} page(s) using {method_label}.",
                int((time.perf_counter() - started) * 1000),
            )
            add_event(
                session,
                run_id,
                "EXTRACTED",
                "COMPLETED" if extraction["verified"] else "ATTENTION",
                f"Read {extraction['page_count']} page(s) using {method_label}; no filename-based routing was used.",
                int((time.perf_counter() - started) * 1000),
            )

            interpreted_at = time.perf_counter()
            fields_present = sum(value not in (None, "", []) for value in extraction["fields"].values())
            add_event(
                session,
                run_id,
                "INTERPRETED",
                "COMPLETED" if extraction["verified"] else "ATTENTION",
                f"Mapped {fields_present} claimed fields into the constrained invoice schema.",
                int((time.perf_counter() - interpreted_at) * 1000),
            )

            validation_passed = bool(extraction["verified"])
            validation_detail = (
                "Field types, page-linked source evidence, and invoice totals passed validation."
                if validation_passed
                else "Some fields, source evidence, or invoice totals could not be verified; the policy engine will require review."
            )
            add_event(
                session,
                run_id,
                "EVIDENCE_VALIDATED",
                "COMPLETED" if validation_passed else "ATTENTION",
                validation_detail,
                0,
            )

            policy_at = time.perf_counter()
            result = evaluate_invoice(session, extraction["fields"], extraction)
            vendor_check = next(item for item in result.checks if item["rule_id"] == "V001_APPROVED_VENDOR")
            add_event(session, run_id, "VENDOR_VALIDATED", vendor_check["outcome"], vendor_check["detail"], 0)
            po_check = next(item for item in result.checks if item["rule_id"] == "P001_PO_MATCH")
            add_event(session, run_id, "PO_MATCHED", po_check["outcome"], po_check["detail"], 0)
            non_pass = [item["rule_id"] for item in result.checks if item["outcome"] != "PASS"]
            add_event(
                session,
                run_id,
                "BUSINESS_RULES_CHECKED",
                "COMPLETED" if not non_pass else "ATTENTION",
                f"All {len(result.checks)} controls passed." if not non_pass else f"Controls requiring attention: {', '.join(non_pass)}.",
                int((time.perf_counter() - policy_at) * 1000),
            )

            run = session.get(Run, run_id)
            run.status = "COMPLETED"
            run.decision = result.decision
            run.checks_json = json_dump(result.checks)
            run.explanation = result.explanation
            run.next_action = result.next_action
            run.money_json = json_dump(result.money)
            run.matched_po_number = result.matched_po_number
            extracted_payload = json_load(run.extracted_json, {})
            extracted_payload["vendor_id"] = result.vendor_id
            extracted_payload["candidate_pos"] = result.candidate_pos
            run.extracted_json = json_dump(extracted_payload)
            run.updated_at = utcnow()
            session.commit()
            add_event(
                session,
                run_id,
                "DECISION_SAVED",
                "COMPLETED",
                f"Saved recommendation {result.decision} with evidence, rule codes, and next action.",
                0,
            )
        except ExtractionError as error:
            set_event(session, run_id, "DOCUMENT_READING", "FAILED", str(error), 0)
            run = session.get(Run, run_id)
            run.status = "FAILED"
            run.decision = None
            run.diagnostics_json = json_dump(["INVALID_OR_UNREADABLE_PDF", str(error)])
            run.explanation = str(error)
            run.next_action = "Upload a valid, non-empty PDF and try again."
            run.updated_at = utcnow()
            session.commit()
            add_event(session, run_id, "EXTRACTION_FAILED", "FAILED", str(error), 0)
        except Exception as error:
            set_event(session, run_id, "DOCUMENT_READING", "FAILED", "Document processing stopped safely.", 0)
            run = session.get(Run, run_id)
            run.status = "FAILED"
            run.diagnostics_json = json_dump(["PROCESSING_ERROR", str(error)[:300]])
            run.explanation = "The invoice could not be processed safely."
            run.next_action = "Inspect the diagnostic and retry with a valid PDF."
            run.updated_at = utcnow()
            session.commit()
            add_event(session, run_id, "PROCESSING_FAILED", "FAILED", str(error)[:300], 0)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="ProofLedger AI",
    version="1.0.0",
    description="Evidence-to-decision invoice processing prototype using synthetic data.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def frontend_cache_headers(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


class NoteRequest(BaseModel):
    note: str = Field(min_length=1, max_length=1200)


class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=500)


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[AssistantChatMessage] = Field(default_factory=list, max_length=8)


@app.get("/api/health")
def health() -> dict[str, Any]:
    ai = get_assistant_status()
    return {
        "status": "ok",
        "database": "sqlite",
        "ocr_available": ocr_available(),
        "ocr_engine": "tesseract" if ocr_available() else None,
        "ai_configured": ai["configured"],
        "ai_provider": ai["provider"],
        "ai_model": ai["model"],
        "demo_data": True,
    }


@app.get("/api/assistant/status")
def assistant_status() -> dict[str, Any]:
    return get_assistant_status()


@app.post("/api/runs", status_code=202)
async def create_run(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form(default="upload"),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    filename = file.filename or "invoice.pdf"
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF uploads are accepted.")
    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="The uploaded file must use a PDF content type.")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF uploads are limited to 10 MB.")
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The file does not contain a valid PDF signature.")

    run_id = str(uuid.uuid4())
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).stem).strip(".-") or "invoice"
    stored_path = UPLOAD_DIR / f"{run_id}-{safe_stem[:80]}.pdf"
    stored_path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    run = Run(
        id=run_id,
        status="PROCESSING",
        original_filename=Path(filename).name[:255],
        stored_path=str(stored_path),
        document_hash=digest,
        file_size=len(payload),
    )
    session.add(run)
    session.commit()
    add_event(
        session,
        run_id,
        "RECEIVED",
        "COMPLETED",
        f"Accepted a {len(payload):,}-byte PDF from {source}; signature, type, and size checks passed.",
        0,
    )
    background_tasks.add_task(process_run, run_id)
    return {"run_id": run_id, "status": "PROCESSING"}


@app.get("/api/runs")
def list_runs(
    decision: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = session.query(Run)
    if decision:
        decisions = [item.strip().upper() for item in decision.split(",") if item.strip()]
        query = query.filter(Run.decision.in_(decisions))
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(or_(Run.original_filename.ilike(token), Run.extracted_json.ilike(token), Run.decision.ilike(token)))
    runs = query.order_by(Run.created_at.desc()).limit(limit).all()
    return [serialize_run(run, include_document_url=False) for run in runs]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return serialize_run(run)


@app.get("/api/runs/{run_id}/document")
def get_document(run_id: str, session: Session = Depends(get_db)) -> FileResponse:
    run = session.get(Run, run_id)
    if not run or not Path(run.stored_path).is_file():
        raise HTTPException(status_code=404, detail="Source document not found.")
    inline_filename = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(run.original_filename).name).strip(".-") or "invoice.pdf"
    return FileResponse(
        run.stored_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{inline_filename}"'},
    )


@app.post("/api/runs/{run_id}/assistant")
def ask_invoice_assistant(
    run_id: str,
    request: AssistantRequest,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status != "COMPLETED" or not run.decision:
        raise HTTPException(status_code=409, detail="The assistant is available after a completed decision receipt exists.")

    try:
        question = validate_question(request.question)
    except AssistantScopeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    status = get_assistant_status()
    if not status["configured"]:
        configuration_error = status.get("configuration_error")
        provider_key = "GEMINI_API_KEY" if status.get("provider_id") == "gemini" else "OPENAI_API_KEY"
        raise HTTPException(
            status_code=503,
            detail=(
                configuration_error
                or f"Invoice AI is not configured. Set {provider_key} and restart the application."
            ),
        )

    context = build_invoice_context(serialize_run(run))
    history = [message.model_dump() for message in request.history]
    started_at = time.perf_counter()
    try:
        answer = generate_invoice_answer(question, history, context)
    except AssistantUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AssistantProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    latency_ms = max(1, round((time.perf_counter() - started_at) * 1000))

    return {
        "answer": answer,
        "evidence": evidence_references(question, context),
        "provider_id": status["provider_id"],
        "provider": status["provider"],
        "model": status["model"],
        "latency_ms": latency_ms,
        "scope": status["scope"],
        "decision_snapshot": run.decision,
    }


@app.post("/api/runs/{run_id}/notes", status_code=201)
def add_review_note(run_id: str, request: NoteRequest, session: Session = Depends(get_db)) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    note = ReviewNote(run_id=run_id, note=request.note.strip())
    session.add(note)
    session.commit()
    session.refresh(note)
    return {"id": note.id, "note": note.note, "created_at": iso(note.created_at)}


@app.post("/api/runs/{run_id}/confirm")
def confirm_run(run_id: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.decision != "READY_FOR_POSTING":
        raise HTTPException(status_code=409, detail="Only an all-clear recommendation can be confirmed to the demo ledger.")
    if run.confirmed_at:
        return {"status": "already_confirmed", "confirmed_at": iso(run.confirmed_at)}

    extracted = json_load(run.extracted_json, {})
    fields = extracted.get("fields", {})
    vendor_id = extracted.get("vendor_id")
    po = session.query(PurchaseOrder).filter(PurchaseOrder.po_number == run.matched_po_number).first()
    net_amount = money(fields.get("net_amount"))
    if not vendor_id or not po or net_amount is None:
        raise HTTPException(status_code=409, detail="The stored evidence is incomplete and cannot be committed.")

    committed = money(
        session.query(func.coalesce(func.sum(ConfirmedInvoice.net_amount), 0))
        .filter(ConfirmedInvoice.po_number == po.po_number)
        .scalar()
    ) or Decimal("0.00")
    remaining = money(po.authorized_net) - committed
    if net_amount > remaining:
        raise HTTPException(status_code=409, detail="PO capacity changed after the recommendation; reprocess the invoice for a current decision.")

    normalized = normalize_invoice_number(fields.get("invoice_number") or "")
    existing = (
        session.query(ConfirmedInvoice)
        .filter(ConfirmedInvoice.vendor_id == vendor_id, ConfirmedInvoice.normalized_invoice_number == normalized)
        .first()
    )
    if existing:
        if existing.run_id == run.id:
            run.confirmed_at = existing.confirmed_at
            session.commit()
            return {"status": "already_confirmed", "confirmed_at": iso(existing.confirmed_at)}
        raise HTTPException(status_code=409, detail="A confirmed invoice now exists with this supplier and normalized invoice number.")

    confirmed_at = utcnow()
    session.add(
        ConfirmedInvoice(
            vendor_id=vendor_id,
            invoice_number=fields["invoice_number"],
            normalized_invoice_number=normalized,
            po_number=po.po_number,
            currency=fields["currency"],
            net_amount=net_amount,
            document_hash=run.document_hash,
            run_id=run.id,
            confirmed_at=confirmed_at,
        )
    )
    run.confirmed_at = confirmed_at
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="The invoice was already confirmed by another request.") from error
    add_event(session, run_id, "CONFIRMED_TO_DEMO_LEDGER", "COMPLETED", "Added one idempotent synthetic ledger confirmation; no ERP or payment action occurred.", 0)
    return {"status": "confirmed", "confirmed_at": iso(confirmed_at)}


@app.get("/api/summary")
def summary(session: Session = Depends(get_db)) -> dict[str, int]:
    rows = dict(session.query(Run.decision, func.count(Run.id)).filter(Run.status == "COMPLETED").group_by(Run.decision).all())
    return {
        "processed": sum(rows.values()),
        "ready": rows.get("READY_FOR_POSTING", 0),
        "needs_review": rows.get("NEEDS_REVIEW", 0),
        "blocked": rows.get("BLOCKED", 0),
    }


@app.get("/api/ledger")
def ledger(session: Session = Depends(get_db)) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for po in session.query(PurchaseOrder).order_by(PurchaseOrder.po_number).all():
        vendor = session.query(Vendor).filter(Vendor.vendor_id == po.vendor_id).first()
        committed = money(
            session.query(func.coalesce(func.sum(ConfirmedInvoice.net_amount), 0))
            .filter(ConfirmedInvoice.po_number == po.po_number)
            .scalar()
        ) or Decimal("0.00")
        authorized = money(po.authorized_net) or Decimal("0.00")
        result.append(
            {
                "po_number": po.po_number,
                "vendor_id": po.vendor_id,
                "vendor_name": vendor.name if vendor else po.vendor_id,
                "currency": po.currency,
                "authorized_net": f"{authorized:.2f}",
                "confirmed_net": f"{committed:.2f}",
                "remaining_net": f"{authorized - committed:.2f}",
                "status": po.status,
                "description": po.description,
            }
        )
    return result


@app.get("/api/demo-samples")
def demo_samples() -> list[dict[str, str]]:
    return [
        {"filename": filename, **metadata}
        for filename, metadata in DEMO_SAMPLES.items()
        if (DEMO_DIR / filename).is_file()
    ]


@app.get("/api/demo-samples/{filename}")
def demo_sample(filename: str) -> FileResponse:
    if filename not in DEMO_SAMPLES:
        raise HTTPException(status_code=404, detail="Demo sample not found.")
    path = DEMO_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Demo sample has not been generated yet.")
    return FileResponse(path, media_type="application/pdf", filename=filename)


FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
