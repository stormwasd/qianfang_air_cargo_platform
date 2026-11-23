import unittest

from sqlalchemy import Text

from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData


class ChinaSouthernAirApprovalModelTests(unittest.TestCase):
    def test_container_column_supports_variable_length_values(self):
        column_type = ChinaSouthernAirApprovalData.__table__.c.container.type

        self.assertIsInstance(column_type, Text)


if __name__ == "__main__":
    unittest.main()
