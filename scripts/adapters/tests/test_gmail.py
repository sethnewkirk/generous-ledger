"""Tests for gmail.py — Gmail message parsing, contact matching, and formatting."""

import base64
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent))
from gmail import (
    extract_body_text,
    extract_sender_email,
    extract_sender_name,
    format_day,
    get_header,
    group_by_sender,
    load_known_contacts,
    parse_message,
    fetch_messages,
    strip_html_tags,
)


def _make_gmail_message(
    msg_id="msg_001",
    thread_id="thread_001",
    from_header="Alice Smith <alice@example.com>",
    subject="Test Subject",
    date_header="Mon, 17 Feb 2026 10:30:00 -0500",
    labels=None,
    body_text="Hello, this is a test email.",
    body_html=None,
):
    """Build a realistic Gmail API message dict for testing."""
    if labels is None:
        labels = ["INBOX", "UNREAD", "CATEGORY_PRIMARY"]

    # Encode body as base64url
    encoded_text = base64.urlsafe_b64encode(body_text.encode()).decode() if body_text else ""
    encoded_html = base64.urlsafe_b64encode(body_html.encode()).decode() if body_html else ""

    headers = [
        {"name": "From", "value": from_header},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": date_header},
    ]

    if body_text and body_html:
        payload = {
            "mimeType": "multipart/alternative",
            "headers": headers,
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded_text}},
                {"mimeType": "text/html", "body": {"data": encoded_html}},
            ],
        }
    elif body_text:
        payload = {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": encoded_text},
        }
    elif body_html:
        payload = {
            "mimeType": "text/html",
            "headers": headers,
            "body": {"data": encoded_html},
        }
    else:
        payload = {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": ""},
        }

    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": labels,
        "payload": payload,
    }


class TestParseMessage(unittest.TestCase):
    """Test message metadata extraction from Gmail API responses."""

    def test_basic_message_parsing(self):
        msg = _make_gmail_message()
        known = {"alice@example.com": "Alice Smith"}
        parsed = parse_message(msg, known)

        self.assertEqual(parsed["id"], "msg_001")
        self.assertEqual(parsed["thread_id"], "thread_001")
        self.assertEqual(parsed["from_name"], "Alice Smith")
        self.assertEqual(parsed["from_email"], "alice@example.com")
        self.assertEqual(parsed["subject"], "Test Subject")
        self.assertTrue(parsed["is_unread"])
        self.assertTrue(parsed["is_known_contact"])
        self.assertEqual(parsed["contact_name"], "Alice Smith")

    def test_date_parsing(self):
        msg = _make_gmail_message(date_header="Tue, 18 Feb 2026 14:00:00 +0000")
        parsed = parse_message(msg, {})
        self.assertIsNotNone(parsed["date"])
        self.assertEqual(parsed["date"].year, 2026)
        self.assertEqual(parsed["date"].month, 2)
        self.assertEqual(parsed["date"].day, 18)
        self.assertIn("2026-02-18", parsed["date_str"])

    def test_invalid_date_header(self):
        msg = _make_gmail_message(date_header="not-a-date")
        parsed = parse_message(msg, {})
        self.assertIsNone(parsed["date"])
        self.assertEqual(parsed["date_str"], "")

    def test_missing_subject_defaults(self):
        msg = _make_gmail_message(subject="")
        # Manually clear the subject header
        for h in msg["payload"]["headers"]:
            if h["name"] == "Subject":
                h["value"] = ""
        parsed = parse_message(msg, {})
        self.assertEqual(parsed["subject"], "(no subject)")

    def test_labels_extraction(self):
        msg = _make_gmail_message(labels=["INBOX", "IMPORTANT", "STARRED"])
        parsed = parse_message(msg, {})
        self.assertIn("INBOX", parsed["labels"])
        self.assertIn("IMPORTANT", parsed["labels"])
        self.assertFalse(parsed["is_unread"])

    def test_body_plain_text(self):
        msg = _make_gmail_message(body_text="Plain text body here.")
        parsed = parse_message(msg, {})
        self.assertEqual(parsed["body"], "Plain text body here.")

    def test_body_html_fallback(self):
        msg = _make_gmail_message(
            body_text=None,
            body_html="<p>HTML <b>body</b> here.</p>",
        )
        parsed = parse_message(msg, {})
        self.assertIn("HTML", parsed["body"])
        self.assertIn("body", parsed["body"])
        # HTML tags should be stripped
        self.assertNotIn("<p>", parsed["body"])
        self.assertNotIn("<b>", parsed["body"])

    def test_multipart_prefers_plain_text(self):
        msg = _make_gmail_message(
            body_text="Plain version",
            body_html="<p>HTML version</p>",
        )
        parsed = parse_message(msg, {})
        self.assertEqual(parsed["body"], "Plain version")

    def test_unknown_contact(self):
        msg = _make_gmail_message(from_header="stranger@unknown.com")
        parsed = parse_message(msg, {"alice@example.com": "Alice"})
        self.assertFalse(parsed["is_known_contact"])
        self.assertEqual(parsed["contact_name"], "")

    def test_empty_body(self):
        msg = _make_gmail_message(body_text="", body_html=None)
        parsed = parse_message(msg, {})
        self.assertEqual(parsed["body"], "")


