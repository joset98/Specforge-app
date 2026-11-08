import pytest
from conftest import make_blank_pdf, make_docx, make_pdf

from app.extract import ExtractionError, extract_text


def test_pdf():
    out = extract_text("req.pdf", make_pdf("Sistema de reservas"), None, 30000)
    assert "Sistema de reservas" in out


def test_docx_includes_table_cells():
    data = make_docx(["Intro"], [["El usuario puede reservar", "Alta"]])
    out = extract_text("req.docx", data, None, 30000)
    assert "Intro" in out and "El usuario puede reservar" in out


def test_plain_text_truncated():
    assert len(extract_text(None, None, "a" * 50, 10)) == 10


def test_txt_file():
    assert extract_text("r.txt", "hola ñandú".encode(), None, 100) == "hola ñandú"


def test_blank_pdf_rejected():
    with pytest.raises(ExtractionError, match="no selectable text"):
        extract_text("scan.pdf", make_blank_pdf(), None, 30000)


def test_whitespace_text_rejected():
    with pytest.raises(ExtractionError):
        extract_text(None, None, "   \n ", 30000)


def test_unsupported_extension_rejected():
    with pytest.raises(ExtractionError):
        extract_text("virus.exe", b"MZ", None, 30000)


def test_corrupt_docx_rejected():
    with pytest.raises(ExtractionError):
        extract_text("req.docx", b"not a zip", None, 30000)


def test_requires_exactly_one_source():
    with pytest.raises(ExtractionError):
        extract_text(None, None, None, 100)
