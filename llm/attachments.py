"""
Answering a question about an attached file (2026-09-20, see
docs/decisions.md) - closes the gap where attaching a file did
nothing except store it: `/api/ask` never received any mention of the
attachment, so "what's this?" fell through to whatever the ordinary
DAM pipeline made of a subject-less question (usually context
carry-over onto an unrelated activity).

Two paths, chosen by the attachment's content type:
  - Images go to GroqProvider.chat_with_image() - genuine vision, not
    a text description of the file.
  - Everything else (PDF, plain text, CSV, Word) gets its text
    extracted here and handed to the provider's ordinary chat() as
    context, the same way agent/generate.py hands facts to the model
    for DAM answers - the model is restricted to what's actually in
    the extracted text and told to say so plainly if the answer isn't
    there, rather than reaching for outside knowledge.

Excel attachments (.xls/.xlsx) and legacy .doc are on the upload
allowlist (webapp/storage.py) but not wired up here yet - both raise
UnsupportedAttachmentError with an honest explanation rather than
either crashing or silently pretending to have read them.
"""

import base64
import io

from llm.base import LLMUnavailableError

MAX_EXTRACTED_CHARS = 12_000

LANGUAGE_NAMES = {
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
}


class UnsupportedAttachmentError(Exception):
    """
    Raised for a file this module has no way to read - a type it
    doesn't know how to parse, a legacy format, or a file with no
    extractable text (e.g. a scanned PDF with no text layer). Distinct
    from LLMUnavailableError: this is "the file can't be read," not
    "the model couldn't be reached," and the caller (webapp/backend.py)
    returns it as a normal, honest answer rather than a 503.
    """


def _extract_pdf_text(contents: bytes) -> str:
    import pdfplumber

    parts = []
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _extract_docx_text(contents: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(contents))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_text(content_type: str, filename: str, contents: bytes) -> str:
    """
    Returns the readable text of a non-image attachment, truncated to
    MAX_EXTRACTED_CHARS (a whole DAM chapter's worth of prose is
    already more context than a single question needs, and an
    unbounded document would risk blowing the provider's context
    window or just being slow/expensive for no benefit). Raises
    UnsupportedAttachmentError for a type this can't parse, or a file
    that parses but has no text in it.
    """
    if content_type == "application/pdf":
        text = _extract_pdf_text(contents)
    elif content_type in ("text/plain", "text/csv"):
        text = contents.decode("utf-8", errors="replace")
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = _extract_docx_text(contents)
    elif content_type == "application/msword":
        raise UnsupportedAttachmentError(
            "This is an older .doc file, which isn't supported for reading yet - "
            "re-save it as .docx or PDF and attach that instead."
        )
    elif content_type in (
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        raise UnsupportedAttachmentError(
            "Reading spreadsheet attachments isn't supported yet - "
            "you can still download it, just not ask questions about its content."
        )
    else:
        raise UnsupportedAttachmentError(f"Reading {content_type!r} attachments isn't supported yet.")

    text = text.strip()
    if not text:
        raise UnsupportedAttachmentError(
            f"No readable text was found in {filename!r} - if it's a scanned "
            "document, it may have no text layer for this to read."
        )
    if len(text) > MAX_EXTRACTED_CHARS:
        text = text[:MAX_EXTRACTED_CHARS] + "\n...[truncated]"
    return text


def _language_instruction(target_language):
    if not target_language or target_language in ("auto", "en"):
        return ""
    name = LANGUAGE_NAMES.get(target_language, target_language)
    return f" Answer in {name}."


def answer_about_attachment(question, content_type, filename, contents, provider, target_language=None):
    """
    Returns {"text": ..., "provider": provider.name}. Raises
    UnsupportedAttachmentError (file can't be read) or
    LLMUnavailableError (model couldn't be reached, or an image was
    attached but the resolved provider can't do vision) - callers
    handle the two differently (see webapp/backend.py's /api/ask).
    """
    language_instruction = _language_instruction(target_language)

    if content_type.startswith("image/"):
        if not getattr(provider, "supports_vision", False):
            raise LLMUnavailableError(
                "Reading images needs the cloud (Groq) mode, which isn't available right now."
            )
        image_data_url = f"data:{content_type};base64,{base64.b64encode(contents).decode('ascii')}"
        system = (
            "You are answering a question about an image a user attached to a chat. "
            "Describe only what is actually visible in the image. If the question asks "
            "about something the image doesn't show, say so plainly rather than guessing."
            + language_instruction
        )
        text = provider.chat_with_image(system, question, image_data_url)
    else:
        extracted = extract_text(content_type, filename, contents)
        system = (
            f"You are answering a question about a document a user attached to a chat ({filename}). "
            "Answer only using the document text provided below. If the answer isn't in it, "
            "say so plainly rather than using outside knowledge."
            + language_instruction
        )
        user_prompt = f'Document content:\n"""\n{extracted}\n"""\n\nQuestion: {question}'
        text = provider.chat(system, user_prompt)

    return {"text": text, "provider": provider.name}
