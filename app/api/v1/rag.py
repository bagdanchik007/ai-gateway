"""RAG-Endpoints: Dokumente hinzufügen und direkt durchsuchen.

Die eigentliche Nutzung im Chat läuft über `rag_collection` im
Chat-Completions-Request (app/api/v1/chat.py) — die Such-Route hier ist vor
allem zum Debuggen/Prüfen der Retrieval-Qualität gedacht, unabhängig von
einem konkreten Chat-Request.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_api_key
from app.db.session import get_db
from app.schemas.rag import DocumentAddRequest, DocumentAddResponse, SearchResponse, SearchResult
from app.services.rag.store import add_document, search

router = APIRouter(dependencies=[Depends(get_current_api_key)])


@router.post(
    "/documents",
    response_model=DocumentAddResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dokument chunken, embedden und speichern",
)
async def add_document_endpoint(
    body: DocumentAddRequest, db: AsyncSession = Depends(get_db)
) -> DocumentAddResponse:
    chunks = await add_document(db, body.text, collection=body.collection, source=body.source)
    return DocumentAddResponse(collection=body.collection, chunks_created=len(chunks))


@router.get("/search", response_model=SearchResponse, summary="Relevante Chunks abfragen")
async def search_endpoint(
    q: str,
    collection: str = "default",
    top_k: int = 3,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    results = await search(db, q, collection=collection, top_k=top_k)
    return SearchResponse(
        results=[
            SearchResult(content=chunk.content, score=score, source=chunk.source)
            for chunk, score in results
        ]
    )
