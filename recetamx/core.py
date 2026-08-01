from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

UTC = timezone.utc
SCHEMA_VERSION = "receta-mx-alpha-0.1.0"
from .catalog import CATALOG, CATALOG_VERSION, DEMO_CATALOG

PROFESSIONS = {
    "MEDICO",
    "MEDICO_HOMEOPATA",
    "CIRUJANO_DENTISTA",
    "MEDICO_VETERINARIO",
    "LIC_ENFERMERIA",
    "PASANTE",
}
SALE_FRACTIONS = {"I", "II", "III", "IV", "V", "VI"}
CONTROLLED_GROUPS = {
    "NONE",
    "ESTUPEFACIENTE",
    "PSICOTROPICO_II",
    "PSICOTROPICO_III",
    "PSICOTROPICO_IV",
}

INTERACTION_RULES = [
    ({"WARFARINA", "IBUPROFENO"}, "ALTA", "Mayor riesgo de sangrado; valorar alternativa y vigilancia."),
    ({"WARFARINA", "NAPROXENO"}, "ALTA", "Mayor riesgo de sangrado; valorar alternativa y vigilancia."),
    ({"SIMVASTATINA", "CLARITROMICINA"}, "ALTA", "Riesgo de miopatía/rabdomiólisis; revisar combinación."),
    ({"SILDENAFIL", "NITROGLICERINA"}, "CONTRAINDICADA", "Riesgo de hipotensión grave."),
    ({"METFORMINA", "MEDIO DE CONTRASTE YODADO"}, "MODERADA", "Revisar función renal y suspensión temporal según contexto."),
]

MEDICATION_WARNINGS = {
    "WARFARINA": ["Medicamento de margen terapéutico estrecho; requiere vigilancia clínica y de INR."],
    "ISOTRETINOINA": ["Alto riesgo teratogénico; requiere medidas estrictas de prevención de embarazo."],
    "METOTREXATO": ["Confirmar periodicidad: errores de dosificación diaria pueden causar toxicidad grave."],
    "INSULINA": ["Riesgo de hipoglucemia; verificar presentación, concentración y dispositivo."],
    "MORFINA": ["Opioide: riesgo de depresión respiratoria, sedación y dependencia."],
}


class RecetaMXError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_name(value: str) -> str:
    return " ".join((value or "").strip().upper().split())


def hash_password(password: str, salt: str | None = None) -> str:
    if not password or len(password) < 8:
        raise RecetaMXError("La contraseña debe tener al menos 8 caracteres.")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hash_password(password, salt).split("$", 2)[2]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_prescriber_number(profession: str) -> str:
    prefixes = {
        "MEDICO": "MED",
        "MEDICO_HOMEOPATA": "HOM",
        "CIRUJANO_DENTISTA": "DEN",
        "MEDICO_VETERINARIO": "VET",
        "LIC_ENFERMERIA": "ENF",
        "PASANTE": "PAS",
    }
    numeric = str(secrets.randbelow(10**10)).zfill(10)
    return f"MXP-{prefixes[profession]}-{numeric}"


def generate_folio() -> str:
    return f"RXMX-{datetime.now(UTC).year}-{uuid.uuid4().hex[:12].upper()}"


