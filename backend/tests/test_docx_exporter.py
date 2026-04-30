"""Tests for the lightweight markdown → DOCX converter."""
import io

from docx import Document

from services.docx_exporter import markdown_to_docx


def test_docx_renders_headings_and_bullets():
    md = (
        "# Demanda civil — ACME\n"
        "## Hechos\n"
        "- Primero: El demandado incumplió el contrato [E:e001]\n"
        "- Segundo: **El importe** es de 1.234 EUR\n"
        "## Fundamentos\n"
        "Solo *texto corrido* aquí.\n"
    )
    blob = markdown_to_docx("Demanda civil — ACME", md, footer_line="Galaxy Legal · test")
    assert isinstance(blob, bytes) and len(blob) > 2000  # non-trivial docx
    doc = Document(io.BytesIO(blob))
    texts = [p.text for p in doc.paragraphs]
    # Title + headings + at least one bullet line
    assert any(t.startswith("Demanda civil") for t in texts)
    assert any("Hechos" == t for t in texts)
    assert any("Primero" in t and "incumpli" in t for t in texts)
    # Footer line made it through
    section = doc.sections[0]
    footer_text = "\n".join(p.text for p in section.footer.paragraphs)
    assert "Galaxy Legal" in footer_text


def test_docx_handles_empty_lines():
    blob = markdown_to_docx("Title", "# Title\n\nA paragraph.\n\n- one\n- two\n")
    doc = Document(io.BytesIO(blob))
    # Ensure no exception and at least the two bullets are rendered
    joined = "\n".join(p.text for p in doc.paragraphs)
    assert "one" in joined and "two" in joined
