import unittest
from pathlib import Path

from app.schemas.cost_service import (
    PayableDomAir,
    PayableGround,
    PayableIntlAir,
    PayableTrucking,
)


class CostServiceSchemaTests(unittest.TestCase):
    def test_removed_intl_air_fields_are_not_api_fields(self):
        self.assertNotIn("airline", PayableIntlAir.model_fields)
        self.assertNotIn("date", PayableIntlAir.model_fields)

        payload = PayableIntlAir.model_validate(
            {
                "airline": "历史客户端字段",
                "date": "2026-08-27",
                "destination": "TPE",
            }
        )
        self.assertEqual(payload.destination, "TPE")
        self.assertNotIn("airline", payload.model_dump())
        self.assertNotIn("date", payload.model_dump())

    def test_domestic_air_airline_remains_available(self):
        self.assertIn("airline", PayableDomAir.model_fields)

    def test_other_payable_transport_dates_remain_available(self):
        self.assertIn("date", PayableTrucking.model_fields)
        self.assertIn("date", PayableDomAir.model_fields)
        self.assertIn("date", PayableGround.model_fields)

    def test_removed_intl_air_fields_are_not_in_orm_models(self):
        model_source = (
            Path(__file__).parents[1] / "app" / "models" / "cost_service.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("pay_intl_air_airline", model_source)
        self.assertNotIn("pay_intl_air_date", model_source)


if __name__ == "__main__":
    unittest.main()