def connect(db_path: str | os.PathLike[str]) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS prescribers (
            id TEXT PRIMARY KEY,
            prescriber_number TEXT NOT NULL UNIQUE,
            curp TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            profession TEXT NOT NULL,
            professional_license TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            verification_state TEXT NOT NULL,
            efirma_certificate_serial TEXT,
            efirma_fingerprint TEXT,
            liveness_check TEXT NOT NULL,
            ai_review TEXT NOT NULL,
            manual_review TEXT NOT NULL,
            attributes_json TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pharmacies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            license_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            attributes_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pharmacy_users (
            id TEXT PRIMARY KEY,
            pharmacy_id TEXT NOT NULL REFERENCES pharmacies(id),
            curp TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            identifier_type TEXT NOT NULL,
            identifier_value TEXT NOT NULL,
            full_name TEXT NOT NULL,
            birth_date TEXT,
            sex TEXT,
            access_code_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(identifier_type, identifier_value)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prescriptions (
            id TEXT PRIMARY KEY,
            folio TEXT NOT NULL UNIQUE,
            verification_token_hash TEXT NOT NULL,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            prescriber_id TEXT NOT NULL REFERENCES prescribers(id),
            status TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            diagnosis_code TEXT,
            clinical_note TEXT,
            public_origin INTEGER NOT NULL DEFAULT 0,
            fulfillment_route TEXT NOT NULL,
            payer_type TEXT NOT NULL,
            transfer_reason TEXT,
            warnings_json TEXT NOT NULL,
            interactions_json TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            catalog_version TEXT NOT NULL,
            signature_alg TEXT NOT NULL,
            signature_value TEXT NOT NULL,
            original_payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prescription_items (
            id TEXT PRIMARY KEY,
            prescription_id TEXT NOT NULL REFERENCES prescriptions(id),
            line_no INTEGER NOT NULL,
            code TEXT,
            generic_name TEXT NOT NULL,
            brand_requested TEXT,
            form TEXT NOT NULL,
            strength TEXT NOT NULL,
            dose TEXT NOT NULL,
            route TEXT NOT NULL,
            frequency TEXT NOT NULL,
            duration_days INTEGER,
            quantity_prescribed REAL NOT NULL,
            quantity_dispensed REAL NOT NULL DEFAULT 0,
            sale_fraction TEXT NOT NULL,
            controlled_group TEXT NOT NULL,
            refills_authorized INTEGER NOT NULL DEFAULT 0,
            refills_used INTEGER NOT NULL DEFAULT 0,
            substitution_allowed INTEGER NOT NULL DEFAULT 1,
            warnings_json TEXT NOT NULL,
            UNIQUE(prescription_id, line_no)
        );

        CREATE TABLE IF NOT EXISTS dispenses (
            id TEXT PRIMARY KEY,
            prescription_id TEXT NOT NULL REFERENCES prescriptions(id),
            pharmacy_id TEXT NOT NULL REFERENCES pharmacies(id),
            pharmacy_user_id TEXT NOT NULL REFERENCES pharmacy_users(id),
            dispensed_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            is_public_transfer INTEGER NOT NULL DEFAULT 0,
            claim_status TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS dispense_items (
            id TEXT PRIMARY KEY,
            dispense_id TEXT NOT NULL REFERENCES dispenses(id),
            prescription_item_id TEXT NOT NULL REFERENCES prescription_items(id),
            quantity REAL NOT NULL,
            brand TEXT NOT NULL,
            lot_number TEXT NOT NULL,
            expiration_date TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            details_json TEXT NOT NULL
        );
        """
    )
    conn.commit()


def audit(
    conn: sqlite3.Connection,
    actor_type: str,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            now_iso(),
            actor_type,
            actor_id,
            action,
            resource_type,
            resource_id,
            canonical_json(details or {}),
        ),
    )


def validate_operator_key(provided: str | None, configured: str) -> None:
    if not provided or not hmac.compare_digest(provided, configured):
        raise RecetaMXError("Credencial de operador inválida.", 401, "operator_auth_failed")


def create_prescriber(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    profession = (data.get("profession") or "").upper()
    if profession not in PROFESSIONS:
        raise RecetaMXError(f"Profesión no admitida: {profession}")
    required = ["curp", "full_name", "professional_license", "phone", "password"]
    for field in required:
        if not data.get(field):
            raise RecetaMXError(f"Falta el campo {field}.")

    attributes = data.get("attributes") or {
        "can_prescribe_general": True,
        "allowed_controlled_groups": [],
        "allowed_drug_codes": [],
        "scope": "HUMAN",
    }
    state = data.get("verification_state", "PENDING")
    checks = {
        "liveness_check": data.get("liveness_check", "PENDING"),
        "ai_review": data.get("ai_review", "PENDING"),
        "manual_review": data.get("manual_review", "PENDING"),
    }
    prescriber_id = str(uuid.uuid4())
    number = generate_prescriber_number(profession)
    try:
        conn.execute(
            """
            INSERT INTO prescribers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prescriber_id,
                number,
                normalize_name(data["curp"]),
                normalize_name(data["full_name"]),
                profession,
                str(data["professional_license"]).strip(),
                str(data["phone"]).strip(),
                (data.get("email") or "").strip() or None,
                state,
                data.get("efirma_certificate_serial"),
                data.get("efirma_fingerprint"),
                checks["liveness_check"],
                checks["ai_review"],
                checks["manual_review"],
                canonical_json(attributes),
                hash_password(data["password"]),
                now_iso(),
            ),
        )
        audit(conn, "OPERATOR", None, "prescriber.created", "prescriber", prescriber_id, {"state": state})
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise RecetaMXError("La CURP o el número de prescriptor ya existe.", 409, "duplicate_prescriber") from exc
    return {
        "id": prescriber_id,
        "prescriber_number": number,
        "verification_state": state,
        "attributes": attributes,
    }


def create_pharmacy(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    for field in ("name", "license_number"):
        if not data.get(field):
            raise RecetaMXError(f"Falta el campo {field}.")
    pharmacy_id = str(uuid.uuid4())
    try:
        conn.execute(
            "INSERT INTO pharmacies VALUES (?, ?, ?, ?, ?, ?)",
            (
                pharmacy_id,
                normalize_name(data["name"]),
                str(data["license_number"]).strip(),
                data.get("status", "ACTIVE"),
                canonical_json(data.get("attributes") or {}),
                now_iso(),
            ),
        )
        audit(conn, "OPERATOR", None, "pharmacy.created", "pharmacy", pharmacy_id, {})
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise RecetaMXError("La licencia de farmacia ya existe.", 409, "duplicate_pharmacy") from exc
    return {"id": pharmacy_id, "status": data.get("status", "ACTIVE")}


def create_pharmacy_user(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    for field in ("pharmacy_id", "curp", "full_name", "password"):
        if not data.get(field):
            raise RecetaMXError(f"Falta el campo {field}.")
    pharmacy = conn.execute("SELECT id, status FROM pharmacies WHERE id=?", (data["pharmacy_id"],)).fetchone()
    if not pharmacy or pharmacy["status"] != "ACTIVE":
        raise RecetaMXError("Farmacia no encontrada o inactiva.", 404, "pharmacy_not_active")
    user_id = str(uuid.uuid4())
    try:
        conn.execute(
            "INSERT INTO pharmacy_users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                data["pharmacy_id"],
                normalize_name(data["curp"]),
                normalize_name(data["full_name"]),
                data.get("role", "DISPENSER"),
                data.get("status", "ACTIVE"),
                hash_password(data["password"]),
                now_iso(),
            ),
        )
        audit(conn, "OPERATOR", None, "pharmacy_user.created", "pharmacy_user", user_id, {})
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise RecetaMXError("La CURP del personal de farmacia ya existe.", 409, "duplicate_pharmacy_user") from exc
    return {"id": user_id, "status": data.get("status", "ACTIVE")}


def create_patient(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    for field in ("identifier_type", "identifier_value", "full_name"):
        if not data.get(field):
            raise RecetaMXError(f"Falta el campo {field}.")
    identifier_type = normalize_name(data["identifier_type"])
    if identifier_type not in {"CURP", "TEMP_RURAL", "NEWBORN", "FOREIGN", "OTHER"}:
        raise RecetaMXError("Tipo de identificador de paciente no permitido.")
    access_code = str(data.get("access_code") or secrets.randbelow(900000) + 100000)
    patient_id = str(uuid.uuid4())
    try:
        conn.execute(
            "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                patient_id,
                identifier_type,
                normalize_name(data["identifier_value"]),
                normalize_name(data["full_name"]),
                data.get("birth_date"),
                data.get("sex"),
                hash_password("code:" + access_code),
                now_iso(),
            ),
        )
        audit(conn, "OPERATOR", None, "patient.created", "patient", patient_id, {"identifier_type": identifier_type})
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise RecetaMXError("El identificador del paciente ya existe.", 409, "duplicate_patient") from exc
    return {
        "id": patient_id,
        "identifier_type": identifier_type,
        "identifier_value": normalize_name(data["identifier_value"]),
        "access_code": access_code,
    }


def login(conn: sqlite3.Connection, actor_type: str, identifier: str, password: str) -> dict[str, Any]:
    actor_type = actor_type.upper()
    identifier = normalize_name(identifier)
    if actor_type == "PRESCRIBER":
        row = conn.execute(
            "SELECT * FROM prescribers WHERE curp=? OR prescriber_number=?",
            (identifier, identifier),
        ).fetchone()
        if not row or row["verification_state"] != "ACTIVE":
            raise RecetaMXError("Prescriptor no encontrado o no activo.", 401, "login_failed")
    elif actor_type == "PHARMACY_USER":
        row = conn.execute("SELECT * FROM pharmacy_users WHERE curp=?", (identifier,)).fetchone()
        if not row or row["status"] != "ACTIVE":
            raise RecetaMXError("Personal de farmacia no encontrado o no activo.", 401, "login_failed")
    else:
        raise RecetaMXError("Tipo de actor no permitido.")
    if not verify_password(password, row["password_hash"]):
        raise RecetaMXError("Credenciales inválidas.", 401, "login_failed")
    token = secrets.token_urlsafe(36)
    expires = (datetime.now(UTC) + timedelta(hours=8)).replace(microsecond=0).isoformat()
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
        (token_hash(token), actor_type, row["id"], expires, now_iso()),
    )
    audit(conn, actor_type, row["id"], "session.created", "session", None, {})
    conn.commit()
    return {"token": token, "actor_type": actor_type, "actor_id": row["id"], "expires_at": expires}


def require_session(conn: sqlite3.Connection, token: str | None, expected_type: str) -> sqlite3.Row:
    if not token:
        raise RecetaMXError("Falta token de sesión.", 401, "missing_token")
    row = conn.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash(token),)).fetchone()
    if not row or row["actor_type"] != expected_type:
        raise RecetaMXError("Sesión inválida.", 401, "invalid_session")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(UTC):
        raise RecetaMXError("La sesión expiró.", 401, "expired_session")
    if expected_type == "PRESCRIBER":
        actor = conn.execute("SELECT * FROM prescribers WHERE id=?", (row["actor_id"],)).fetchone()
    else:
        actor = conn.execute("SELECT * FROM pharmacy_users WHERE id=?", (row["actor_id"],)).fetchone()
    if not actor:
        raise RecetaMXError("Actor no encontrado.", 401, "invalid_session")
    return actor


