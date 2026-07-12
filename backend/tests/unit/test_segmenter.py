from services.ingestion.segmenter import hash_text, segment_clauses


def test_segment_clauses_splits_on_numbered_headings():
    text = """1. A firm must appoint a compliance officer.

2. The compliance officer must report to the board annually.

3. Failure to comply is a criminal offence."""
    clauses = segment_clauses(text)
    assert [c.clause_ref for c in clauses] == ["s.1", "s.2", "s.3"]
    assert clauses[0].text == "A firm must appoint a compliance officer."
    assert clauses[0].ordinal == 1


def test_segment_clauses_supports_alphanumeric_suffixes():
    text = "12A. A subsidiary provision."
    clauses = segment_clauses(text)
    assert clauses[0].clause_ref == "s.12A"


def test_segment_clauses_falls_back_to_sequential_ref_when_unnumbered():
    text = """Introductory recital with no number.

1. First real clause."""
    clauses = segment_clauses(text)
    assert clauses[0].clause_ref == "cl.1"
    assert clauses[1].clause_ref == "s.1"


def test_segment_clauses_never_drops_a_paragraph():
    text = "\n\n".join(f"{i}. Clause number {i}." for i in range(1, 11))
    clauses = segment_clauses(text)
    assert len(clauses) == 10


def test_hash_text_is_deterministic_and_content_sensitive():
    assert hash_text("hello") == hash_text("hello")
    assert hash_text("hello") != hash_text("hello!")
