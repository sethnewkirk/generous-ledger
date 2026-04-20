"""Tests for contacts.py — formatting Apple Contacts data into vault entries."""

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from contacts import format_contact


class TestContactsAdapter(unittest.TestCase):
    def test_format_contact_basic(self):
        fm, body = format_contact(
            {
                "id": "ABCD1234EFGH5678",
                "name": "Max Smith",
                "organization": "Acme",
                "nickname": "Max",
                "birthday": "1989-03-14T00:00:00Z",
                "emails": ["max@example.com"],
                "phones": ["+1 (555) 123-4567"],
                "urls": ["https://example.com"],
                "note": "Church friend",
            }
        )

        self.assertEqual(fm["type"], "contact-entry")
        self.assertEqual(fm["name"], "Max Smith")
        self.assertEqual(fm["birthday"], "1989-03-14")
        self.assertIn("max@example.com", fm["emails"])
        self.assertIn("Phones:", body)
        self.assertIn("Church friend", body)


if __name__ == "__main__":
    unittest.main()
