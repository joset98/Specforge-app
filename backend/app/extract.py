import io
from pathlib import PurePath


class ExtractionError(ValueError):
    """User-facing reason why the input could not be turned into text."""


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise ExtractionError("This PDF has no selectable text (scanned?). Paste the text instead.")
    return text


def _docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    # Requirements docs often live in tables; include every cell.
    parts += [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
    return "\n".join(parts)


def _plain(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


READERS = {".pdf": _pdf, ".docx": _docx, ".txt": _plain, ".md": _plain}


def extract_text(filename: str | None, data: bytes | None, text: str | None, max_chars: int) -> str:
    if (data is None) == (text is None):
        raise ExtractionError("Send either text or a file.")
    if data is not None:
        ext = PurePath(filename or "").suffix.lower()
        reader = READERS.get(ext)
        if reader is None:
            raise ExtractionError("Unsupported file type. Use PDF, DOCX, TXT or MD.")
        try:
            text = reader(data)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError("The file could not be read. Is it corrupt?") from exc
    text = text.strip()
    if not text:
        raise ExtractionError("The requirement is empty.")
    return text[:max_chars]
