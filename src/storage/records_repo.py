"""Tenant-isolated evidence records repository."""

import json
from datetime import datetime, timezone
from typing import Optional

from src.models.response import (
    EvidenceRecord,
    SubjectInfo,
    CheckResult,
    OutcomeResult,
    ImageRecord,
    OverrideRecord,
    RecordStatus,
)
from src.storage.database import get_db_connection


def _row_to_record(row) -> EvidenceRecord:
    """Convert SQLite Row into an EvidenceRecord domain model."""
    checks_raw = json.loads(row["checks_json"]) if row["checks_json"] else []
    outcome_raw = json.loads(row["outcome_json"]) if row["outcome_json"] else {}
    images_raw = json.loads(row["images_json"]) if row["images_json"] else []
    overrides_raw = json.loads(row["overrides_json"]) if row["overrides_json"] else []

    checks = [CheckResult.model_validate(c) for c in checks_raw]
    outcome = OutcomeResult.model_validate(outcome_raw)
    images = [ImageRecord.model_validate(img) for img in images_raw]
    overrides = [OverrideRecord.model_validate(ovr) for ovr in overrides_raw]

    subject = SubjectInfo(
        unit_id=row["unit_id"],
        order_id=row["order_id"],
        ordered_sku=row["ordered_sku"],
        ordered_asin=row["ordered_asin"],
    )

    return EvidenceRecord(
        record_id=row["record_id"],
        schema_version=row["schema_version"],
        organization_id=row["org_id"],
        client_id=row["client_id"],
        agent=row["agent"],
        subject=subject,
        captured_at=row["captured_at"],
        operator_label=row["operator_id"],
        images=images,
        checks=checks,
        outcome=outcome,
        overrides=overrides,
        status=RecordStatus(row["status"]),
        content_hash=row["content_hash"],
    )


def save_record(record: EvidenceRecord, db_path: Optional[str] = None) -> EvidenceRecord:
    """Save or update an evidence record. Always scoped to record.organization_id."""
    checks_json = json.dumps([c.model_dump(mode="json") for c in record.checks])
    outcome_json = json.dumps(record.outcome.model_dump(mode="json"))
    images_json = json.dumps([img.model_dump(mode="json") for img in record.images])
    overrides_json = json.dumps([ovr.model_dump(mode="json") for ovr in record.overrides])
    now_iso = datetime.now(timezone.utc).isoformat()

    sql = """
    INSERT INTO evidence_records (
        record_id, schema_version, org_id, client_id, agent,
        unit_id, order_id, ordered_sku, ordered_asin, operator_id,
        captured_at, status, content_hash, checks_json, outcome_json,
        images_json, overrides_json, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(record_id) DO UPDATE SET
        schema_version = excluded.schema_version,
        org_id = excluded.org_id,
        client_id = excluded.client_id,
        agent = excluded.agent,
        unit_id = excluded.unit_id,
        order_id = excluded.order_id,
        ordered_sku = excluded.ordered_sku,
        ordered_asin = excluded.ordered_asin,
        operator_id = excluded.operator_id,
        captured_at = excluded.captured_at,
        status = excluded.status,
        content_hash = excluded.content_hash,
        checks_json = excluded.checks_json,
        outcome_json = excluded.outcome_json,
        images_json = excluded.images_json,
        overrides_json = excluded.overrides_json,
        updated_at = excluded.updated_at
    WHERE evidence_records.org_id = excluded.org_id;
    """

    with get_db_connection(db_path) as conn:
        conn.execute(
            sql,
            (
                record.record_id,
                record.schema_version,
                record.organization_id,
                record.client_id,
                record.agent,
                record.subject.unit_id,
                record.subject.order_id,
                record.subject.ordered_sku,
                record.subject.ordered_asin,
                record.operator_label,
                record.captured_at,
                record.status.value,
                record.content_hash,
                checks_json,
                outcome_json,
                images_json,
                overrides_json,
                now_iso,
            ),
        )
        conn.commit()

    return record


def get_record(record_id: str, org_id: str, db_path: Optional[str] = None) -> Optional[EvidenceRecord]:
    """Retrieve an evidence record by record_id and tenant org_id. Cross-tenant access returns None."""
    sql = "SELECT * FROM evidence_records WHERE record_id = ? AND org_id = ?;"
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(sql, (record_id, org_id))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_record(row)


def list_records(
    org_id: str,
    unit_id: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[EvidenceRecord]:
    """List records belonging ONLY to the specified tenant org_id."""
    sql = "SELECT * FROM evidence_records WHERE org_id = ?"
    params: list[str] = [org_id]

    if unit_id:
        sql += " AND unit_id = ?"
        params.append(unit_id)
    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY captured_at DESC;"

    with get_db_connection(db_path) as conn:
        cursor = conn.execute(sql, tuple(params))
        rows = cursor.fetchall()
        return [_row_to_record(r) for r in rows]


def add_override(
    record_id: str,
    org_id: str,
    override: OverrideRecord,
    db_path: Optional[str] = None,
) -> Optional[EvidenceRecord]:
    """Append an override to a record, preserving the original (RULES.md §3.3)."""
    record = get_record(record_id, org_id, db_path=db_path)
    if not record:
        return None

    record.overrides.append(override)
    save_record(record, db_path=db_path)
    return record