def _validate_item_for_prescriber(item: dict[str, Any], prescriber: sqlite3.Row) -> dict[str, Any]:
    catalog_item = None
    if item.get("code"):
        try:
            catalog_item = CATALOG.validate_item(item)
        except ValueError as exc:
            raise RecetaMXError(str(exc), 409, "catalog_mismatch") from exc
        if catalog_item is None:
            raise RecetaMXError(
                "El código no existe en la versión activa del catálogo.",
                422,
                "catalog_code_unknown",
            )
    source = {**(catalog_item or {}), **item}
    generic_name = normalize_name(source.get("generic_name", ""))
    if not generic_name:
        raise RecetaMXError("Cada medicamento requiere denominación genérica.")
    sale_fraction = normalize_name(source.get("sale_fraction", "IV"))
    controlled_group = normalize_name(source.get("controlled_group", "NONE"))
    if sale_fraction not in SALE_FRACTIONS:
        raise RecetaMXError(f"Fracción de venta inválida: {sale_fraction}")
    if controlled_group not in CONTROLLED_GROUPS:
        raise RecetaMXError(f"Grupo controlado inválido: {controlled_group}")
    try:
        quantity = float(source.get("quantity_prescribed"))
    except (TypeError, ValueError) as exc:
        raise RecetaMXError("Cantidad prescrita inválida.") from exc
    if quantity <= 0:
        raise RecetaMXError("La cantidad prescrita debe ser mayor que cero.")

    attrs = json.loads(prescriber["attributes_json"])
    if not attrs.get("can_prescribe_general", False):
        raise RecetaMXError("El prescriptor no tiene atributo de prescripción general.", 403, "scope_denied")
    allowed_controlled = set(attrs.get("allowed_controlled_groups") or [])
    if controlled_group != "NONE" and controlled_group not in allowed_controlled:
        raise RecetaMXError(
            f"El prescriptor no está autorizado para {controlled_group}.",
            403,
            "controlled_scope_denied",
        )
    if prescriber["profession"] == "LIC_ENFERMERIA":
        allowed_codes = set(attrs.get("allowed_drug_codes") or [])
        if not source.get("code") or source.get("code") not in allowed_codes:
            raise RecetaMXError(
                "El medicamento no está dentro del catálogo habilitado para enfermería.",
                403,
                "nursing_catalog_denied",
            )
    refills = int(source.get("refills_authorized", 0) or 0)
    if controlled_group in {"ESTUPEFACIENTE", "PSICOTROPICO_II", "PSICOTROPICO_III"} and refills > 0:
        raise RecetaMXError("Este grupo controlado no admite resurtidos en la alpha.")
    if controlled_group == "PSICOTROPICO_IV" and refills > 2:
        raise RecetaMXError("Psicotrópico IV admite como máximo dos resurtidos adicionales.")

    return {
        "code": source.get("code"),
        "generic_name": generic_name,
        "brand_requested": normalize_name(source.get("brand_requested", "")) or None,
        "form": str(source.get("form") or "NO ESPECIFICADA").strip(),
        "strength": str(source.get("strength") or "NO ESPECIFICADA").strip(),
        "dose": str(source.get("dose") or "NO ESPECIFICADA").strip(),
        "route": str(source.get("route") or "NO ESPECIFICADA").strip(),
        "frequency": str(source.get("frequency") or "NO ESPECIFICADA").strip(),
        "duration_days": int(source["duration_days"]) if source.get("duration_days") is not None else None,
        "quantity_prescribed": quantity,
        "sale_fraction": sale_fraction,
        "controlled_group": controlled_group,
        "refills_authorized": refills,
        "substitution_allowed": bool(source.get("substitution_allowed", True)),
        "warnings": MEDICATION_WARNINGS.get(generic_name, []),
    }


