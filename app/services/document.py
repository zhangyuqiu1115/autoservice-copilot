from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.schemas.document import DocumentUploadMetadata

CHUNK_SIZE = 1024 * 1024

ALLOWED_FILE_TYPES = {
    ".pdf": frozenset({"application/pdf"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
}


class UnsupportedDocumentFileError(Exception):
    """文件扩展名不受支持。"""


class InvalidDocumentContentTypeError(Exception):
    """文件扩展名与 Content-Type 不匹配。"""


class EmptyDocumentError(Exception):
    """上传文件为空。"""


class DocumentTooLargeError(Exception):
    """上传文件超过大小限制。"""


class DocumentAlreadyExistsError(Exception):
    """相同内容的文档已经存在。"""

    def __init__(
        self,
        checksum: str,
        document_id: int | None = None,
    ) -> None:
        self.checksum = checksum
        self.document_id = document_id

        message = f"Document with checksum '{checksum}' already exists."

        if document_id is not None:
            message = (
                f"Document with checksum '{checksum}' already exists "
                f"as document ID {document_id}."
            )

        super().__init__(message)


class DocumentNotFoundError(Exception):
    """指定文档不存在。"""

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"Document with ID {document_id} was not found."
        )


def _validate_upload_file(
    upload_file: UploadFile,
) -> tuple[str, str]:
    """校验文件名、扩展名和 Content-Type。"""

    original_filename = Path(upload_file.filename or "").name

    if not original_filename:
        raise UnsupportedDocumentFileError(
            "The uploaded file must have a filename."
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_FILE_TYPES:
        allowed_extensions = ", ".join(
            sorted(ALLOWED_FILE_TYPES)
        )
        raise UnsupportedDocumentFileError(
            f"Unsupported file extension '{extension}'. "
            f"Allowed extensions: {allowed_extensions}."
        )

    content_type = (
        upload_file.content_type or ""
    ).split(";", maxsplit=1)[0].strip().lower()

    if content_type not in ALLOWED_FILE_TYPES[extension]:
        raise InvalidDocumentContentTypeError(
            f"Content-Type '{content_type}' is not valid "
            f"for '{extension}' files."
        )

    return original_filename, extension


def _write_temporary_file(
    upload_file: UploadFile,
    upload_directory: Path,
    max_size_bytes: int,
) -> tuple[Path, str]:
    """流式保存临时文件，同时计算 SHA-256。"""

    digest = sha256()
    total_size = 0

    with NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=upload_directory,
        suffix=".upload",
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

        try:
            upload_file.file.seek(0)

            while chunk := upload_file.file.read(CHUNK_SIZE):
                total_size += len(chunk)

                if total_size > max_size_bytes:
                    raise DocumentTooLargeError(
                        "Uploaded document exceeds the configured "
                        "size limit."
                    )

                digest.update(chunk)
                temporary_file.write(chunk)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    if total_size == 0:
        temporary_path.unlink(missing_ok=True)
        raise EmptyDocumentError(
            "The uploaded document is empty."
        )

    return temporary_path, digest.hexdigest()


def get_document_by_id(
    db: Session,
    document_id: int,
) -> Document:
    """根据 ID 查询文档。"""

    document = db.get(Document, document_id)

    if document is None:
        raise DocumentNotFoundError(document_id)

    return document


def list_documents(
    db: Session,
    offset: int = 0,
    limit: int = 20,
) -> list[Document]:
    """分页查询文档。"""

    statement = (
        select(Document)
        .order_by(Document.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def create_document(
    db: Session,
    upload_file: UploadFile,
    metadata: DocumentUploadMetadata,
) -> Document:
    """安全保存文件，并创建文档元数据。"""

    settings = get_settings()
    upload_directory = Path(settings.upload_directory)
    upload_directory.mkdir(parents=True, exist_ok=True)

    original_filename, extension = _validate_upload_file(
        upload_file
    )

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    temporary_path, checksum = _write_temporary_file(
        upload_file,
        upload_directory,
        max_size_bytes,
    )

    existing_document = db.scalar(
        select(Document).where(Document.checksum == checksum)
    )

    if existing_document is not None:
        temporary_path.unlink(missing_ok=True)
        raise DocumentAlreadyExistsError(
            checksum,
            existing_document.id,
        )

    stored_path = upload_directory / (
        f"{uuid4().hex}{extension}"
    )
    temporary_path.replace(stored_path)

    document = Document(
        **metadata.model_dump(),
        source_filename=original_filename,
        source_path=stored_path.as_posix(),
        checksum=checksum,
    )

    db.add(document)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise DocumentAlreadyExistsError(checksum) from error

    db.refresh(document)
    return document
