from services.citation_validator import (
    EvidenceInput,
    parse_evidence_markers,
    validate_citations,
)


DOC_TEXT = (
    "El demandado, ACME S.A., incumplió el contrato firmado el 15 de marzo de 2024.\n"
    "El importe pendiente asciende a 12.345,67 EUROS según consta en la factura adjunta.\n"
)


def test_verbatim_match_passes():
    evs = [
        EvidenceInput(external_id="e1", document_id="d1", quote_excerpt="incumplió el contrato firmado el 15 de marzo de 2024"),
        EvidenceInput(external_id="e2", document_id="d1", quote_excerpt="12.345,67 EUROS"),
    ]
    res = validate_citations(evs, {"d1": DOC_TEXT})
    assert res.valid, res.errors
    assert set(res.verified_ids) == {"e1", "e2"}


def test_paraphrase_fails():
    evs = [
        EvidenceInput(external_id="e1", document_id="d1", quote_excerpt="ACME breached the contract on March 15"),
    ]
    res = validate_citations(evs, {"d1": DOC_TEXT})
    assert not res.valid
    assert res.errors[0].external_id == "e1"


def test_unknown_document_fails():
    evs = [
        EvidenceInput(external_id="e1", document_id="ghost", quote_excerpt="incumplió el contrato"),
    ]
    res = validate_citations(evs, {"d1": DOC_TEXT})
    assert not res.valid
    assert "ghost" in res.errors[0].reason


def test_short_excerpt_fails():
    evs = [
        EvidenceInput(external_id="e1", document_id="d1", quote_excerpt="ACME"),
    ]
    res = validate_citations(evs, {"d1": DOC_TEXT})
    assert not res.valid


def test_marker_parsing():
    md = "Esto es un hecho [E:e001] y otro [E:e002] y de nuevo [E:e001]."
    assert parse_evidence_markers(md) == ["e001", "e002"]


def test_whitespace_normalization():
    evs = [
        EvidenceInput(
            external_id="e1",
            document_id="d1",
            quote_excerpt="  incumplió   el  contrato firmado el 15 de marzo de 2024  ",
        ),
    ]
    res = validate_citations(evs, {"d1": DOC_TEXT})
    assert res.valid