def _interaction_check(items: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    names = {item["generic_name"] for item in items}
    findings: list[dict[str, str]] = []
    for pair, severity, message in INTERACTION_RULES:
        if pair.issubset(names):
            findings.append({"medications": " + ".join(sorted(pair)), "severity": severity, "message": message})
    return findings


def _validity_days(items: list[dict[str, Any]]) -> int:
    days = 365
    for item in items:
        if item["controlled_group"] in {"ESTUPEFACIENTE", "PSICOTROPICO_II"} or item["sale_fraction"] in {"I", "II"}:
            days = min(days, 30)
        elif item["controlled_group"] in {"PSICOTROPICO_III", "PSICOTROPICO_IV"} or item["sale_fraction"] == "III":
            days = min(days, 180)
    return days


def issue_prescription(
    conn: sqlite3.Connection,
    prescriber: sqlite3.Row,
    data: dict[str, Any],
    signing_secret: str,
    public_base_url: str,
) -> dict[str, Any]:
    patient_ref = data.get("patient") or {}
    patient = conn.execute(
        "SELECT * FROM patients WHERE identifier_type=? AND identifier_value=?",
        (normalize_name(patient_ref.get("identifier_type", "")), normalize_name(patient_ref.get("identifier_value", ""))),
    ).fetchone()
    generated_access_code = None
    if not patient:
        created = create_patient(conn, patient_ref)
        generated_access_code = created["access_code"]
        patient = conn.execute("SELECT * FROM patients WHERE id=?", (created["id"],)).fetchone()
    raw_items = data.get("items") or []
    if not raw_items:
        raise RecetaMXError("La receta requiere al menos un medicamento.")
    items = [_validate_item_for_prescriber(item, prescriber) for item in raw_items]
    interactions = _interaction_check(items)
    warnings = [warning for item in items for warning in item["warnings"]]
    if interactions:
        warnings.append("La receta contiene interacciones que requieren revisión clínica.")

    folio = generate_folio()
    verification_token = secrets.token_urlsafe(24)
    prescription_id = str(uuid.uuid4())
    issued_at = now_iso()
    valid_until = (datetime.now(UTC) + timedelta(days=_validity_days(items))).replace(microsecond=0).isoformat()
    payload = {
        "schema": SCHEMA_VERSION,
        "folio": folio,
        "issued_at": issued_at,
        "valid_until": valid_until,
        "patient": {
            "identifier_type": patient["identifier_type"],
            "identifier_value": patient["identifier_value"],
            "full_name": patient["full_name"],
        },
        "prescriber": {
            "prescriber_number": prescriber["prescriber_number"],
            "professional_license": prescriber["professional_license"],
            "full_name": prescriber["full_name"],
            "profession": prescriber["profession"],
        },
        "items": items,
        "diagnosis_code": data.get("diagnosis_code"),
        "clinical_note": data.get("clinical_note"),
        "public_origin": bool(data.get("public_origin", False)),
        "fulfillment_route": data.get("fulfillment_route", "ANY_AUTHORIZED_PHARMACY"),
        "payer_type": data.get("payer_type", "PATIENT"),
        "transfer_reason": data.get("transfer_reason"),
        "catalog_version": CATALOG_VERSION,
    }
    signature = hmac.new(signing_secret.encode(), canonical_json(payload).encode(), hashlib.sha256).hexdigest()
    conn.execute(
        """
        INSERT INTO prescriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            prescription_id,
            folio,
            token_hash(verification_token),
            patient["id"],
            prescriber["id"],
            "ACTIVE",
            issued_at,
            valid_until,
            data.get("diagnosis_code"),
            data.get("clinical_note"),
            1 if data.get("public_origin") else 0,
            data.get("fulfillment_route", "ANY_AUTHORIZED_PHARMACY"),
            data.get("payer_type", "PATIENT"),
            data.get("transfer_reason"),
            canonical_json(warnings),
            canonical_json(interactions),
            prescriber["phone"],
            CATALOG_VERSION,
            "ALPHA-HMAC-SHA256",
            signature,
            canonical_json(payload),
            now_iso(),
        ),
    )
    for line_no, item in enumerate(items, 1):
        conn.execute(
            """
            INSERT INTO prescription_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                prescription_id,
                line_no,
                item["code"],
                item["generic_name"],
                item["brand_requested"],
                item["form"],
                item["strength"],
                item["dose"],
                item["route"],
                item["frequency"],
                item["duration_days"],
                item["quantity_prescribed"],
                0,
                item["sale_fraction"],
                item["controlled_group"],
                item["refills_authorized"],
                0,
                1 if item["substitution_allowed"] else 0,
                canonical_json(item["warnings"]),
            ),
        )
    audit(conn, "PRESCRIBER", prescriber["id"], "prescription.issued", "prescription", prescription_id, {"folio": folio})
    conn.commit()
    verification_url = f"{public_base_url.rstrip('/')}/verify/{folio}?token={verification_token}"
    response = {
        "folio": folio,
        "status": "ACTIVE",
        "issued_at": issued_at,
        "valid_until": valid_until,
        "verification_token": verification_token,
        "verification_url": verification_url,
        "bidimensional_payload": verification_url,
        "warnings": warnings,
        "interactions": interactions,
        "signature": {"algorithm": "ALPHA-HMAC-SHA256", "value": signature},
    }
    if generated_access_code:
        response["patient_access_code"] = generated_access_code
    return response


