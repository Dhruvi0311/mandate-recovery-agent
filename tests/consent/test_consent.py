import unittest
import pandas as pd
import os
from src.consent.consent_service import ConsentService

class TestConsentService(unittest.TestCase):
    def setUp(self):
        # Create a temporary mock consent CSV
        self.mock_csv = "test_consents.csv"
        df = pd.DataFrame([
            {"customer_id": "C001", "consent_id": "CON1", "status": "ACTIVE", "data_scope": "TRANSACTIONS,PROFILE", "expiry_date": "2099-01-01"},
            {"customer_id": "C002", "consent_id": "CON2", "status": "REVOKED", "data_scope": "TRANSACTIONS", "expiry_date": "2099-01-01"},
            {"customer_id": "C003", "consent_id": "CON3", "status": "ACTIVE", "data_scope": "TRANSACTIONS", "expiry_date": "2020-01-01"}, # Expired
            {"customer_id": "C004", "consent_id": "CON4", "status": "ACTIVE", "data_scope": "PROFILE", "expiry_date": "2099-01-01"} # Wrong scope
        ])
        df.to_csv(self.mock_csv, index=False)
        self.service = ConsentService(data_path=self.mock_csv)

    def tearDown(self):
        if os.path.exists(self.mock_csv):
            os.remove(self.mock_csv)

    def test_active_valid_consent(self):
        res = self.service.validate_data_consent("C001")
        self.assertTrue(res["valid"])
        self.assertEqual(res["status"], "ACTIVE")

    def test_revoked_consent(self):
        res = self.service.validate_data_consent("C002")
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "REVOKED")

    def test_expired_consent(self):
        res = self.service.validate_data_consent("C003")
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "EXPIRED")
        
    def test_wrong_scope_consent(self):
        res = self.service.validate_data_consent("C004")
        self.assertFalse(res["valid"])
        
    def test_missing_consent(self):
        res = self.service.validate_data_consent("C999")
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "MISSING")

if __name__ == '__main__':
    unittest.main()
