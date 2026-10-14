from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.retrieval import (
    RetrievalRequest,
    RetrievedChunkResponse,
)
from app.services import (
    document as document_service,
)
from app.services import (
    vector_store as vector_store_service,
)

router = APIRouter(
    prefix="/retrieval",
    tags=["retrieval"],
)


@router.post(
    "/search",
    response_model=list[RetrievedChunkResponse],
)
def search_document_chunks(
    request: RetrievalRequest,
    db: Annotated[Session, Depends(get_db)],
) -> list[RetrievedChunkResponse]:
    """根据自然语言问题检索最相关的文档文本块。"""

    try:
        if request.document_id is not None:
            document_service.get_document_by_id(
                db,
                request.document_id,
            )

        return (
            vector_store_service.search_document_chunks(
                request.query,
                limit=request.limit,
                document_id=request.document_id,
            )
        )
    except document_service.DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except vector_store_service.VectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