class TestHeaderExtraction(unittest.TestCase):
    """Test low-level header and sender extraction."""

    def test_get_header_case_insensitive(self):
        msg = _make_gmail_message()
        self.assertEqual(get_header(msg, "from"), "Alice Smith <alice@example.com>")
        self.assertEqual(get_header(msg, "FROM"), "Alice Smith <alice@example.com>")
        self.assertEqual(get_header(msg, "From"), "Alice Smith <alice@example.com>")

    def test_get_header_missing(self):
        msg = _make_gmail_message()
        self.assertEqual(get_header(msg, "X-Custom-Header"), "")

    def test_extract_sender_email_with_name(self):
        self.assertEqual(extract_sender_email("Alice Smith <alice@example.com>"), "alice@example.com")

    def test_extract_sender_email_bare(self):
        self.assertEqual(extract_sender_email("bob@example.com"), "bob@example.com")

    def test_extract_sender_email_uppercase(self):
        self.assertEqual(extract_sender_email("Alice <ALICE@Example.COM>"), "alice@example.com")

    def test_extract_sender_name_with_name(self):
        self.assertEqual(extract_sender_name("Alice Smith <alice@example.com>"), "Alice Smith")

    def test_extract_sender_name_bare_email(self):
        self.assertEqual(extract_sender_name("alice@example.com"), "alice@example.com")


class TestStripHtmlTags(unittest.TestCase):
    """Test HTML-to-text conversion for email bodies."""

    def test_strip_basic_tags(self):
        result = strip_html_tags("<p>Hello <b>world</b></p>")
        self.assertIn("Hello", result)
        self.assertIn("world", result)
        self.assertNotIn("<", result)

    def test_strip_style_blocks(self):
        html = "<style>body { color: red; }</style><p>Content</p>"
        result = strip_html_tags(html)
        self.assertNotIn("color", result)
        self.assertIn("Content", result)

    def test_br_becomes_newline(self):
        result = strip_html_tags("Line 1<br>Line 2<br/>Line 3")
        self.assertIn("Line 1", result)
        self.assertIn("Line 2", result)

    def test_html_entities(self):
        result = strip_html_tags("&amp; &lt; &gt; &quot; &#39; &nbsp;")
        self.assertIn("&", result)
        self.assertIn("<", result)
        self.assertIn(">", result)


