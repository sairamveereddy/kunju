from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr


DB_PATH = Path(os.environ.get("LICENSE_DB", "licenses.sqlite3"))
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change-me-before-live")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me-before-live")
MAX_ACTIVATIONS = int(os.environ.get("MAX_ACTIVATIONS", "1"))

app = FastAPI(title="Privacy Alarm License Server")


class VerifyRequest(BaseModel):
    license_key: str
    machine_id: str
    app_id: str = "SairamPrivacyAlarm"


class CreateLicenseRequest(BaseModel):
    email: EmailStr | None = None
    provider: str = "manual"
    order_id: str | None = None


class PaymentWebhookRequest(BaseModel):
    email: EmailStr
    provider: str
    order_id: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                license_key TEXT PRIMARY KEY,
                email TEXT,
                provider TEXT NOT NULL,
                order_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                activated_at TEXT NOT NULL,
                UNIQUE(license_key, machine_id)
            )
            """
        )


def require_secret(value: str | None, expected: str) -> None:
    if not value or not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def generate_license_key() -> str:
    return "PAL-" + secrets.token_urlsafe(24).replace("_", "").replace("-", "").upper()[:24]


def create_license(email: str | None, provider: str, order_id: str | None) -> str:
    key = generate_license_key()
    with connect() as db:
        db.execute(
            """
            INSERT INTO licenses (license_key, email, provider, order_id, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (key, email, provider, order_id, utc_now()),
        )
    return key


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/license/verify")
def verify_license(payload: VerifyRequest) -> dict[str, object]:
    init_db()
    with connect() as db:
        license_row = db.execute(
            "SELECT * FROM licenses WHERE license_key = ?",
            (payload.license_key.strip(),),
        ).fetchone()

        if not license_row or license_row["status"] != "active":
            return {"valid": False, "reason": "inactive_or_missing"}

        existing = db.execute(
            "SELECT * FROM activations WHERE license_key = ? AND machine_id = ?",
            (payload.license_key, payload.machine_id),
        ).fetchone()
        if existing:
            return {"valid": True, "status": "active"}

        count = db.execute(
            "SELECT COUNT(*) AS count FROM activations WHERE license_key = ?",
            (payload.license_key,),
        ).fetchone()["count"]
        if count >= MAX_ACTIVATIONS:
            return {"valid": False, "reason": "activation_limit_reached"}

        db.execute(
            """
            INSERT INTO activations (license_key, machine_id, activated_at)
            VALUES (?, ?, ?)
            """,
            (payload.license_key, payload.machine_id, utc_now()),
        )
        return {"valid": True, "status": "activated"}


@app.post("/api/admin/licenses")
def admin_create_license(
    payload: CreateLicenseRequest,
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, str | None]:
    require_secret(x_admin_secret, ADMIN_SECRET)
    key = create_license(payload.email, payload.provider, payload.order_id)
    return {"license_key": key, "email": payload.email}


@app.post("/api/webhooks/payment")
def payment_webhook(
    payload: PaymentWebhookRequest,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, str]:
    require_secret(x_webhook_secret, WEBHOOK_SECRET)
    key = create_license(payload.email, payload.provider, payload.order_id)
    return {"license_key": key}