def _prescription_rows(conn: sqlite3.Connection, folio: str) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
    rx = conn.execute(
        """
        SELECT p.*, pr.prescriber_number, pr.full_name AS prescriber_name, pr.professional_license,
               pt.identifier_type, pt.identifier_value, pt.full_name AS patient_name
        FROM prescriptions p
        JOIN prescribers pr ON pr.id=p.prescriber_id
        JOIN patients pt ON pt.id=p.patient_id
        WHERE p.folio=?
        """,
        (normalize_name(folio),),
    ).fetchone()
    if not rx:
        raise RecetaMXError("Receta no encontrada.", 404, "prescription_not_found")
    items = conn.execute(
        "SELECT * FROM prescription_items WHERE prescription_id=? ORDER BY line_no",
        (rx["id"],),
    ).fetchall()
    return rx, items


def verify_prescription(conn: sqlite3.Connection, folio: str, verification_token: str) -> dict[str, Any]:
    rx, items = _prescription_rows(conn, folio)
    if not hmac.compare_digest(rx["verification_token_hash"], token_hash(verification_token or "")):
        raise RecetaMXError("Token de verificación inválido.", 401, "verification_failed")
    result = serialize_prescription(rx, items)
    audit(conn, "PUBLIC", None, "prescription.verified", "prescription", rx["id"], {"folio": rx["folio"]})
    conn.commit()
    return result


