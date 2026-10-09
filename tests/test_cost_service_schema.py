import unittest
from pathlib import Path

from app.schemas.cost_service import (
    CostRegistrationSave,
    CostConsignmentQuery,
    CostConsignmentSubmissionStatus,
    DiscountInfo,
    PayableDomAir,
    PayableGround,
    PayableIntlAir,
    PayableTrucking,
    ReceivablesInfo,
)
from app.api.cost_service import _apply_cost_payload, _format_cost_record
from app.models.cost_service import CostConsignment, CostRegistration


class CostServiceSchemaTests(unittest.TestCase):
    def test_ground_fees_round_trip_and_preserve_existing_update_semantics(self):
        for model in (CostRegistration, CostConsignment):
            with self.subTest(model=model.__name__):
                record = model(id=1, pay_ground_freight=120, pay_ground_subtotal=200, pay_total=500)
                if model is CostConsignment:
                    record.status = CostConsignmentSubmissionStatus.SUBMITTED.value
                ground = _format_cost_record(record)["payables"]["ground"]
                self.assertIsNone(ground["tc_fee"])
                self.assertIsNone(ground["pickup_fee"])
                _apply_cost_payload(record, CostRegistrationSave.model_validate({
                    "payables": {"ground": {"tc_fee": 35.5, "pickup_fee": 20}},
                }))
                ground = _format_cost_record(record)["payables"]["ground"]
                self.assertEqual(ground["freight"], 120)
                self.assertEqual(ground["tc_fee"], 35.5)
                self.assertEqual(ground["pickup_fee"], 20)
                self.assertEqual(ground["subtotal"], 200)
                self.assertEqual(record.pay_total, 500)

                for body in ({}, {"payables": None}, {"payables": {"ground": None}},
                             {"payables": {"ground": {"tc_fee": None, "pickup_fee": None}}}):
                    _apply_cost_payload(record, CostRegistrationSave.model_validate(body))
                    self.assertEqual(record.pay_ground_tc_fee, 35.5)
                    self.assertEqual(record.pay_ground_pickup_fee, 20)
                _apply_cost_payload(record, CostRegistrationSave.model_validate({
                    "payables": {"ground": {"tc_fee": 0, "pickup_fee": 0}},
                }))
                ground = _format_cost_record(record)["payables"]["ground"]
                self.assertEqual(ground["tc_fee"], 0)
                self.assertEqual(ground["pickup_fee"], 0)

    def test_discount_info_rate_round_trips_through_both_cost_models(self):
        self.assertIn("discount_rate", DiscountInfo.model_fields)
        payload = CostRegistrationSave.model_validate(
            {
                "discount_info": {
                    "discount_person": "张三",
                    "discount_rate": 7.25,
                    "discount_fee": 88.5,
                }
            }
        )

        for model in (CostRegistration, CostConsignment):
            with self.subTest(model=model.__name__):
                model_fields = {"id": 1, "discount_rate": 3.5}
                if model is CostConsignment:
                    model_fields["status"] = CostConsignmentSubmissionStatus.SUBMITTED.value
                record = model(**model_fields)
                _apply_cost_payload(record, payload)
                self.assertEqual(record.discount_rate, 7.25)
                self.assertEqual(
                    _format_cost_record(record)["discount_info"],
                    {
                        "discount_person": "张三",
                        "discount_rate": 7.25,
                        "discount_fee": 88.5,
                    },
                )

                _apply_cost_payload(
                    record,
                    CostRegistrationSave.model_validate(
                        {"discount_info": {"discount_rate": 0}}
                    ),
                )
                self.assertEqual(record.discount_rate, 0)
                _apply_cost_payload(
                    record,
                    CostRegistrationSave.model_validate(
                        {"discount_info": {"discount_fee": 99}}
                    ),
                )
                self.assertEqual(record.discount_rate, 0)

    def test_discount_rate_is_present_in_models_and_database_scripts(self):
        for model in (CostRegistration, CostConsignment):
            with self.subTest(model=model.__name__):
                column = model.__table__.columns["discount_rate"]
                self.assertTrue(column.nullable)
                self.assertEqual(column.type.precision, 10)
                self.assertEqual(column.type.scale, 2)

        project_root = Path(__file__).parents[1]
        create_script = (
            project_root / "sql" / "migration_create_cost_service_consignments.sql"
        ).read_text(encoding="utf-8")
        migration_script = (
            project_root / "sql" / "migration_add_cost_discount_rate.sql"
        ).read_text(encoding="utf-8")
        expected_column = "`discount_rate` decimal(10,2) DEFAULT NULL COMMENT '折让费率'"
        self.assertEqual(create_script.count(expected_column), 2)
        self.assertEqual(migration_script.count(expected_column), 2)
        self.assertIn("ALTER TABLE `cost_registrations`", migration_script)
        self.assertIn("ALTER TABLE `cost_consignments`", migration_script)

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
