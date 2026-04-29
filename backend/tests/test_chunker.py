from services.chunker import chunk_text


def test_chunker_basic_splits_long_pages():
    long_para = "Lorem ipsum dolor sit amet. " * 80
    extracted = {
        "full_text": long_para,
        "pages": [{"page": 1, "text": long_para + "\n\n" + long_para}],
        "pages_count": 1,
    }
    chunks = chunk_text(extracted, target_tokens=200, overlap_tokens=20)
    assert len(chunks) >= 2
    # Each chunk has a positive token count and valid metadata.
    for c in chunks:
        assert c.token_count > 0
        assert c.page == 1
        assert c.chunk_index >= 0
        assert isinstance(c.chunk_text, str) and len(c.chunk_text) > 0


def test_chunker_preserves_overlap_between_chunks():
    text = "\n\n".join(f"Paragraph number {i} with some words to count." for i in range(40))
    extracted = {"full_text": text, "pages": [{"page": 1, "text": text}], "pages_count": 1}
    chunks = chunk_text(extracted, target_tokens=80, overlap_tokens=20)
    assert len(chunks) >= 2
    # Detect overlap: last paragraph of chunk N should appear in chunk N+1.
    for i in range(len(chunks) - 1):
        last = chunks[i].chunk_text.split("\n\n")[-1]
        assert last in chunks[i + 1].chunk_text


def test_chunker_handles_multiple_pages():
    pages = [
        {"page": 1, "text": "Page one content.\n\nMore content."},
        {"page": 2, "text": "Page two text here.\n\nFinal paragraph."},
    ]
    extracted = {"full_text": "ignored", "pages": pages, "pages_count": 2}
    chunks = chunk_text(extracted, target_tokens=400, overlap_tokens=20)
    assert {c.page for c in chunks} == {1, 2}