def serialize_prescription(rx: sqlite3.Row, items: list[sqlite3.Row]) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "folio": rx["folio"],
        "status": rx["status"],
        "issued_at": rx["issued_at"],
        "valid_until": rx["valid_until"],
        "patient": {
            "identifier_type": rx["identifier_type"],
            "identifier_value_masked": mask_identifier(rx["identifier_value"]),
            "full_name": rx["patient_name"],
        },
        "prescriber": {
            "prescriber_number": rx["prescriber_number"],
            "full_name": rx["prescriber_name"],
            "professional_license": rx["professional_license"],
            "contact_phone": rx["contact_phone"],
        },
        "items": [
            {
                "line_no": item["line_no"],
                "code": item["code"],
                "generic_name": item["generic_name"],
                "brand_requested": item["brand_requested"],
                "form": item["form"],
                "strength": item["strength"],
                "dose": item["dose"],
                "route": item["route"],
                "frequency": item["frequency"],
                "duration_days": item["duration_days"],
                "quantity_prescribed": item["quantity_prescribed"],
                "quantity_dispensed": item["quantity_dispensed"],
                "quantity_remaining": max(0, item["quantity_prescribed"] - item["quantity_dispensed"]),
                "sale_fraction": item["sale_fraction"],
                "controlled_group": item["controlled_group"],
                "refills_authorized": item["refills_authorized"],
                "refills_used": item["refills_used"],
                "substitution_allowed": bool(item["substitution_allowed"]),
                "warnings": json.loads(item["warnings_json"]),
            }
            for item in items
        ],
        "warnings": json.loads(rx["warnings_json"]),
        "interactions": json.loads(rx["interactions_json"]),
        "public_origin": bool(rx["public_origin"]),
        "fulfillment_route": rx["fulfillment_route"],
        "payer_type": rx["payer_type"],
        "transfer_reason": rx["transfer_reason"],
        "signature": {"algorithm": rx["signature_alg"], "value": rx["signature_value"]},
        "catalog_version": rx["catalog_version"],
    }


