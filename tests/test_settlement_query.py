import unittest
from datetime import date

from app.schemas.settlement import SettlementQuery


class SettlementQueryTests(unittest.TestCase):
    def test_flight_date_range_parameters_are_parsed(self):
        query = SettlementQuery(
            flight_date_start="2026-10-21",
            flight_date_end="2026-10-22",
        )

        self.assertEqual(query.flight_date_start, date(2026, 10, 21))
        self.assertEqual(query.flight_date_end, date(2026, 10, 22))

    def test_old_record_time_parameters_are_not_used_as_flight_date_filters(self):
        query = SettlementQuery(
            airline_record_time_start="2026-10-21",
            airline_record_time_end="2026-10-22",
        )

        self.assertIsNone(query.flight_date_start)
        self.assertIsNone(query.flight_date_end)


if __name__ == "__main__":
    unittest.main()
