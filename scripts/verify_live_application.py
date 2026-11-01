#!/usr/bin/env python3
"""Exercise every featured ProofLedger PDF against a running application."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "demo_samples"
BASE_URL = os.getenv("PROOFLEDGER_URL", "http://127.0.0.1:8000").rstrip("/")
EVENT_STAGES = [
    "RECEIVED",
    "EXTRACTED",
    "INTERPRETED",
    "VENDOR_VALIDATED",
    "PO_MATCHED",
    "BUSINESS_RULES_CHECKED",
    "DECISION_SAVED",
]


CASES: list[dict[str, Any]] = [
    {
        "file": "happy_path.pdf",
        "decision": "READY_FOR_POSTING",
        "method": "machine_text",
        "money": {"net": "25000.00", "tax": "4500.00", "gross": "29500.00", "authorized": "120000.00", "committed": "45000.00", "remaining": "75000.00", "exceeded": "0.00"},
        "checks": {"B001_PO_REMAINING": "PASS", "D001_DUPLICATE": "PASS"},
    },
    {
        "file": "duplicate_invoice.pdf",
        "decision": "BLOCKED",
        "method": "machine_text",
        "money": {"net": "12000.00", "tax": "2160.00", "gross": "14160.00"},
        "checks": {"D001_DUPLICATE": "FAIL"},
        "previous_invoice": "INV-2048",
    },
    {
        "file": "split_po_overspend.pdf",
        "decision": "NEEDS_REVIEW",
        "method": "machine_text",
        "money": {"net": "35000.00", "tax": "6300.00", "gross": "41300.00", "authorized": "100000.00", "committed": "70000.00", "remaining": "30000.00", "exceeded": "5000.00"},
        "checks": {"B001_PO_REMAINING": "REVIEW"},
    },
    {
        "file": "scanned_inclusive_tax.pdf",
        "decision": "READY_FOR_POSTING",
        "method": "ocr",
        "money": {"net": "10000.00", "tax": "1800.00", "gross": "11800.00", "authorized": "50000.00", "committed": "0.00", "remaining": "50000.00", "exceeded": "0.00"},
        "checks": {"T001_TOTAL_RECONCILIATION": "PASS", "X001_EXTRACTION_QUALITY": "PASS"},
        "diagnostic": "OCR_EXECUTED",
        "tax_treatment": "INCLUSIVE",
    },
    {
        "file": "ambiguous_po.pdf",
        "decision": "NEEDS_REVIEW",
        "method": "machine_text",
        "money": {"net": "8000.00", "tax": "1440.00", "gross": "9440.00"},
        "checks": {"P001_PO_MATCH": "REVIEW"},
        "candidate_pos": ["PO-4001", "PO-4002"],
    },
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_map(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["rule_id"]: item for item in run["checks"]}


def wait_for_run(client: httpx.Client, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        if run["status"] != "PROCESSING":
            return run
        time.sleep(0.2)
    raise AssertionError(f"Run {run_id} did not complete within 30 seconds")


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=45) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        health_data = health.json()
        require(health_data["status"] == "ok", "Health endpoint is not OK")
        require(health_data["ocr_available"] is True, "Featured OCR success case requires Tesseract")

        summary_before = client.get("/api/summary").json()
        ledger_before = client.get("/api/ledger").json()
        run_ids: dict[str, str] = {}

        for case in CASES:
            path = SAMPLES / case["file"]
            payload = path.read_bytes()
            require(payload.startswith(b"%PDF-"), f"{path.name} lacks a PDF signature")
            response = client.post(
                "/api/runs",
                files={"file": (path.name, payload, "application/pdf")},
                data={"source": "live-verification"},
            )
            require(response.status_code == 202, f"{path.name} upload returned {response.status_code}: {response.text}")
            run = wait_for_run(client, response.json()["run_id"])
            run_ids[path.name] = run["id"]

            require(run["status"] == "COMPLETED", f"{path.name} status was {run['status']}")
            require(run["decision"] == case["decision"], f"{path.name} decision {run['decision']} != {case['decision']}")
            require(run["extraction_method"] == case["method"], f"{path.name} extraction method was {run['extraction_method']}")
            require([event["stage"] for event in run["events"]] == EVENT_STAGES, f"{path.name} event sequence was incomplete")
            require(all(event["created_at"] for event in run["events"]), f"{path.name} has an event without a timestamp")
            require(len(run["checks"]) == 7, f"{path.name} did not save all seven checks")
            require(run["explanation"] and run["next_action"], f"{path.name} receipt lacks explanation or next action")
            require(run["document_hash"] == hashlib.sha256(payload).hexdigest(), f"{path.name} hash did not come from uploaded bytes")

            document = client.get(run["document_url"])
            require(document.status_code == 200 and document.content == payload, f"{path.name} persisted document differs from uploaded bytes")

            for key, expected in case["money"].items():
                require(run["money"].get(key) == expected, f"{path.name} money.{key}={run['money'].get(key)} != {expected}")
            checks = check_map(run)
            for rule_id, expected in case["checks"].items():
                require(checks[rule_id]["outcome"] == expected, f"{path.name} {rule_id} outcome was {checks[rule_id]['outcome']}")

            if case.get("previous_invoice"):
                require(checks["D001_DUPLICATE"]["evidence"]["previous_invoice"] == case["previous_invoice"], "Duplicate evidence did not reference the confirmed invoice")
            if case.get("diagnostic"):
                require(case["diagnostic"] in run["diagnostics"], f"{path.name} lacks {case['diagnostic']}")
            if case.get("tax_treatment"):
                require(run["extracted"]["fields"]["tax_treatment"] == case["tax_treatment"], f"{path.name} tax treatment was incorrect")
            if case.get("candidate_pos"):
                require(run["matched_po_number"] is None, "Ambiguous invoice incorrectly selected a PO")
                require(run["extracted"]["candidate_pos"] == case["candidate_pos"], "Ambiguous PO candidates were incorrect")

            print(f"PASS {path.name}: {run['decision']} · {run['extraction_method']} · 7 events · 7 checks")

        summary_after = client.get("/api/summary").json()
        expected_delta = {"processed": 5, "ready": 2, "needs_review": 2, "blocked": 1}
        actual_delta = {key: summary_after[key] - summary_before[key] for key in expected_delta}
        require(actual_delta == expected_delta, f"Summary delta {actual_delta} != {expected_delta}")

        history = client.get("/api/runs", params={"limit": 200}).json()
        history_ids = {item["id"] for item in history}
        require(set(run_ids.values()).issubset(history_ids), "One or more live runs are missing from history")

        review_queue = client.get("/api/runs", params={"decision": "NEEDS_REVIEW,BLOCKED", "limit": 200}).json()
        review_ids = {item["id"] for item in review_queue}
        expected_review_ids = {run_ids["duplicate_invoice.pdf"], run_ids["split_po_overspend.pdf"], run_ids["ambiguous_po.pdf"]}
        require(expected_review_ids.issubset(review_ids), "Featured exceptions are missing from the review queue")

        ledger_after = client.get("/api/ledger").json()
        require(ledger_after == ledger_before, "Recommendations changed confirmed PO commitments")

        reopened = client.get(f"/api/runs/{run_ids['scanned_inclusive_tax.pdf']}").json()
        require(reopened["decision"] == "READY_FOR_POSTING" and reopened["events"][-1]["stage"] == "DECISION_SAVED", "Saved OCR receipt did not persist")

        print(f"PASS summary delta: {actual_delta}")
        print("PASS persistence: all run IDs in history; saved OCR receipt reopened")
        print("PASS review queue: duplicate, over-budget, and ambiguous-PO runs present")
        print("PASS ledger immutability: recommendations consumed zero PO capacity")
        print(f"LIVE VERIFICATION PASSED at {BASE_URL}")


if __name__ == "__main__":
    main()