def mask_identifier(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def patient_recent_prescriptions(
    conn: sqlite3.Connection,
    pharmacy_user: sqlite3.Row,
    identifier_type: str,
    identifier_value: str,
    access_code: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    patient = conn.execute(
        "SELECT * FROM patients WHERE identifier_type=? AND identifier_value=?",
        (normalize_name(identifier_type), normalize_name(identifier_value)),
    ).fetchone()
    if not patient or not verify_password("code:" + access_code, patient["access_code_hash"]):
        raise RecetaMXError("Paciente o código de acceso inválido.", 401, "patient_consent_failed")
    limit = max(1, min(int(limit), 10))
    prescriptions = conn.execute(
        """
        SELECT p.*, pr.prescriber_number, pr.full_name AS prescriber_name, pr.professional_license,
               pt.identifier_type, pt.identifier_value, pt.full_name AS patient_name
        FROM prescriptions p
        JOIN prescribers pr ON pr.id=p.prescriber_id
        JOIN patients pt ON pt.id=p.patient_id
        WHERE p.patient_id=?
        ORDER BY p.issued_at DESC
        LIMIT ?
        """,
        (patient["id"], limit),
    ).fetchall()
    result = []
    for rx in prescriptions:
        items = conn.execute(
            "SELECT * FROM prescription_items WHERE prescription_id=? ORDER BY line_no",
            (rx["id"],),
        ).fetchall()
        result.append(serialize_prescription(rx, items))
    audit(
        conn,
        "PHARMACY_USER",
        pharmacy_user["id"],
        "patient.recent_prescriptions.accessed",
        "patient",
        patient["id"],
        {"employee_curp": pharmacy_user["curp"], "count": len(result)},
    )
    conn.commit()
    return result


def dispense_prescription(
    conn: sqlite3.Connection,
    pharmacy_user: sqlite3.Row,
    folio: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    rx, items = _prescription_rows(conn, folio)
    if rx["status"] not in {"ACTIVE", "PARTIALLY_DISPENSED"}:
        raise RecetaMXError("La receta ya no está disponible para surtimiento.", 409, "prescription_closed")
    if datetime.fromisoformat(rx["valid_until"]) < datetime.now(UTC):
        raise RecetaMXError("La receta está vencida.", 409, "prescription_expired")
    pharmacy = conn.execute("SELECT * FROM pharmacies WHERE id=?", (pharmacy_user["pharmacy_id"],)).fetchone()
    if not pharmacy or pharmacy["status"] != "ACTIVE":
        raise RecetaMXError("Farmacia no activa.", 403, "pharmacy_not_active")

    requested = data.get("items") or []
    if not requested:
        raise RecetaMXError("El surtimiento requiere al menos una partida.")
    by_line = {int(item["line_no"]): item for item in items}
    dispense_id = str(uuid.uuid4())
    mode = normalize_name(data.get("mode", "FULL"))
    conn.execute(
        "INSERT INTO dispenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            dispense_id,
            rx["id"],
            pharmacy["id"],
            pharmacy_user["id"],
            now_iso(),
            mode,
            1 if data.get("is_public_transfer") else 0,
            data.get("claim_status"),
            data.get("notes"),
        ),
    )
    for request in requested:
        line_no = int(request.get("line_no", 0))
        item = by_line.get(line_no)
        if not item:
            raise RecetaMXError(f"Partida inexistente: {line_no}")
        try:
            quantity = float(request.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise RecetaMXError(f"Cantidad inválida en partida {line_no}.") from exc
        remaining = item["quantity_prescribed"] - item["quantity_dispensed"]
        if quantity <= 0 or quantity > remaining:
            raise RecetaMXError(f"Cantidad excede el remanente de la partida {line_no}.")
        if not request.get("brand") or not request.get("lot_number"):
            raise RecetaMXError("Marca y lote son obligatorios en cada partida surtida.")
        conn.execute(
            "INSERT INTO dispense_items VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                dispense_id,
                item["id"],
                quantity,
                normalize_name(request["brand"]),
                normalize_name(request["lot_number"]),
                request.get("expiration_date"),
            ),
        )
        refills_used = item["refills_used"] + (1 if mode == "REFILL" else 0)
        if refills_used > item["refills_authorized"]:
            raise RecetaMXError(f"La partida {line_no} no tiene resurtidos disponibles.")
        conn.execute(
            "UPDATE prescription_items SET quantity_dispensed=quantity_dispensed+?, refills_used=? WHERE id=?",
            (quantity, refills_used, item["id"]),
        )

    refreshed = conn.execute(
        "SELECT quantity_prescribed, quantity_dispensed FROM prescription_items WHERE prescription_id=?",
        (rx["id"],),
    ).fetchall()
    complete = all(row["quantity_dispensed"] >= row["quantity_prescribed"] for row in refreshed)
    new_status = "DISPENSED" if complete else "PARTIALLY_DISPENSED"
    conn.execute("UPDATE prescriptions SET status=? WHERE id=?", (new_status, rx["id"]))
    audit(
        conn,
        "PHARMACY_USER",
        pharmacy_user["id"],
        "prescription.dispensed",
        "prescription",
        rx["id"],
        {
            "folio": rx["folio"],
            "employee_curp": pharmacy_user["curp"],
            "pharmacy_license": pharmacy["license_number"],
            "mode": mode,
            "status": new_status,
        },
    )
    conn.commit()
    return {"dispense_id": dispense_id, "folio": rx["folio"], "status": new_status}


def fhir_bundle(conn: sqlite3.Connection, folio: str, verification_token: str) -> dict[str, Any]:
    rx = verify_prescription(conn, folio, verification_token)
    patient_id = f"patient-{hashlib.sha256(rx['patient']['identifier_value_masked'].encode()).hexdigest()[:12]}"
    practitioner_id = f"practitioner-{rx['prescriber']['prescriber_number']}"
    entries = [
        {
            "fullUrl": f"urn:uuid:{patient_id}",
            "resource": {
                "resourceType": "Patient",
                "id": patient_id,
                "identifier": [{"system": "https://receta.mx/id/patient", "value": rx["patient"]["identifier_value_masked"]}],
                "name": [{"text": rx["patient"]["full_name"]}],
            },
        },
        {
            "fullUrl": f"urn:uuid:{practitioner_id}",
            "resource": {
                "resourceType": "Practitioner",
                "id": practitioner_id,
                "identifier": [
                    {"system": "https://receta.mx/id/prescriber", "value": rx["prescriber"]["prescriber_number"]},
                    {"system": "https://cedulaprofesional.sep.gob.mx", "value": rx["prescriber"]["professional_license"]},
                ],
                "name": [{"text": rx["prescriber"]["full_name"]}],
                "telecom": [{"system": "phone", "value": rx["prescriber"]["contact_phone"]}],
            },
        },
    ]
    for item in rx["items"]:
        entries.append(
            {
                "fullUrl": f"urn:uuid:medreq-{rx['folio']}-{item['line_no']}",
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": f"medreq-{rx['folio']}-{item['line_no']}",
                    "status": "active" if rx["status"] in {"ACTIVE", "PARTIALLY_DISPENSED"} else "completed",
                    "intent": "order",
                    "medicationCodeableConcept": {
                        "coding": [{"system": "https://receta.mx/catalog/demo", "code": item["code"]}],
                        "text": f"{item['generic_name']} {item['strength']} {item['form']}",
                    },
                    "subject": {"reference": f"urn:uuid:{patient_id}"},
                    "requester": {"reference": f"urn:uuid:{practitioner_id}"},
                    "authoredOn": rx["issued_at"],
                    "dosageInstruction": [
                        {
                            "text": f"{item['dose']} vía {item['route']} {item['frequency']}",
                            "route": {"text": item["route"]},
                        }
                    ],
                    "dispenseRequest": {
                        "quantity": {"value": item["quantity_prescribed"]},
                        "numberOfRepeatsAllowed": item["refills_authorized"],
                    },
                    "extension": [
                        {"url": "https://receta.mx/fhir/StructureDefinition/sale-fraction", "valueCode": item["sale_fraction"]},
                        {"url": "https://receta.mx/fhir/StructureDefinition/controlled-group", "valueCode": item["controlled_group"]},
                    ],
                },
            }
        )
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "identifier": {"system": "https://receta.mx/id/prescription", "value": rx["folio"]},
        "timestamp": now_iso(),
        "meta": {"tag": [{"system": "https://receta.mx/standard", "code": SCHEMA_VERSION}]},
        "entry": entries,
    }


