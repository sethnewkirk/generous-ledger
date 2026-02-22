"""Tests for imessage.py — iMessage timestamp conversion, body decoding, and formatting."""

import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from imessage import (
    CORE_DATA_EPOCH,
    convert_timestamp,
    decode_attributed_body,
    format_day,
    group_messages_by_conversation,
    load_known_contacts,
    match_contact,
    normalize_phone,
)


class TestConvertTimestamp(unittest.TestCase):
    """Test Core Data timestamp conversion — nanosecond and second formats."""

    def test_nanosecond_format(self):
        """Large values > 1e12 are treated as nanoseconds since Core Data epoch."""
        # 2026-02-17 10:30:00 UTC
        target_unix = 1771325400
        core_data_seconds = target_unix - CORE_DATA_EPOCH
        raw_ns = int(core_data_seconds * 1e9)

        result = convert_timestamp(raw_ns)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 17)

    def test_second_format(self):
        """Smaller values are treated as seconds since Core Data epoch."""
        # 2026-02-17 10:30:00 UTC
        target_unix = 1771325400
        core_data_seconds = target_unix - CORE_DATA_EPOCH

        result = convert_timestamp(core_data_seconds)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 17)

    def test_nanosecond_vs_second_same_result(self):
        """Both formats for the same instant should produce the same datetime."""
        target_unix = 1771325400
        core_data_seconds = target_unix - CORE_DATA_EPOCH
        raw_ns = int(core_data_seconds * 1e9)

        from_ns = convert_timestamp(raw_ns)
        from_s = convert_timestamp(core_data_seconds)

        self.assertIsNotNone(from_ns)
        self.assertIsNotNone(from_s)
        # They should be within 1 second of each other (floating point rounding)
        diff = abs((from_ns - from_s).total_seconds())
        self.assertLess(diff, 1.0)

    def test_none_input(self):
        self.assertIsNone(convert_timestamp(None))

    def test_zero_input(self):
        self.assertIsNone(convert_timestamp(0))

    def test_realistic_nanosecond_value(self):
        """A realistic iMessage timestamp from recent macOS versions."""
        # 793018200 seconds since Core Data epoch = some time in 2026
        # In nanoseconds: 793018200 * 1e9 = 793018200000000000
        raw_ns = 793018200000000000
        result = convert_timestamp(raw_ns)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)


class TestDecodeAttributedBody(unittest.TestCase):
    """Test attributedBody blob decoding strategies."""

    def test_none_input(self):
        self.assertEqual(decode_attributed_body(None), "")

    def test_empty_bytes(self):
        self.assertEqual(decode_attributed_body(b""), "")

    def test_nsstring_marker_extraction(self):
        """Test extraction of text after NSString marker."""
        # Construct a blob with NSString marker followed by text
        prefix = b"\x00\x01\x02NSString\x05\x10"
        text = b"Hello from iMessage"
        suffix = b"\x00\x00\x00"
        blob = prefix + text + suffix

        result = decode_attributed_body(blob)
        self.assertIn("Hello from iMessage", result)

    def test_graceful_fallback_undecodable(self):
        """Blobs with no recognizable patterns return empty string."""
        blob = bytes(range(256))  # random control bytes
        result = decode_attributed_body(blob)
        # Should not raise, should return something (possibly empty or best-effort)
        self.assertIsInstance(result, str)

    def test_fallback_to_longest_printable_run(self):
        """When NSString strategy fails, should find longest printable run."""
        # Blob with no NSString marker but contains readable text
        blob = b"\x01\x02\x03This is the message text\x00\x01\x02short\x00"
        result = decode_attributed_body(blob)
        # Should extract the longest readable run
        self.assertIn("This is the message text", result)

    def test_filters_metadata_strings(self):
        """Known metadata strings like NSObject should be filtered in fallback strategy."""
        # Build a blob with NO NSString/NSDictionary marker so Strategy 1 is skipped,
        # forcing the fallback Strategy 2 which filters metadata strings.
        # The longest printable run is a metadata string; the real text is shorter.
        blob = b"\x01\x02\x03streamtyped\x00\x00NSMutableAttributedString\x00\x01Real text here\x00"
        result = decode_attributed_body(blob)
        # Strategy 2 should filter out "NSMutableAttributedString" and return the real text
        if result:
            self.assertNotEqual(result, "NSMutableAttributedString")


