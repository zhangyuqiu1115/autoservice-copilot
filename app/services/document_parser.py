import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED_DOCUMENT_EXTENSIONS = frozenset(
    {
        ".md",
        ".pdf",
        ".txt",
    }
)

INLINE_WHITESPACE_PATTERN = re.compile(r"[ \t\f\v]+")

NATURAL_SEPARATORS = (
    "\n\n",
    "\n",
    "。",
    ". ",
    "！",
    "! ",
    "？",
    "? ",
    "；",
    "; ",
)

MINIMUM_SPLIT_RATIO = 0.6


class DocumentParsingError(Exception):
    """文档解析错误的基础异常。"""


class UnsupportedDocumentFormatError(DocumentParsingError):
    """文档格式不受支持。"""


class DocumentTextExtractionError(DocumentParsingError):
    """无法从文档中提取文本。"""


class EmptyDocumentContentError(DocumentParsingError):
    """文档中没有可处理的文本。"""


def normalize_text(text: str) -> str:
    """统一换行和空白，同时保留段落边界。"""

    normalized_newlines = (
        text.replace("\r\n", "\n").replace("\r", "\n")
    )

    normalized_lines: list[str] = []
    previous_line_was_blank = True

    for raw_line in normalized_newlines.split("\n"):
        line = INLINE_WHITESPACE_PATTERN.sub(
            " ",
            raw_line,
        ).strip()

        if line:
            normalized_lines.append(line)
            previous_line_was_blank = False
        elif not previous_line_was_blank:
            normalized_lines.append("")
            previous_line_was_blank = True

    return "\n".join(normalized_lines).strip()


def _extract_pdf_text(document_path: Path) -> str:
    """提取 PDF 每一页的文本。"""

    reader = PdfReader(document_path)

    page_texts = [
        page.extract_text() or ""
        for page in reader.pages
    ]

    return "\n\n".join(page_texts)


def extract_text_from_document(
    file_path: str | Path,
) -> str:
    """根据文件扩展名提取并规范化文档文本。"""

    document_path = Path(file_path)

    if not document_path.is_file():
        raise DocumentTextExtractionError(
            f"Document file '{document_path}' does not exist."
        )

    extension = document_path.suffix.lower()

    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        allowed_extensions = ", ".join(
            sorted(SUPPORTED_DOCUMENT_EXTENSIONS)
        )
        raise UnsupportedDocumentFormatError(
            f"Unsupported document extension '{extension}'. "
            f"Allowed extensions: {allowed_extensions}."
        )

    try:
        if extension == ".pdf":
            extracted_text = _extract_pdf_text(document_path)
        else:
            extracted_text = document_path.read_text(
                encoding="utf-8-sig"
            )
    except (
        OSError,
        UnicodeError,
        PdfReadError,
    ) as error:
        raise DocumentTextExtractionError(
            f"Could not extract text from "
            f"'{document_path.name}'."
        ) from error

    normalized_text = normalize_text(extracted_text)

    if not normalized_text:
        raise EmptyDocumentContentError(
            f"Document '{document_path.name}' "
            f"does not contain extractable text."
        )

    return normalized_text


def _find_natural_split_position(
    text: str,
    start: int,
    maximum_end: int,
) -> int:
    """在块长度范围内寻找尽量靠后的自然分隔符。"""

    if maximum_end >= len(text):
        return len(text)

    minimum_end = start + int(
        (maximum_end - start) * MINIMUM_SPLIT_RATIO
    )

    best_position = -1
    best_separator = ""

    for separator in NATURAL_SEPARATORS:
        position = text.rfind(
            separator,
            minimum_end,
            maximum_end,
        )

        if position > best_position:
            best_position = position
            best_separator = separator

    if best_position == -1:
        return maximum_end

    return best_position + len(best_separator)


def split_text_into_chunks(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """按字符长度分块，并在相邻块之间保留重叠文本。"""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap must be zero or greater."
        )

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size."
        )

    normalized_text = normalize_text(text)

    if not normalized_text:
        raise EmptyDocumentContentError(
            "Document does not contain extractable text."
        )

    chunks: list[str] = []
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        maximum_end = min(
            start + chunk_size,
            text_length,
        )

        end = _find_natural_split_position(
            normalized_text,
            start,
            maximum_end,
        )

        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = max(
            end - chunk_overlap,
            start + 1,
        )

        while (
            next_start < text_length
            and normalized_text[next_start].isspace()
        ):
            next_start += 1

        start = next_start

    return chunks


def extract_and_chunk_document(
    file_path: str | Path,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """提取文档文本并将其拆分为可检索的文本块。"""

    text = extract_text_from_document(file_path)

    return split_text_into_chunks(
        text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )