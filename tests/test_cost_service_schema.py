import unittest
from pathlib import Path

from app.schemas.cost_service import (
    CostConsignmentQuery,
    CostConsignmentSubmissionStatus,
    PayableDomAir,
    PayableGround,
    PayableIntlAir,
    PayableTrucking,
    ReceivablesInfo,
)


class CostServiceSchemaTests(unittest.TestCase):
    def test_list_date_filters_are_optional_and_independent(self):
        query = CostConsignmentQuery(start_flight_date="2026-09-20")

        self.assertEqual(query.start_flight_date, "2026-09-20")
        self.assertIsNone(query.end_flight_date)
        self.assertIsNone(query.start_warehouse_date)
        self.assertIsNone(query.end_warehouse_date)

    def test_cost_consignment_flight_date_filter_is_indexed(self):
        model_source = (
            Path(__file__).parents[1] / "app" / "models" / "cost_service.py"
        ).read_text(encoding="utf-8")
        create_script = (
            Path(__file__).parents[1]
            / "sql"
            / "migration_create_cost_service_consignments.sql"
        ).read_text(encoding="utf-8")
        migration_script = (
            Path(__file__).parents[1]
            / "sql"
            / "migration_add_cost_consignment_flight_date_index.sql"
        ).read_text(encoding="utf-8")

        cost_model_source = model_source.split("class CostConsignment(Base):", maxsplit=1)[1]
        self.assertIn(
            'flight_date = Column(Date, nullable=True, index=True, comment="航班日期")',
            cost_model_source,
        )
        self.assertIn("KEY `idx_flight_date` (`flight_date`)", create_script)
        self.assertIn("ADD INDEX `idx_flight_date` (`flight_date`)", migration_script)

    def test_consignment_submission_status_uses_numeric_values(self):
        self.assertEqual(CostConsignmentSubmissionStatus.UNSUBMITTED.value, 0)
        self.assertEqual(CostConsignmentSubmissionStatus.SUBMITTED.value, 1)
        self.assertEqual(CostConsignmentSubmissionStatus.VOIDED.value, 2)
    def test_receivables_include_freight_method(self):
        self.assertIn("freight_method", ReceivablesInfo.model_fields)
        self.assertIn("receivable_fuel_fee", ReceivablesInfo.model_fields)
        payload = ReceivablesInfo.model_validate(
            {
                "unit_price": 10,
                "freight_method": "按实际重量",
                "freight": 20,
                "receivable_fuel_fee": 30,
            }
        )
        self.assertEqual(payload.freight_method, "按实际重量")
        self.assertEqual(payload.receivable_fuel_fee, 30)

    def test_air_payables_include_freight_method(self):
        for schema in (PayableIntlAir, PayableDomAir):
            with self.subTest(schema=schema.__name__):
                self.assertIn("freight_method", schema.model_fields)
                payload = schema.model_validate({"rate": 10, "freight_method": "按实际重量", "freight": 20})
                self.assertEqual(payload.freight_method, "按实际重量")
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

    def test_fresh_database_script_places_status_on_list_table(self):
        migration_source = (
            Path(__file__).parents[1] / "sql" / "migration_create_cost_service_consignments.sql"
        ).read_text(encoding="utf-8")
        registration_sql, consignment_sql = migration_source.split(
            "CREATE TABLE IF NOT EXISTS `cost_consignments`", maxsplit=1,
        )
        self.assertNotIn("`status` tinyint", registration_sql)
        self.assertIn(
            "`status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '单据状态：0=未提交，1=已提交，2=作废'",
            consignment_sql,
        )


if __name__ == "__main__":
    unittest.main()
