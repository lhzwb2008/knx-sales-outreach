import unittest

from backend.excel_import import callable_phone, lead_has_callable_phone


class PhoneRuleTests(unittest.TestCase):
    def test_mobile_must_be_eleven_digits(self):
        self.assertTrue(callable_phone("13800138000"))
        self.assertTrue(callable_phone("138 0013 8000"))
        self.assertTrue(callable_phone("+86 13800138000"))
        self.assertFalse(callable_phone("1"))
        self.assertFalse(callable_phone("12345"))
        self.assertFalse(callable_phone(""))

    def test_landline_is_area_plus_seven_or_eight(self):
        self.assertTrue(callable_phone("021-12345678"))
        self.assertTrue(callable_phone("0101234567"))
        self.assertTrue(callable_phone("0755-1234567"))
        self.assertTrue(callable_phone("075512345678"))
        self.assertFalse(callable_phone("021-1234"))
        self.assertFalse(callable_phone("0755-123456"))

    def test_lead_without_callable_phone_cannot_be_reached(self):
        self.assertFalse(lead_has_callable_phone({"phone": "1", "contacts": [{"phone": "1"}]}))
        self.assertTrue(lead_has_callable_phone({"phone": "1", "contacts": [{"phone": "13800138000"}]}))


if __name__ == "__main__":
    unittest.main()
