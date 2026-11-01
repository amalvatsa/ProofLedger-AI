from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="proofledger-tests-"))
os.environ["DATA_DIR"] = str(TEST_DATA_DIR)

from backend.app.db import ConfirmedInvoice, ReviewNote, Run, RunEvent, SessionLocal  # noqa: E402
from backend.app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
    with SessionLocal() as session:
        session.query(ReviewNote).delete()
        session.query(RunEvent).delete()
        session.query(Run).delete()
        session.query(ConfirmedInvoice).filter(ConfirmedInvoice.run_id.is_not(None)).delete()
        session.commit()

