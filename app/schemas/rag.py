"""Schemas für die RAG-Endpoints."""

from pydantic import BaseModel, Field


class DocumentAddRequest(BaseModel):
    text: str = Field(..., min_length=1)
    collection: str = Field(default="default")
    source: str | None = Field(default=None, description="Freitext-Referenz, z. B. Dateiname/URL")


class DocumentAddResponse(BaseModel):
    collection: str
    chunks_created: int


class SearchResult(BaseModel):
    content: str
    score: float
    source: str | None


class SearchResponse(BaseModel):
    results: list[SearchResult]