class TestContactMatching(unittest.TestCase):
    """Test loading contacts from profile/people/*.md files."""

    def test_load_contacts_from_frontmatter(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            people_dir = Path(tmp) / "profile" / "people"
            people_dir.mkdir(parents=True)

            (people_dir / "alice.md").write_text(
                "---\nname: Alice Smith\nemail: alice@example.com\n---\nSome notes.\n"
            )
            (people_dir / "bob.md").write_text(
                "---\nname: Bob Jones\nemail:\n  - bob@work.com\n  - bob@personal.com\n---\n"
            )

            contacts = load_known_contacts(tmp)
            self.assertEqual(contacts["alice@example.com"], "Alice Smith")
            self.assertEqual(contacts["bob@work.com"], "Bob Jones")
            self.assertEqual(contacts["bob@personal.com"], "Bob Jones")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_contacts_scans_body_for_emails(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            people_dir = Path(tmp) / "profile" / "people"
            people_dir.mkdir(parents=True)

            (people_dir / "charlie.md").write_text(
                "---\nname: Charlie Brown\n---\nContact: charlie@peanuts.com\n"
            )

            contacts = load_known_contacts(tmp)
            self.assertEqual(contacts["charlie@peanuts.com"], "Charlie Brown")
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

    def test_load_contacts_no_frontmatter(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            people_dir = Path(tmp) / "profile" / "people"
            people_dir.mkdir(parents=True)

            (people_dir / "nofm.md").write_text("Just some plain text, no frontmatter.\n")

            contacts = load_known_contacts(tmp)
            self.assertEqual(contacts, {})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_email_lowercased(self):
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            people_dir = Path(tmp) / "profile" / "people"
            people_dir.mkdir(parents=True)

            (people_dir / "upper.md").write_text(
                "---\nname: Upper Case\nemail: UPPER@Example.COM\n---\n"
            )

            contacts = load_known_contacts(tmp)
            self.assertIn("upper@example.com", contacts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFormatDay(unittest.TestCase):
    """Test frontmatter schema and body formatting for daily email files."""

    def _make_parsed_message(self, **overrides):
        defaults = {
            "id": "msg_001",
            "thread_id": "thread_001",
            "from_name": "Alice Smith",
            "from_email": "alice@example.com",
            "subject": "Hello there",
            "date": datetime(2026, 2, 17, 10, 30),
            "date_str": "2026-02-17 10:30",
            "labels": ["INBOX", "UNREAD"],
            "body": "Test body content.",
            "is_unread": True,
            "is_known_contact": True,
            "contact_name": "Alice Smith",
        }
        defaults.update(overrides)
        return defaults

    def test_frontmatter_schema(self):
        msgs = [self._make_parsed_message()]
        fm, body = format_day("2026-02-17", msgs)

        self.assertEqual(fm["type"], "email-daily")
        self.assertEqual(fm["date"], "2026-02-17")
        self.assertEqual(fm["message_count"], 1)
        self.assertEqual(fm["unread_count"], 1)
        self.assertEqual(fm["known_contact_messages"], 1)
        self.assertEqual(fm["source"], "gmail")
        self.assertIn("data", fm["tags"])
        self.assertIn("email", fm["tags"])
        self.assertIn("last_synced", fm)

    def test_frontmatter_counts_multiple_messages(self):
        msgs = [
            self._make_parsed_message(id="m1", is_unread=True, is_known_contact=True),
            self._make_parsed_message(id="m2", is_unread=False, is_known_contact=True),
            self._make_parsed_message(id="m3", is_unread=True, is_known_contact=False, contact_name=""),
        ]
        fm, _ = format_day("2026-02-17", msgs)

        self.assertEqual(fm["message_count"], 3)
        self.assertEqual(fm["unread_count"], 2)
        self.assertEqual(fm["known_contact_messages"], 2)

    def test_body_contains_sender_grouping(self):
        msgs = [
            self._make_parsed_message(from_name="Alice Smith", from_email="alice@example.com"),
            self._make_parsed_message(
                id="m2", from_name="Bob Jones", from_email="bob@example.com",
                is_known_contact=False, contact_name="",
            ),
        ]
        _, body = format_day("2026-02-17", msgs)

        self.assertIn("Alice Smith", body)
        self.assertIn("Bob Jones", body)

    def test_body_contains_subject_and_content(self):
        msgs = [self._make_parsed_message(subject="Important meeting", body="Let's discuss.")]
        _, body = format_day("2026-02-17", msgs)

        self.assertIn("Important meeting", body)
        self.assertIn("Let's discuss.", body)

    def test_empty_day(self):
        fm, body = format_day("2026-02-17", [])

        self.assertEqual(fm["message_count"], 0)
        self.assertEqual(fm["unread_count"], 0)
        self.assertIn("No messages", body)

    def test_known_contacts_appear_first(self):
        msgs = [
            self._make_parsed_message(
                id="m1", from_name="Stranger", from_email="stranger@example.com",
                is_known_contact=False, contact_name="",
                date=datetime(2026, 2, 17, 12, 0),
            ),
            self._make_parsed_message(
                id="m2", from_name="Alice", from_email="alice@example.com",
                is_known_contact=True, contact_name="Alice",
                date=datetime(2026, 2, 17, 8, 0),
            ),
        ]
        _, body = format_day("2026-02-17", msgs)

        # Known contact section should come before unknown
        alice_pos = body.find("Alice")
        stranger_pos = body.find("Stranger")
        self.assertLess(alice_pos, stranger_pos)

    def test_thread_organization_by_sender(self):
        msgs = [
            self._make_parsed_message(
                id="m1", thread_id="t1", subject="Thread 1",
                date=datetime(2026, 2, 17, 9, 0),
            ),
            self._make_parsed_message(
                id="m2", thread_id="t1", subject="Re: Thread 1",
                date=datetime(2026, 2, 17, 11, 0),
            ),
        ]
        _, body = format_day("2026-02-17", msgs)

        # Both messages from same sender should be grouped
        self.assertIn("Thread 1", body)
        self.assertIn("Re: Thread 1", body)

    def test_unread_marker_in_body(self):
        msgs = [self._make_parsed_message(is_unread=True)]
        _, body = format_day("2026-02-17", msgs)
        self.assertIn("unread", body.lower())


class TestDeduplication(unittest.TestCase):
    """Test that messages appearing in both primary and known-contact queries are deduplicated."""

    def test_fetch_messages_deduplicates_by_id(self):
        """Messages that appear in both primary and contact queries should appear only once."""
        service = MagicMock()

        # Primary query returns msg_001 and msg_002
        primary_response = {"messages": [{"id": "msg_001"}, {"id": "msg_002"}]}
        # Contact query returns msg_002 and msg_003 (msg_002 overlaps)
        contact_response = {"messages": [{"id": "msg_002"}, {"id": "msg_003"}]}

        # Build the mock chain for messages().list().execute()
        list_mock = MagicMock()
        # First call (primary), second call (contacts)
        list_mock.execute.side_effect = [primary_response, contact_response]
        messages_mock = MagicMock()
        messages_mock.list.return_value = list_mock
        users_mock = MagicMock()
        users_mock.messages.return_value = messages_mock

        # Mock the get() call for each unique message
        def mock_get(userId, id, format):
            mock_exec = MagicMock()
            mock_exec.execute.return_value = _make_gmail_message(
                msg_id=id, subject=f"Subject for {id}"
            )
            return mock_exec

        messages_mock.get.side_effect = mock_get
        service.users.return_value = users_mock

        known = {"friend@example.com": "Friend"}
        result = fetch_messages(service, days=1, known_contacts=known)

        # Should have exactly 3 unique messages, not 4
        self.assertEqual(len(result), 3)
        result_ids = [m["id"] for m in result]
        self.assertEqual(result_ids, ["msg_001", "msg_002", "msg_003"])

    def test_fetch_messages_no_contacts(self):
        """With no known contacts, only primary query runs."""
        service = MagicMock()

        primary_response = {"messages": [{"id": "msg_001"}]}
        list_mock = MagicMock()
        list_mock.execute.return_value = primary_response
        messages_mock = MagicMock()
        messages_mock.list.return_value = list_mock
        users_mock = MagicMock()
        users_mock.messages.return_value = messages_mock

        def mock_get(userId, id, format):
            mock_exec = MagicMock()
            mock_exec.execute.return_value = _make_gmail_message(msg_id=id)
            return mock_exec

        messages_mock.get.side_effect = mock_get
        service.users.return_value = users_mock

        result = fetch_messages(service, days=1, known_contacts={})
        self.assertEqual(len(result), 1)

    def test_fetch_messages_empty_results(self):
        """Empty API response returns no messages."""
        service = MagicMock()

        list_mock = MagicMock()
        list_mock.execute.return_value = {}  # No "messages" key
        messages_mock = MagicMock()
        messages_mock.list.return_value = list_mock
        users_mock = MagicMock()
        users_mock.messages.return_value = messages_mock
        service.users.return_value = users_mock

        result = fetch_messages(service, days=1, known_contacts={})
        self.assertEqual(len(result), 0)


class TestGroupBySender(unittest.TestCase):
    """Test sender grouping logic."""

    def test_groups_by_email(self):
        msgs = [
            {"from_email": "a@test.com", "date": datetime(2026, 2, 17, 9, 0)},
            {"from_email": "b@test.com", "date": datetime(2026, 2, 17, 10, 0)},
            {"from_email": "a@test.com", "date": datetime(2026, 2, 17, 11, 0)},
        ]
        grouped = group_by_sender(msgs)
        self.assertEqual(len(grouped["a@test.com"]), 2)
        self.assertEqual(len(grouped["b@test.com"]), 1)

    def test_sorts_within_sender_by_date(self):
        msgs = [
            {"from_email": "a@test.com", "date": datetime(2026, 2, 17, 14, 0)},
            {"from_email": "a@test.com", "date": datetime(2026, 2, 17, 8, 0)},
        ]
        grouped = group_by_sender(msgs)
        dates = [m["date"] for m in grouped["a@test.com"]]
        self.assertEqual(dates[0], datetime(2026, 2, 17, 8, 0))
        self.assertEqual(dates[1], datetime(2026, 2, 17, 14, 0))


if __name__ == "__main__":
    unittest.main()