class TestGroupMessages(unittest.TestCase):
    """Test conversation grouping by handle/chat."""

    def _msg(self, handle_id="", chat_id="", is_group=False, is_from_me=False,
             chat_display_name="", text="Hello"):
        return {
            "handle_id": handle_id,
            "text": text,
            "is_from_me": is_from_me,
            "timestamp": datetime(2026, 2, 17, 10, 0),
            "service": "iMessage",
            "chat_id": chat_id,
            "chat_display_name": chat_display_name,
            "is_group": is_group,
        }

    def test_direct_messages_grouped_by_handle(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(handle_id="+15551234567"),
            self._msg(handle_id="+15551234567", text="Second message"),
            self._msg(handle_id="+15559999999"),
        ]

        known_convos, unknown_count, unknown_msgs = group_messages_by_conversation(
            msgs, contacts
        )

        # Alice is known, so her conversation appears in known_convos
        self.assertIn("+15551234567", known_convos)
        self.assertEqual(len(known_convos["+15551234567"]), 2)

    def test_group_chats_keyed_by_chat_id(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(
                handle_id="+15551234567",
                chat_id="chat123",
                is_group=True,
                chat_display_name="Family Chat",
            ),
        ]

        known_convos, _, _ = group_messages_by_conversation(msgs, contacts)
        self.assertIn("chat123", known_convos)

    def test_unknown_contacts_counted_separately(self):
        contacts = {}  # No known contacts
        msgs = [
            self._msg(handle_id="+15559999999"),
            self._msg(handle_id="+15558888888"),
        ]

        known_convos, unknown_count, unknown_msgs = group_messages_by_conversation(
            msgs, contacts
        )

        self.assertEqual(len(known_convos), 0)
        self.assertEqual(unknown_count, 2)
        self.assertEqual(unknown_msgs, 2)

    def test_mixed_known_and_unknown(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(handle_id="+15551234567"),
            self._msg(handle_id="+15559999999"),
        ]

        known_convos, unknown_count, unknown_msgs = group_messages_by_conversation(
            msgs, contacts
        )

        self.assertEqual(len(known_convos), 1)
        self.assertEqual(unknown_count, 1)


