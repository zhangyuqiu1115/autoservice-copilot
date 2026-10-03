from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import DocumentType
from app.schemas.document import (
    DocumentResponse,
    DocumentUploadMetadata,
)
from app.services import document as document_service

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: Annotated[
        UploadFile,
        File(description="PDF, TXT, or Markdown document."),
    ],
    title: Annotated[
        str,
        Form(min_length=1, max_length=200),
    ],
    document_type: Annotated[DocumentType, Form()],
    db: Annotated[Session, Depends(get_db)],
    vehicle_brand: Annotated[
        str | None,
        Form(max_length=50),
    ] = None,
    vehicle_model: Annotated[
        str | None,
        Form(max_length=100),
    ] = None,
    model_year: Annotated[
        int | None,
        Form(ge=2000, le=2100),
    ] = None,
) -> DocumentResponse:
    """上传知识库文档并保存元数据。"""

    if not title.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document title must not be blank.",
        )

    metadata = DocumentUploadMetadata(
        title=title,
        document_type=document_type,
        vehicle_brand=vehicle_brand,
        vehicle_model=vehicle_model,
        model_year=model_year,
    )

    try:
        return document_service.create_document(
            db,
            file,
            metadata,
        )
    except (
        document_service.UnsupportedDocumentFileError,
        document_service.InvalidDocumentContentTypeError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except document_service.EmptyDocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except document_service.DocumentTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except document_service.DocumentAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DocumentResponse]:
    """分页查询知识库文档。"""

    return document_service.list_documents(
        db,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    """根据 ID 查询知识库文档。"""

    try:
        return document_service.get_document_by_id(
            db,
            document_id,
        )
    except document_service.DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error