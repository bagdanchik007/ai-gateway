"""Tests für die Cosine-Similarity-Berechnung in app/services/rag/store.py."""

from app.services.rag.store import _cosine_similarity


def test_identical_vectors_have_similarity_one() -> None:
    v = [1.0, 2.0, 3.0]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9


def test_orthogonal_vectors_have_similarity_zero() -> None:
    assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_opposite_vectors_have_similarity_minus_one() -> None:
    assert abs(_cosine_similarity([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-9


def test_zero_vector_returns_zero_instead_of_dividing_by_zero() -> None:
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
