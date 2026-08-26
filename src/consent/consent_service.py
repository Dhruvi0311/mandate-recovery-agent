import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

class ConsentService:
    def __init__(self, data_path: str = "data/consents.csv"):
        self.data_path = data_path
        self._load_consents()
        
    def _load_consents(self):
        try:
            self.consents_df = pd.read_csv(self.data_path)
            self.consents_df['expiry_date'] = pd.to_datetime(self.consents_df['expiry_date'])
        except Exception:
            # If the file is missing or invalid, create an empty dataframe with expected schema
            self.consents_df = pd.DataFrame(columns=['customer_id', 'consent_id', 'status', 'data_scope', 'expiry_date'])

    def validate_data_consent(self, customer_id: str, required_scope: str = "TRANSACTIONS") -> Dict[str, Any]:
        """
        Validates whether a customer has active Account Aggregator / Data consent.
        This is distinct from explicit Action Consent.
        """
        customer_consents = self.consents_df[self.consents_df['customer_id'] == customer_id]
        
        if customer_consents.empty:
            return {
                "customer_id": customer_id,
                "valid": False,
                "status": "MISSING",
                "scope": None,
                "reason": "No consent record found for customer."
            }
            
        # For MVP, just take the first matching consent record
        consent = customer_consents.iloc[0]
        status = consent['status'].upper()
        scope = str(consent['data_scope']).upper()
        expiry_date = consent['expiry_date']
        
        if status == 'REVOKED':
            return {
                "customer_id": customer_id,
                "valid": False,
                "status": "REVOKED",
                "scope": scope,
                "reason": "Consent has been revoked."
            }
            
        if pd.notnull(expiry_date) and expiry_date < pd.Timestamp.now():
            return {
                "customer_id": customer_id,
                "valid": False,
                "status": "EXPIRED",
                "scope": scope,
                "reason": "Consent has expired."
            }
            
        if required_scope not in scope:
            return {
                "customer_id": customer_id,
                "valid": False,
                "status": status,
                "scope": scope,
                "reason": f"Consent scope does not include {required_scope}."
            }
            
        return {
            "customer_id": customer_id,
            "valid": True,
            "status": "ACTIVE",
            "scope": scope,
            "reason": "VALID_CONSENT"
        }
