from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.document_parser import (
    EmptyDocumentContentError,
    UnsupportedDocumentFormatError,
    extract_text_from_document,
    normalize_text,
    split_text_into_chunks,
)


def test_normalize_text() -> None:
    """测试换行、行内空格和空白段落规范化。"""

    raw_text = (
        "  First\t line  \r\n"
        "\r\n"
        "\r\n"
        "  Second   line  "
    )

    normalized_text = normalize_text(raw_text)

    assert normalized_text == (
        "First line\n\nSecond line"
    )


@pytest.mark.parametrize(
    "extension",
    [
        ".txt",
        ".md",
    ],
)
def test_extract_text_from_plain_text_document(
    tmp_path: Path,
    extension: str,
) -> None:
    """测试 TXT 和 Markdown 文档文本提取。"""

    document_path = tmp_path / f"manual{extension}"
    document_path.write_text(
        "  Charging\t safety  \n\n"
        "Inspect the connector.  ",
        encoding="utf-8",
    )

    extracted_text = extract_text_from_document(
        document_path
    )

    assert extracted_text == (
        "Charging safety\n\n"
        "Inspect the connector."
    )


@patch("app.services.document_parser.PdfReader")
def test_extract_text_from_pdf(
    mock_pdf_reader: MagicMock,
    tmp_path: Path,
) -> None:
    """测试 PDF 多页文本提取与合并。"""

    document_path = tmp_path / "manual.pdf"
    document_path.write_bytes(b"%PDF-1.4")

    first_page = MagicMock()
    first_page.extract_text.return_value = (
        " Page one text. "
    )

    second_page = MagicMock()
    second_page.extract_text.return_value = (
        " Page two text. "
    )

    mock_pdf_reader.return_value.pages = [
        first_page,
        second_page,
    ]

    extracted_text = extract_text_from_document(
        document_path
    )

    assert extracted_text == (
        "Page one text.\n\n"
        "Page two text."
    )

    mock_pdf_reader.assert_called_once_with(
        document_path
    )


def test_split_text_into_overlapping_chunks() -> None:
    """测试分块长度和相邻块重叠内容。"""

    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 20

    chunks = split_text_into_chunks(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 7
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert chunks[0][-20:] == chunks[1][:20]


def test_split_text_rejects_invalid_overlap() -> None:
    """重叠长度不能大于或等于分块长度。"""

    with pytest.raises(
        ValueError,
        match="smaller than chunk_size",
    ):
        split_text_into_chunks(
            "Valid text",
            chunk_size=100,
            chunk_overlap=100,
        )


def test_extract_text_rejects_empty_document(
    tmp_path: Path,
) -> None:
    """没有有效文本的文档应被拒绝。"""

    document_path = tmp_path / "empty.txt"
    document_path.write_text(
        "\n\t  \n",
        encoding="utf-8",
    )

    with pytest.raises(
        EmptyDocumentContentError,
        match="does not contain extractable text",
    ):
        extract_text_from_document(document_path)


def test_extract_text_rejects_unsupported_format(
    tmp_path: Path,
) -> None:
    """不支持的文件扩展名应被拒绝。"""

    document_path = tmp_path / "manual.csv"
    document_path.write_text(
        "unsupported",
        encoding="utf-8",
    )

    with pytest.raises(
        UnsupportedDocumentFormatError,
        match="Unsupported document extension",
    ):
        extract_text_from_document(document_path)
        