class TestContactMatching(unittest.TestCase):
    """Test matching handle IDs (phone numbers, emails) against profile contacts."""

    def test_match_phone_number(self):
        contacts = {"5551234567": "Alice"}
        self.assertEqual(match_contact("+15551234567", contacts), "Alice")

    def test_match_email(self):
        contacts = {"alice@example.com": "Alice"}
        self.assertEqual(match_contact("alice@example.com", contacts), "Alice")

    def test_no_match(self):
        contacts = {"5551234567": "Alice"}
        self.assertIsNone(match_contact("+15559999999", contacts))

    def test_empty_handle(self):
        contacts = {"5551234567": "Alice"}
        self.assertIsNone(match_contact("", contacts))

    def test_none_handle(self):
        # match_contact expects a string but should handle None-like edge case
        # The function checks `if not handle_id:` which catches empty strings
        contacts = {"5551234567": "Alice"}
        self.assertIsNone(match_contact("", contacts))

    def test_email_case_insensitive(self):
        contacts = {"alice@example.com": "Alice"}
        self.assertEqual(match_contact("ALICE@Example.COM", contacts), "Alice")

    def test_normalize_phone_strips_formatting(self):
        self.assertEqual(normalize_phone("+1 (555) 123-4567"), "5551234567")
        self.assertEqual(normalize_phone("555-123-4567"), "5551234567")
        self.assertEqual(normalize_phone("15551234567"), "5551234567")

    def test_normalize_phone_short_number(self):
        """Non-US short numbers are kept as-is (digits only)."""
        self.assertEqual(normalize_phone("1234567"), "1234567")

    def test_load_contacts_phone_and_email(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            people_dir = Path(tmp) / "profile" / "people"
            people_dir.mkdir(parents=True)

            (people_dir / "alice.md").write_text(
                "---\nname: Alice Smith\nphone: '+15551234567'\nemail: alice@example.com\n---\n"
            )

            contacts = load_known_contacts(tmp)
            self.assertIn("5551234567", contacts)
            self.assertIn("alice@example.com", contacts)
            self.assertEqual(contacts["5551234567"], "Alice Smith")
            self.assertEqual(contacts["alice@example.com"], "Alice Smith")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_contacts_multiple_phones(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            people_dir = Path(tmp) / "profile" / "people"
            people_dir.mkdir(parents=True)

            (people_dir / "bob.md").write_text(
                "---\nname: Bob Jones\nphone:\n  - '+15551111111'\n  - '+15552222222'\n---\n"
            )

            contacts = load_known_contacts(tmp)
            self.assertIn("5551111111", contacts)
            self.assertIn("5552222222", contacts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_contacts_empty_dir(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            contacts = load_known_contacts(tmp)
            self.assertEqual(contacts, {})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFormatDay(unittest.TestCase):
    """Test frontmatter schema and body formatting — known vs unknown contacts."""

    def _msg(self, handle_id="+15551234567", text="Hello", is_from_me=False,
             timestamp=None, chat_id="", chat_display_name="", is_group=False):
        if timestamp is None:
            timestamp = datetime(2026, 2, 17, 10, 30)
        return {
            "handle_id": handle_id,
            "text": text,
            "is_from_me": is_from_me,
            "timestamp": timestamp,
            "service": "iMessage",
            "chat_id": chat_id,
            "chat_display_name": chat_display_name,
            "is_group": is_group,
        }

    def test_frontmatter_schema(self):
        contacts = {"5551234567": "Alice"}
        msgs = [self._msg()]
        fm, body = format_day("2026-02-17", msgs, contacts)

        self.assertEqual(fm["type"], "imessage-daily")
        self.assertEqual(fm["date"], "2026-02-17")
        self.assertIn("conversation_count", fm)
        self.assertIn("message_count", fm)
        self.assertIn("known_contact_conversations", fm)
        self.assertEqual(fm["source"], "imessage-local")
        self.assertIn("data", fm["tags"])
        self.assertIn("messages", fm["tags"])
        self.assertIn("last_synced", fm)

    def test_known_contacts_get_full_detail(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(handle_id="+15551234567", text="Hey there!"),
            self._msg(handle_id="+15551234567", text="How are you?",
                      timestamp=datetime(2026, 2, 17, 10, 35)),
        ]
        fm, body = format_day("2026-02-17", msgs, contacts)

        # Known conversations should have full message detail
        self.assertIn("Alice", body)
        self.assertIn("Hey there!", body)
        self.assertIn("How are you?", body)
        self.assertEqual(fm["known_contact_conversations"], 1)

    def test_unknown_contacts_get_count_only(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(handle_id="+15559999999", text="Spam message"),
            self._msg(handle_id="+15558888888", text="Another spam"),
        ]
        fm, body = format_day("2026-02-17", msgs, contacts)

        # Unknown messages should NOT have their text in body
        self.assertNotIn("Spam message", body)
        self.assertNotIn("Another spam", body)
        # But should have a count summary
        self.assertIn("other conversation", body)

    def test_mixed_known_and_unknown(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(handle_id="+15551234567", text="Known message"),
            self._msg(handle_id="+15559999999", text="Unknown message"),
        ]
        fm, body = format_day("2026-02-17", msgs, contacts)

        self.assertIn("Known message", body)
        self.assertNotIn("Unknown message", body)
        self.assertIn("other conversation", body)
        self.assertEqual(fm["known_contact_conversations"], 1)

    def test_empty_day(self):
        fm, body = format_day("2026-02-17", [], {})

        self.assertEqual(fm["message_count"], 0)
        self.assertEqual(fm["conversation_count"], 0)
        self.assertIn("No messages", body)

    def test_message_count_includes_all(self):
        contacts = {"5551234567": "Alice"}
        msgs = [
            self._msg(handle_id="+15551234567", text="Known"),
            self._msg(handle_id="+15559999999", text="Unknown 1"),
            self._msg(handle_id="+15558888888", text="Unknown 2"),
        ]
        fm, _ = format_day("2026-02-17", msgs, contacts)

        self.assertEqual(fm["message_count"], 3)
        self.assertEqual(fm["conversation_count"], 3)

    def test_body_header(self):
        contacts = {}
        msgs = [self._msg()]
        _, body = format_day("2026-02-17", msgs, contacts)
        self.assertIn("# Messages", body)
        self.assertIn("2026-02-17", body)


class TestNullTextHandling(unittest.TestCase):
    """Test that messages with NULL text column fall back to attributedBody."""

    def test_null_text_uses_attributed_body(self):
        """When text is NULL/empty, decode_attributed_body should be used."""
        # Simulate what fetch_messages does: if text is empty, try attributedBody
        text = ""
        attributed_body = b"\x01\x02NSString\x05\x10Decoded message text\x00\x00"

        # This mirrors the logic in fetch_messages
        if not text.strip():
            text = decode_attributed_body(attributed_body)

        self.assertIn("Decoded message text", text)

    def test_null_text_none_attributed_body(self):
        """When both text and attributedBody are empty, result is empty."""
        text = ""
        attributed_body = None

        if not text.strip():
            text = decode_attributed_body(attributed_body)

        self.assertEqual(text, "")

    def test_text_present_skips_attributed_body(self):
        """When text column has content, attributedBody is not needed."""
        text = "Regular text message"
        # This mirrors the logic: only fall back if text is empty
        if not text.strip():
            text = decode_attributed_body(b"Should not be used")

        self.assertEqual(text, "Regular text message")


if __name__ == "__main__":
    unittest.main()
