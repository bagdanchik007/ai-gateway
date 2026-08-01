"""Einfaches Text-Chunking für RAG.

Feste Zeichenlänge mit Überlappung — kein satz-/absatzbewusstes Chunking.
Für den Einstieg ausreichend; ein semantischeres Chunking (z. B. entlang
Absatzgrenzen oder mit einem echten Tokenizer) ist ein Kandidat für eine
spätere Verfeinerung, sobald der Bedarf in der Praxis auftritt.
"""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Zerlegt `text` in überlappende Chunks fester Zeichenlänge."""
    if overlap >= chunk_size:
        raise ValueError("overlap muss kleiner als chunk_size sein")
    if chunk_size <= 0:
        raise ValueError("chunk_size muss positiv sein")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap

    return [c for c in chunks if c.strip()]
