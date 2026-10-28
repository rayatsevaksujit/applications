import unittest
from app import clean_table, safe_sheet_name
import pandas as pd

class HelperTests(unittest.TestCase):
    def test_clean_table_uses_header_and_keeps_rows(self):
        df = clean_table([["Name", "Class"], ["Asha", "5"], ["Rahul", "6"]])
        self.assertEqual(list(df.columns), ["Name", "Class"])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0, 0], "Asha")

    def test_clean_table_pads_short_rows(self):
        df = clean_table([["A", "B"], ["1"]])
        self.assertEqual(df.shape, (1, 2))
        self.assertEqual(df.iloc[0, 1], "")

    def test_sheet_names_are_unique_and_safe(self):
        used = set()
        one = safe_sheet_name("A/B.pdf", used)
        two = safe_sheet_name("A/B.pdf", used)
        self.assertNotEqual(one, two)
        self.assertNotIn("/", one)

if __name__ == "__main__":
    unittest.main()
