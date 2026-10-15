from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.rag import RagAnswerRequest, RagAnswerResponse
from app.services import document as document_service
from app.services import rag as rag_service
from app.services import vector_store as vector_store_service

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


@router.post(
    "/answer",
    response_model=RagAnswerResponse,
)
def answer_document_question(
    request: RagAnswerRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RagAnswerResponse:
    """检索售后文档并返回带来源引用的回答。"""

    try:
        if request.document_id is not None:
            document_service.get_document_by_id(db, request.document_id)

        return RagAnswerResponse.model_validate(
            rag_service.answer_question(
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
    except rag_service.RagServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
