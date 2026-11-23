import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.schemas.financial_audit import (
    AirFinancialAuditDataUpsert,
    PayableRequest,
    ReceivableRequest,
)


class FinancialAuditRequestSchemaTests(unittest.TestCase):
    def test_numeric_json_values_are_accepted_and_normalized(self):
        request = AirFinancialAuditDataUpsert(
            source_type="shenzhen_air",
            source_id="370976932327723008",
            payable={
                "billing_pieces": 2,
                "billing_weight": 81,
                "chargeable_weight": 100,
                "freight_rate": 2.5,
                "air_freight": 250,
                "fuel_surcharge": 25,
                "total_cost": 275,
            },
            receivable={
                "waybill_number": "479-62200552",
                "pieces": 2,
                "chargeable_weight": 100,
                "total_amount": 250,
                "weight": 100,
                "freight": 250,
            },
        )

        self.assertEqual(request.source_id, "370976932327723008")
        self.assertEqual(request.payable.billing_pieces, "2")
        self.assertEqual(request.payable.billing_weight, "81")
        self.assertEqual(request.payable.freight_rate, "2.5")
        self.assertEqual(request.payable.total_cost, "275")
        self.assertEqual(request.receivable.pieces, "2")
        self.assertEqual(request.receivable.total_amount, "250")
        self.assertEqual(request.receivable.freight, "250")

    def test_existing_strings_none_and_decimal_are_preserved_or_normalized(self):
        request = PayableRequest(
            billing_pieces="2",
            billing_weight=None,
            freight_rate=Decimal("2.50"),
            other_fee_remark="人工填写",
        )

        self.assertEqual(request.billing_pieces, "2")
        self.assertIsNone(request.billing_weight)
        self.assertEqual(request.freight_rate, "2.50")
        self.assertEqual(request.other_fee_remark, "人工填写")

    def test_non_scalar_values_and_booleans_are_still_rejected(self):
        with self.assertRaises(ValidationError):
            ReceivableRequest(pieces=True)

        with self.assertRaises(ValidationError):
            ReceivableRequest(pieces=[2])

        with self.assertRaises(ValidationError):
            ReceivableRequest(pieces={"value": 2})

        with self.assertRaises(ValidationError):
            ReceivableRequest(pieces=float("nan"))


if __name__ == "__main__":
    unittest.main()