def bootstrap_demo(conn: sqlite3.Connection) -> dict[str, Any]:
    existing = conn.execute("SELECT COUNT(*) AS n FROM prescribers").fetchone()["n"]
    if existing:
        return {"message": "La base ya contiene datos; no se volvió a sembrar."}
    prescriber = create_prescriber(
        conn,
        {
            "curp": "MEDD900101HDFMXX09",
            "full_name": "Médico Demo Receta MX",
            "profession": "MEDICO",
            "professional_license": "12345678",
            "phone": "+52 55 0000 0000",
            "email": "medico@demo.receta.mx",
            "password": "demo-medico",
            "verification_state": "ACTIVE",
            "efirma_certificate_serial": "DEMO-NO-VALIDO",
            "efirma_fingerprint": "DEMO",
            "liveness_check": "PASSED",
            "ai_review": "PASSED",
            "manual_review": "PASSED",
            "attributes": {
                "can_prescribe_general": True,
                "allowed_controlled_groups": [
                    "ESTUPEFACIENTE",
                    "PSICOTROPICO_II",
                    "PSICOTROPICO_III",
                    "PSICOTROPICO_IV",
                ],
                "allowed_drug_codes": [],
                "scope": "HUMAN",
                "demo": True,
            },
        },
    )
    pharmacy = create_pharmacy(
        conn,
        {"name": "Farmacia Demo", "license_number": "LIC-DEMO-001", "status": "ACTIVE"},
    )
    pharmacy_user = create_pharmacy_user(
        conn,
        {
            "pharmacy_id": pharmacy["id"],
            "curp": "FARD900101MDFMXX02",
            "full_name": "Dispensadora Demo",
            "password": "demo-farmacia",
            "role": "DISPENSER",
        },
    )
    patient = create_patient(
        conn,
        {
            "identifier_type": "TEMP_RURAL",
            "identifier_value": "RURAL-DEMO-001",
            "full_name": "Paciente Demo Rural",
            "birth_date": "1980-01-01",
            "sex": "X",
            "access_code": "123456",
        },
    )
    return {
        "prescriber": {
            "identifier": "MEDD900101HDFMXX09",
            "password": "demo-medico",
            **prescriber,
        },
        "pharmacy": pharmacy,
        "pharmacy_user": {
            "identifier": "FARD900101MDFMXX02",
            "password": "demo-farmacia",
            **pharmacy_user,
        },
        "patient": {**patient, "access_code": "123456"},
        "warning": "Todos los datos son sintéticos y no acreditan autorizaciones reales.",
    }
