"""
Tests for llm/attachments.py - answering a question about an attached
file (2026-09-20, see docs/decisions.md). webapp/backend.py's own
attachment branch of /api/ask is covered separately in
tests/test_backend.py; these tests exercise the extraction and
provider-orchestration logic in isolation, the same way test_llm.py
tests each provider without a real network call.
"""

import io
from unittest.mock import MagicMock, Mock, patch

import pytest

from llm.attachments import (
    MAX_EXTRACTED_CHARS,
    UnsupportedAttachmentError,
    answer_about_attachment,
    extract_text,
)
from llm.base import LLMUnavailableError


def _make_docx_bytes(paragraphs):
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _fake_pdf_context(pages_text):
    pdf = MagicMock()
    pdf.pages = [MagicMock(extract_text=MagicMock(return_value=t)) for t in pages_text]
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=pdf)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestExtractText:
    def test_plain_text(self):
        text = extract_text("text/plain", "notes.txt", b"who approves 2.126?")
        assert text == "who approves 2.126?"

    def test_csv_uses_the_same_plain_text_path(self):
        text = extract_text("text/csv", "data.csv", b"id,role\n2.126,Sector Manager")
        assert "2.126" in text

    def test_pdf_extracts_and_joins_pages(self):
        with patch("pdfplumber.open", return_value=_fake_pdf_context(["Page one text.", "Page two text."])):
            text = extract_text("application/pdf", "doc.pdf", b"%PDF-fake-bytes")
        assert "Page one text." in text
        assert "Page two text." in text

    def test_pdf_with_no_text_layer_raises_unsupported(self):
        with patch("pdfplumber.open", return_value=_fake_pdf_context([None, ""])):
            with pytest.raises(UnsupportedAttachmentError):
                extract_text("application/pdf", "scanned.pdf", b"%PDF-fake-bytes")

    def test_docx_extracts_real_paragraph_text(self):
        contents = _make_docx_bytes(["First paragraph.", "Second paragraph about 3.111."])
        text = extract_text(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "memo.docx",
            contents,
        )
        assert "First paragraph." in text
        assert "3.111" in text

    def test_legacy_doc_raises_unsupported_with_a_clear_message(self):
        with pytest.raises(UnsupportedAttachmentError, match="doc"):
            extract_text("application/msword", "old.doc", b"anything")

    def test_excel_raises_unsupported_with_a_clear_message(self):
        with pytest.raises(UnsupportedAttachmentError, match="spreadsheet"):
            extract_text(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "sheet.xlsx",
                b"anything",
            )

    def test_unknown_type_raises_unsupported(self):
        with pytest.raises(UnsupportedAttachmentError):
            extract_text("application/zip", "archive.zip", b"anything")

    def test_empty_text_raises_unsupported(self):
        with pytest.raises(UnsupportedAttachmentError):
            extract_text("text/plain", "empty.txt", b"   \n  ")

    def test_long_text_is_truncated(self):
        long_text = ("word " * 5000).encode("utf-8")
        text = extract_text("text/plain", "long.txt", long_text)
        assert len(text) <= MAX_EXTRACTED_CHARS + len("\n...[truncated]")
        assert text.endswith("...[truncated]")


class TestAnswerAboutAttachment:
    def test_text_attachment_calls_chat_with_extracted_content(self):
        provider = Mock(name="groq")
        provider.name = "groq"
        provider.chat = Mock(return_value="Sector Manager approves it.")

        result = answer_about_attachment(
            "who approves this?", "text/plain", "notes.txt", b"2.126 is approved by Sector Manager", provider
        )

        assert result == {"text": "Sector Manager approves it.", "provider": "groq"}
        system, user_prompt = provider.chat.call_args.args
        assert "notes.txt" in system
        assert "outside knowledge" in system
        assert "Sector Manager" in user_prompt
        assert "who approves this?" in user_prompt

    def test_text_attachment_adds_language_instruction(self):
        provider = Mock(name="groq")
        provider.name = "groq"
        provider.chat = Mock(return_value="reponse")

        answer_about_attachment(
            "question", "text/plain", "notes.txt", b"content", provider, target_language="fr"
        )

        system = provider.chat.call_args.args[0]
        assert "French" in system

    def test_unsupported_attachment_type_propagates(self):
        provider = Mock()
        with pytest.raises(UnsupportedAttachmentError):
            answer_about_attachment("question", "application/zip", "f.zip", b"x", provider)

    def test_image_attachment_uses_vision_when_supported(self):
        provider = Mock(name="groq")
        provider.name = "groq"
        provider.supports_vision = True
        provider.chat_with_image = Mock(return_value="A diagram of authority codes.")

        result = answer_about_attachment("what's this?", "image/png", "shot.png", b"\x89PNG...", provider)

        assert result == {"text": "A diagram of authority codes.", "provider": "groq"}
        system, user_text, image_data_url = provider.chat_with_image.call_args.args
        assert user_text == "what's this?"
        assert image_data_url.startswith("data:image/png;base64,")

    def test_image_attachment_without_vision_support_raises_unavailable(self):
        provider = Mock(name="ollama")
        provider.name = "ollama"
        provider.supports_vision = False

        with pytest.raises(LLMUnavailableError):
            answer_about_attachment("what's this?", "image/png", "shot.png", b"\x89PNG...", provider)

    def test_image_attachment_defaults_to_no_vision_support_when_unset(self):
        # A bare Mock() would otherwise auto-create a truthy
        # `supports_vision` attribute and silently pass this check -
        # spec'd here to a plain object with no such attribute to make
        # sure the real getattr(..., False) default is what's doing
        # the work, not Mock's own attribute-conjuring behaviour.
        class BareProvider:
            name = "ollama"

        with pytest.raises(LLMUnavailableError):
            answer_about_attachment("what's this?", "image/png", "shot.png", b"\x89PNG...", BareProvider())
