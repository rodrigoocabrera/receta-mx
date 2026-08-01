import tempfile
import unittest
from pathlib import Path

from recetamx.core import (
    RecetaMXError,
    bootstrap_demo,
    connect,
    dispense_prescription,
    initialize_database,
    issue_prescription,
    login,
    patient_recent_prescriptions,
    require_session,
    verify_prescription,
)


class RecetaMXCoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "test.sqlite3")
        self.conn = connect(self.db_path)
        initialize_database(self.conn)
        self.demo = bootstrap_demo(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tempdir.cleanup()

    def login_prescriber(self):
        auth = login(self.conn, "PRESCRIBER", "MEDD900101HDFMXX09", "demo-medico")
        return require_session(self.conn, auth["token"], "PRESCRIBER")

    def login_pharmacy(self):
        auth = login(self.conn, "PHARMACY_USER", "FARD900101MDFMXX02", "demo-farmacia")
        return require_session(self.conn, auth["token"], "PHARMACY_USER")

    def issue_demo(self, generic="AMOXICILINA", sale_fraction="IV", controlled_group="NONE"):
        prescriber = self.login_prescriber()
        return issue_prescription(
            self.conn,
            prescriber,
            {
                "patient": {
                    "identifier_type": "TEMP_RURAL",
                    "identifier_value": "RURAL-DEMO-001",
                    "full_name": "Paciente Demo Rural",
                },
                "items": [
                    {
                        "code": "RXMX-DEMO-AMOX",
                        "generic_name": generic,
                        "form": "CÁPSULA",
                        "strength": "500 mg",
                        "dose": "1 cápsula",
                        "route": "ORAL",
                        "frequency": "cada 8 horas",
                        "duration_days": 7,
                        "quantity_prescribed": 21,
                        "sale_fraction": sale_fraction,
                        "controlled_group": controlled_group,
                        "refills_authorized": 0,
                    }
                ],
            },
            "test-secret",
            "http://localhost:8080",
        )

    def test_issue_and_verify(self):
        issued = self.issue_demo()
        verified = verify_prescription(self.conn, issued["folio"], issued["verification_token"])
        self.assertEqual(verified["folio"], issued["folio"])
        self.assertEqual(verified["status"], "ACTIVE")
        self.assertEqual(verified["items"][0]["quantity_remaining"], 21)

    def test_invalid_verification_token(self):
        issued = self.issue_demo()
        with self.assertRaises(RecetaMXError):
            verify_prescription(self.conn, issued["folio"], "wrong")

    def test_pharmacy_recent_requires_patient_code(self):
        self.issue_demo()
        pharmacy_user = self.login_pharmacy()
        with self.assertRaises(RecetaMXError):
            patient_recent_prescriptions(
                self.conn,
                pharmacy_user,
                "TEMP_RURAL",
                "RURAL-DEMO-001",
                "000000",
            )
        items = patient_recent_prescriptions(
            self.conn,
            pharmacy_user,
            "TEMP_RURAL",
            "RURAL-DEMO-001",
            "123456",
        )
        self.assertEqual(len(items), 1)

    def test_dispense_closes_complete_prescription(self):
        issued = self.issue_demo()
        pharmacy_user = self.login_pharmacy()
        result = dispense_prescription(
            self.conn,
            pharmacy_user,
            issued["folio"],
            {
                "mode": "FULL",
                "items": [
                    {
                        "line_no": 1,
                        "quantity": 21,
                        "brand": "GENÉRICO DEMO",
                        "lot_number": "LOT-001",
                    }
                ],
            },
        )
        self.assertEqual(result["status"], "DISPENSED")

    def test_interaction_warning(self):
        prescriber = self.login_prescriber()
        issued = issue_prescription(
            self.conn,
            prescriber,
            {
                "patient": {
                    "identifier_type": "TEMP_RURAL",
                    "identifier_value": "RURAL-DEMO-001",
                    "full_name": "Paciente Demo Rural",
                },
                "items": [
                    {
                        "generic_name": "WARFARINA",
                        "form": "TABLETA",
                        "strength": "5 mg",
                        "dose": "1",
                        "route": "ORAL",
                        "frequency": "cada 24 horas",
                        "quantity_prescribed": 10,
                        "sale_fraction": "IV",
                        "controlled_group": "NONE",
                    },
                    {
                        "generic_name": "IBUPROFENO",
                        "form": "TABLETA",
                        "strength": "400 mg",
                        "dose": "1",
                        "route": "ORAL",
                        "frequency": "cada 8 horas",
                        "quantity_prescribed": 10,
                        "sale_fraction": "IV",
                        "controlled_group": "NONE",
                    },
                ],
            },
            "test-secret",
            "http://localhost:8080",
        )
        self.assertTrue(issued["interactions"])
        self.assertEqual(issued["interactions"][0]["severity"], "ALTA")


if __name__ == "__main__":
    unittest.main()
