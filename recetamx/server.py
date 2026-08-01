from __future__ import annotations

import html
import io
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .catalog import CATALOG, CATALOG_VERSION
from .core import (
    RecetaMXError,
    bootstrap_demo,
    connect,
    create_patient,
    create_pharmacy,
    create_pharmacy_user,
    create_prescriber,
    dispense_prescription,
    fhir_bundle,
    initialize_database,
    issue_prescription,
    login,
    patient_recent_prescriptions,
    require_session,
    validate_operator_key,
    verify_prescription,
)

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
DB_PATH = os.environ.get("RECETAMX_DB", str(ROOT / "data" / "recetamx.sqlite3"))
OPERATOR_KEY = os.environ.get("RECETAMX_OPERATOR_KEY", "dev-operator-key")
SIGNING_SECRET = os.environ.get("RECETAMX_SIGNING_SECRET", "dev-signing-secret-change-me")
PUBLIC_BASE_URL = os.environ.get("RECETAMX_PUBLIC_BASE_URL", "http://localhost:8080")


def bearer(headers: Any) -> str | None:
    value = headers.get("Authorization", "")
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return None


def optional_qr_svg(payload: str) -> bytes:
    try:
        import qrcode  # type: ignore
        from qrcode.image.svg import SvgPathImage  # type: ignore

        image = qrcode.make(payload, image_factory=SvgPathImage, box_size=8, border=3)
        stream = io.BytesIO()
        image.save(stream)
        return stream.getvalue()
    except Exception:
        safe = html.escape(payload)
        return f"""<svg xmlns='http://www.w3.org/2000/svg' width='680' height='180' viewBox='0 0 680 180'>
        <rect width='100%' height='100%' fill='white'/>
        <rect x='12' y='12' width='656' height='156' fill='none' stroke='black' stroke-width='2'/>
        <text x='30' y='58' font-family='sans-serif' font-size='20'>QR no disponible: instala el extra qrcode.</text>
        <text x='30' y='94' font-family='monospace' font-size='12'>{safe}</text>
        <text x='30' y='132' font-family='sans-serif' font-size='13'>El texto es el payload bidimensional verificable.</text>
        </svg>""".encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "RecetaMXAlpha/0.1"

    def _conn(self):
        conn = connect(DB_PATH)
        initialize_database(conn)
        return conn

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 1_500_000:
            raise RecetaMXError("Solicitud demasiado grande.", 413, "payload_too_large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RecetaMXError("JSON inválido.") from exc
        if not isinstance(value, dict):
            raise RecetaMXError("El cuerpo debe ser un objeto JSON.")
        return value

    def _send_json(self, value: object, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _send_bytes(self, payload: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, exc: Exception) -> None:
        if isinstance(exc, RecetaMXError):
            self._send_json({"error": exc.code, "message": exc.message}, exc.status)
        else:
            self._send_json({"error": "internal_error", "message": "Error interno no controlado."}, 500)
            print(f"Unhandled error: {exc!r}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Operator-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path in {"/", "/index.html"}:
                self._send_bytes((WEB_ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/api/status":
                self._send_json(
                    {
                        "service": "Receta MX Alpha",
                        "status": "ok",
                        "catalog_version": CATALOG_VERSION,
                        "production_ready": False,
                        "regulatory_authorization": False,
                    }
                )
                return
            if path == "/api/catalog":
                query_text = (query.get("q") or [""])[0]
                sale_fraction = (query.get("sale_fraction") or [None])[0]
                controlled_group = (query.get("controlled_group") or [None])[0]
                limit = int((query.get("limit") or ["20"])[0])
                items = CATALOG.search(
                    query_text,
                    sale_fraction=sale_fraction,
                    controlled_group=controlled_group,
                    limit=limit,
                )
                self._send_json(
                    {
                        "metadata": CATALOG.metadata.__dict__,
                        "query": query_text,
                        "count": len(items),
                        "items": items,
                    }
                )
                return

            catalog_match = re.fullmatch(r"/api/catalog/([^/]+)", path)
            if catalog_match:
                item = CATALOG.get(unquote(catalog_match.group(1)))
                if not item:
                    self._send_json({"error": "not_found", "message": "Medicamento no encontrado."}, 404)
                    return
                self._send_json({"metadata": CATALOG.metadata.__dict__, "item": item})
                return

            verify_match = re.fullmatch(r"/api/prescriptions/([^/]+)", path)
            if verify_match:
                token = (query.get("token") or [""])[0]
                with self._conn() as conn:
                    self._send_json(verify_prescription(conn, unquote(verify_match.group(1)), token))
                return

            fhir_match = re.fullmatch(r"/api/prescriptions/([^/]+)/fhir", path)
            if fhir_match:
                token = (query.get("token") or [""])[0]
                with self._conn() as conn:
                    self._send_json(fhir_bundle(conn, unquote(fhir_match.group(1)), token))
                return

            qr_match = re.fullmatch(r"/api/prescriptions/([^/]+)/qr\.svg", path)
            if qr_match:
                token = (query.get("token") or [""])[0]
                folio = unquote(qr_match.group(1))
                with self._conn() as conn:
                    verify_prescription(conn, folio, token)
                payload = f"{PUBLIC_BASE_URL.rstrip('/')}/verify/{folio}?token={token}"
                self._send_bytes(optional_qr_svg(payload), "image/svg+xml; charset=utf-8")
                return

            recent_match = re.fullmatch(r"/api/patients/([^/]+)/recent", path)
            if recent_match:
                identifier_type = (query.get("identifier_type") or ["CURP"])[0]
                access_code = (query.get("access_code") or [""])[0]
                limit = int((query.get("limit") or ["10"])[0])
                with self._conn() as conn:
                    user = require_session(conn, bearer(self.headers), "PHARMACY_USER")
                    result = patient_recent_prescriptions(
                        conn,
                        user,
                        identifier_type,
                        unquote(recent_match.group(1)),
                        access_code,
                        limit,
                    )
                    self._send_json({"items": result, "count": len(result)})
                return

            human_verify = re.fullmatch(r"/verify/([^/]+)", path)
            if human_verify:
                token = (query.get("token") or [""])[0]
                folio = unquote(human_verify.group(1))
                with self._conn() as conn:
                    result = verify_prescription(conn, folio, token)
                body = "<pre>" + html.escape(json.dumps(result, ensure_ascii=False, indent=2)) + "</pre>"
                self._send_bytes(
                    ("<!doctype html><meta charset='utf-8'><title>Verificación Receta MX</title>" + body).encode(),
                    "text/html; charset=utf-8",
                )
                return

            self._send_json({"error": "not_found", "message": "Ruta no encontrada."}, 404)
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            data = self._json_body()
            with self._conn() as conn:
                if path == "/api/auth/login":
                    self._send_json(login(conn, data.get("actor_type", ""), data.get("identifier", ""), data.get("password", "")))
                    return

                if path.startswith("/api/operator/"):
                    validate_operator_key(self.headers.get("X-Operator-Key"), OPERATOR_KEY)
                    if path == "/api/operator/bootstrap":
                        self._send_json(bootstrap_demo(conn), 201)
                    elif path == "/api/operator/prescribers":
                        self._send_json(create_prescriber(conn, data), 201)
                    elif path == "/api/operator/pharmacies":
                        self._send_json(create_pharmacy(conn, data), 201)
                    elif path == "/api/operator/pharmacy-users":
                        self._send_json(create_pharmacy_user(conn, data), 201)
                    elif path == "/api/operator/patients":
                        self._send_json(create_patient(conn, data), 201)
                    else:
                        self._send_json({"error": "not_found", "message": "Ruta de operador no encontrada."}, 404)
                    return

                if path == "/api/prescriptions":
                    prescriber = require_session(conn, bearer(self.headers), "PRESCRIBER")
                    self._send_json(issue_prescription(conn, prescriber, data, SIGNING_SECRET, PUBLIC_BASE_URL), 201)
                    return

                dispense_match = re.fullmatch(r"/api/prescriptions/([^/]+)/dispense", path)
                if dispense_match:
                    user = require_session(conn, bearer(self.headers), "PHARMACY_USER")
                    self._send_json(dispense_prescription(conn, user, unquote(dispense_match.group(1)), data), 201)
                    return

                self._send_json({"error": "not_found", "message": "Ruta no encontrada."}, 404)
        except Exception as exc:
            self._error(exc)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    host = os.environ.get("RECETAMX_HOST", "127.0.0.1")
    port = int(os.environ.get("RECETAMX_PORT", "8080"))
    with connect(DB_PATH) as conn:
        initialize_database(conn)
    print(f"Receta MX Alpha escuchando en http://{host}:{port}")
    if OPERATOR_KEY == "dev-operator-key" or SIGNING_SECRET.startswith("dev-"):
        print("ADVERTENCIA: se están usando secretos de desarrollo. No desplegar así en producción.")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
