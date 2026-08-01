"""Tests für app/services/rag/chunking.py."""

import pytest
from app.services.rag.chunking import chunk_text


def test_short_text_produces_single_chunk() -> None:
    chunks = chunk_text("Hallo Welt", chunk_size=800, overlap=100)
    assert chunks == ["Hallo Welt"]


def test_long_text_is_split_into_multiple_overlapping_chunks() -> None:
    text = "A" * 2000
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 3
    # Ueberlappung: Ende von Chunk 1 und Anfang von Chunk 2 teilen sich Zeichen.
    assert chunks[0][-100:] == chunks[1][:100]


def test_empty_or_whitespace_only_chunks_are_dropped() -> None:
    chunks = chunk_text("  \n  ", chunk_size=800, overlap=100)
    assert chunks == []


def test_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("text", chunk_size=100, overlap=100)


def test_chunk_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("text", chunk_size=0, overlap=0)
