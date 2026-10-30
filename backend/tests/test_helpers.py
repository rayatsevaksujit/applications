import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import clean_table, safe_sheet_name, is_legacy_marathi_garbled

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

    def test_detects_legacy_encoded_marathi_text(self):
        legacy = "EòÉä±½þÉ{ÉÚ®ú ºÉÆºlÉäSÉä xÉÉÆ´É ¶ÉÉ³äýSÉä " * 5
        self.assertTrue(is_legacy_marathi_garbled(legacy))

    def test_does_not_flag_unicode_marathi(self):
        self.assertFalse(is_legacy_marathi_garbled("कोल्हापूर विभाग माध्यमिक शाळा " * 5))

    def test_sheet_names_are_unique_and_safe(self):
        used = set()
        one = safe_sheet_name("A/B.pdf", used)
        two = safe_sheet_name("A/B.pdf", used)
        self.assertNotEqual(one, two)
        self.assertNotIn("/", one)

if __name__ == "__main__":
    unittest.main()
