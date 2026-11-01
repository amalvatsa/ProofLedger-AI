from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data" / "runtime")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
SEED_DIR = ROOT_DIR / "data" / "seed"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    authorized_net: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    description: Mapped[str] = mapped_column(String(250), default="")

    vendor: Mapped[Vendor] = relationship(back_populates="purchase_orders")


class ConfirmedInvoice(Base):
    __tablename__ = "confirmed_invoices"
    __table_args__ = (
        UniqueConstraint("vendor_id", "normalized_invoice_number", name="uq_confirmed_vendor_invoice"),
        Index("ix_confirmed_po", "po_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(100))
    normalized_invoice_number: Mapped[str] = mapped_column(String(100), index=True)
    po_number: Mapped[str] = mapped_column(ForeignKey("purchase_orders.po_number"))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    document_hash: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_created_decision", "created_at", "decision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="PROCESSING", index=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    document_hash: Mapped[str] = mapped_column(String(128), index=True)
    file_size: Mapped[int] = mapped_column()
    extraction_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extracted_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    checks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    money_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_po_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    events: Mapped[list["RunEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    notes: Mapped[list["ReviewNote"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_run_id_id", "run_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(24))
    explanation: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="events")


class ReviewNote(Base):
    __tablename__ = "review_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="notes")


engine = create_engine(
    f"sqlite:///{DATA_DIR / 'proofledger.db'}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def normalize_invoice_number(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        if session.query(Vendor).count() > 0:
            return

        with (SEED_DIR / "vendors.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                session.add(Vendor(**row))
        session.flush()

        with (SEED_DIR / "purchase_orders.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                session.add(
                    PurchaseOrder(
                        po_number=row["po_number"],
                        vendor_id=row["vendor_id"],
                        currency=row["currency"],
                        authorized_net=Decimal(row["authorized_net"]),
                        status=row["status"],
                        description=row["description"],
                    )
                )
        session.flush()

        with (SEED_DIR / "confirmed_invoices.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                session.add(
                    ConfirmedInvoice(
                        vendor_id=row["vendor_id"],
                        invoice_number=row["invoice_number"],
                        normalized_invoice_number=normalize_invoice_number(row["invoice_number"]),
                        po_number=row["po_number"],
                        currency=row["currency"],
                        net_amount=Decimal(row["net_amount"]),
                        document_hash=row["document_hash"],
                        confirmed_at=datetime.fromisoformat(row["confirmed_at"].replace("Z", "+00:00")),
                    )
                )
        session.commit()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

