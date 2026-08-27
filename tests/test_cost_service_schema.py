import unittest
from pathlib import Path

from app.schemas.cost_service import PayableDomAir, PayableIntlAir


class CostServiceSchemaTests(unittest.TestCase):
    def test_intl_air_airline_is_not_an_api_field(self):
        self.assertNotIn("airline", PayableIntlAir.model_fields)

        payload = PayableIntlAir.model_validate(
            {"airline": "历史客户端字段", "destination": "TPE"}
        )
        self.assertEqual(payload.destination, "TPE")
        self.assertNotIn("airline", payload.model_dump())

    def test_domestic_air_airline_remains_available(self):
        self.assertIn("airline", PayableDomAir.model_fields)

    def test_intl_air_airline_is_removed_from_orm_models(self):
        model_source = (
            Path(__file__).parents[1] / "app" / "models" / "cost_service.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("pay_intl_air_airline", model_source)


if __name__ == "__main__":
    unittest.main()
