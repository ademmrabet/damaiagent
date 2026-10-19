# answer questions about an uploaded file

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


# raised for a file type we cannot read
class UnsupportedAttachmentError(Exception):
    pass


# read all text from an uploaded pdf
def _extract_pdf_text(contents: bytes) -> str:
    import pdfplumber

    parts = []
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


# read all paragraphs from an uploaded word file
def _extract_docx_text(contents: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(contents))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


# readable text of a pdf or word attachment, cut to a max length
def extract_text(content_type: str, filename: str, contents: bytes) -> str:
    if content_type == "application/pdf":
        text = _extract_pdf_text(contents)
    elif content_type in ("text/plain", "text/csv"):
        text = contents.decode("utf-8", errors="replace")
    elif (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
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
        raise UnsupportedAttachmentError(
            f"Reading {content_type!r} attachments isn't supported yet."
        )

    text = text.strip()
    if not text:
        raise UnsupportedAttachmentError(
            f"No readable text was found in {filename!r} - if it's a scanned "
            "document, it may have no text layer for this to read."
        )
    if len(text) > MAX_EXTRACTED_CHARS:
        text = text[:MAX_EXTRACTED_CHARS] + "\n...[truncated]"
    return text


# extra prompt text asking for the answer in the chosen language
def _language_instruction(target_language):
    if not target_language or target_language in ("auto", "en"):
        return ""
    name = LANGUAGE_NAMES.get(target_language, target_language)
    return f" Answer in {name}."


# ask the llm about the attachment (text or image)
def answer_about_attachment(
    question, content_type, filename, contents, provider, target_language=None
):
    language_instruction = _language_instruction(target_language)

    if content_type.startswith("image/"):
        if not getattr(provider, "supports_vision", False):
            raise LLMUnavailableError(
                "Reading images needs the cloud (Groq) mode, which isn't available right now."
            )
        image_data_url = (
            f"data:{content_type};base64,{base64.b64encode(contents).decode('ascii')}"
        )
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
            "say so plainly rather than using outside knowledge." + language_instruction
        )
        user_prompt = (
            f'Document content:\n"""\n{extracted}\n"""\n\nQuestion: {question}'
        )
        text = provider.chat(system, user_prompt)

    return {"text": text, "provider": provider.name}
