#!/usr/bin/env python3
"""
PDF 문서 변환 모듈

pdfplumber 기반 PDF → JSON 변환
- 텍스트 추출 (페이지별)
- 테이블 추출
- 섹션/조항 감지
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from docling.document_converter import DocumentConverter
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False


# 기본 출력 디렉토리 (기존 data/converted와 분리)
DEFAULT_OUTPUT_DIR = "data/converted_v2"

# 버전 정보
CONVERTER_VERSION = "2.0.0"


@dataclass
class PageData:
    """페이지 데이터"""
    page: int
    text: str
    char_count: int
    width: float
    height: float
    tables: List[str]  # 해당 페이지의 테이블 ID 목록


@dataclass
class TableData:
    """테이블 데이터"""
    table_id: str
    page: int
    rows: int
    cols: int
    headers: Optional[List[str]]
    data: List[List[str]]


@dataclass
class SectionData:
    """섹션/조항 데이터"""
    type: str  # clause, chapter, article, etc.
    title: str
    start_page: int
    end_page: int
    level: int = 1


class PDFConverter:
    """PDF 변환기"""

    # 보험 약관 섹션 패턴
    SECTION_PATTERNS = [
        # 관 (Chapter) - 제1관, 제2관 등
        (r'^제(\d+)관\s*[:\.]?\s*(.+?)(?:\s+\d+)?$', 'chapter', 1),
        # 조 (Article) - 제1조, 제2조 등
        (r'^제(\d+)조\s*\(([^)]+)\)', 'clause', 2),
        (r'^제(\d+)조의?\d*\s*\(([^)]+)\)', 'clause', 2),
        # 특별약관
        (r'^(\d+[-\.]\s*.+특별약관)', 'special_terms', 2),
        (r'^\d+[-\.]?\d*[-\.]?\s*(.+특별약관)', 'special_terms', 2),
        # 장 (Section)
        (r'^제(\d+)장\s*(.+?)(?:\s+\d+)?$', 'section', 1),
    ]

    def __init__(self, backend: str = "auto"):
        """
        Args:
            backend: "pdfplumber", "docling", or "auto"
        """
        self.backend = self._select_backend(backend)

    def _select_backend(self, backend: str) -> str:
        """사용 가능한 백엔드 선택"""
        if backend == "auto":
            if HAS_PDFPLUMBER:
                return "pdfplumber"
            elif HAS_DOCLING:
                return "docling"
            else:
                raise ImportError("No PDF backend available. Install pdfplumber or docling.")
        elif backend == "pdfplumber" and not HAS_PDFPLUMBER:
            raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")
        elif backend == "docling" and not HAS_DOCLING:
            raise ImportError("docling not installed. Run: pip install docling")
        return backend

    def convert(
        self,
        pdf_path: str,
        document_id: str,
        company_name: str,
        product_name: str,
        doc_type: str,
        version: str,
        effective_date: str,
        output_base_dir: str = DEFAULT_OUTPUT_DIR,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        PDF를 JSON으로 변환

        Args:
            pdf_path: PDF 파일 경로
            document_id: 문서 ID
            company_name: 보험사명
            product_name: 상품명
            doc_type: 문서 유형 (terms, proposal 등)
            version: 버전
            effective_date: 시행일
            output_base_dir: 출력 기본 디렉토리
            max_pages: 최대 페이지 수 (테스트용)

        Returns:
            변환 결과 딕셔너리
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # 출력 디렉토리 생성
        output_dir = Path(output_base_dir) / company_name.lower() / document_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 변환 실행
        if self.backend == "pdfplumber":
            result = self._convert_with_pdfplumber(pdf_path, max_pages)
        else:
            result = self._convert_with_docling(pdf_path, max_pages)

        pages_data = result["pages"]
        tables_data = result["tables"]
        total_pages = result["total_pages"]
        processed_pages = result["processed_pages"]

        # 섹션 추출
        sections = self._extract_sections(pages_data)

        # 파일 저장
        self._save_metadata(
            output_dir, document_id, company_name, product_name,
            doc_type, version, effective_date, pdf_path,
            total_pages, processed_pages
        )
        self._save_text(output_dir, pages_data)
        self._save_sections(output_dir, sections)
        tables_saved = self._save_tables(output_dir, tables_data)

        return {
            "output_dir": str(output_dir),
            "total_pages": total_pages,
            "processed_pages": processed_pages,
            "tables_extracted": tables_saved,
            "sections_detected": len(sections)
        }

    def _convert_with_pdfplumber(
        self,
        pdf_path: Path,
        max_pages: Optional[int]
    ) -> Dict[str, Any]:
        """pdfplumber를 사용한 변환"""
        pages_data: List[PageData] = []
        tables_data: List[TableData] = []

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_process = pdf.pages[:max_pages] if max_pages else pdf.pages

            for page in pages_to_process:
                page_num = page.page_number

                # 텍스트 추출
                text = page.extract_text() or ""

                # 페이지 크기
                width = page.width
                height = page.height

                # 테이블 추출
                page_table_ids = []
                extracted_tables = page.extract_tables() or []

                for idx, table in enumerate(extracted_tables):
                    if table and len(table) > 0:
                        table_id = f"table_{page_num:03d}_{idx+1:02d}"
                        page_table_ids.append(table_id)

                        # 테이블 데이터 정리
                        cleaned_table = self._clean_table(table)
                        if cleaned_table:
                            headers = cleaned_table[0] if len(cleaned_table) > 1 else None

                            tables_data.append(TableData(
                                table_id=table_id,
                                page=page_num,
                                rows=len(cleaned_table),
                                cols=len(cleaned_table[0]) if cleaned_table else 0,
                                headers=headers,
                                data=cleaned_table
                            ))

                pages_data.append(PageData(
                    page=page_num,
                    text=text,
                    char_count=len(text),
                    width=width,
                    height=height,
                    tables=page_table_ids
                ))

        return {
            "pages": pages_data,
            "tables": tables_data,
            "total_pages": total_pages,
            "processed_pages": len(pages_data)
        }

    def _convert_with_docling(
        self,
        pdf_path: Path,
        max_pages: Optional[int]
    ) -> Dict[str, Any]:
        """docling을 사용한 변환 (설치 시 사용)"""
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))

        # docling 결과를 표준 형식으로 변환
        pages_data: List[PageData] = []
        tables_data: List[TableData] = []

        # docling API에 따라 구현 필요
        # 현재는 placeholder
        doc = result.document
        total_pages = len(doc.pages) if hasattr(doc, 'pages') else 0

        # TODO: docling API 구조에 맞게 구현

        return {
            "pages": pages_data,
            "tables": tables_data,
            "total_pages": total_pages,
            "processed_pages": len(pages_data)
        }

    def _clean_table(self, table: List[List]) -> List[List[str]]:
        """테이블 데이터 정리"""
        if not table:
            return []

        cleaned = []
        for row in table:
            if row is None:
                continue
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    # 개행 정리, 공백 정규화
                    cell_str = str(cell).replace('\n', ' ').strip()
                    cell_str = re.sub(r'\s+', ' ', cell_str)
                    cleaned_row.append(cell_str)

            # 빈 행 제외
            if any(cell for cell in cleaned_row):
                cleaned.append(cleaned_row)

        return cleaned

    def _extract_sections(self, pages_data: List[PageData]) -> List[SectionData]:
        """페이지 텍스트에서 섹션/조항 추출"""
        sections = []

        for page_data in pages_data:
            lines = page_data.text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                for pattern, section_type, level in self.SECTION_PATTERNS:
                    match = re.match(pattern, line)
                    if match:
                        # 제목 추출
                        if section_type == 'clause':
                            title = f"제{match.group(1)}조 ({match.group(2)})"
                        elif section_type in ('chapter', 'section'):
                            title = f"제{match.group(1)}{'관' if section_type == 'chapter' else '장'} {match.group(2)}"
                        else:
                            title = match.group(1) if match.lastindex >= 1 else line

                        sections.append(SectionData(
                            type=section_type,
                            title=title,
                            start_page=page_data.page,
                            end_page=page_data.page,
                            level=level
                        ))
                        break

        return sections

    def _save_metadata(
        self,
        output_dir: Path,
        document_id: str,
        company_name: str,
        product_name: str,
        doc_type: str,
        version: str,
        effective_date: str,
        source_file: Path,
        total_pages: int,
        processed_pages: int
    ) -> None:
        """메타데이터 저장"""
        metadata = {
            "document_id": document_id,
            "company_name": company_name,
            "product_name": product_name,
            "doc_type": doc_type,
            "version": version,
            "effective_date": effective_date,
            "source_file": str(source_file.absolute()),
            "file_size_bytes": source_file.stat().st_size,
            "total_pages": total_pages,
            "processed_pages": processed_pages,
            "converted_at": datetime.now().isoformat(),
            "converter_version": CONVERTER_VERSION
        }

        with open(output_dir / "metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _save_text(self, output_dir: Path, pages_data: List[PageData]) -> None:
        """텍스트 데이터 저장"""
        text_output = {
            "pages": [asdict(p) for p in pages_data]
        }

        with open(output_dir / "text.json", 'w', encoding='utf-8') as f:
            json.dump(text_output, f, ensure_ascii=False, indent=2)

    def _save_sections(self, output_dir: Path, sections: List[SectionData]) -> None:
        """섹션 데이터 저장"""
        sections_output = {
            "sections": [asdict(s) for s in sections]
        }

        with open(output_dir / "sections.json", 'w', encoding='utf-8') as f:
            json.dump(sections_output, f, ensure_ascii=False, indent=2)

    def _save_tables(self, output_dir: Path, tables_data: List[TableData]) -> int:
        """테이블 데이터 저장"""
        if not tables_data:
            return 0

        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)

        # 테이블 인덱스
        tables_index = {
            "tables": []
        }

        for table in tables_data:
            # 개별 테이블 저장 (2D 배열 형태)
            table_file = tables_dir / f"{table.table_id}.json"
            with open(table_file, 'w', encoding='utf-8') as f:
                json.dump(table.data, f, ensure_ascii=False, indent=2)

            # 인덱스에 추가
            tables_index["tables"].append({
                "table_id": table.table_id,
                "page": table.page,
                "rows": table.rows,
                "cols": table.cols,
                "file": f"tables/{table.table_id}.json"
            })

        # 인덱스 저장
        with open(output_dir / "tables_index.json", 'w', encoding='utf-8') as f:
            json.dump(tables_index, f, ensure_ascii=False, indent=2)

        return len(tables_data)


# 편의 함수 (scripts/convert_documents.py에서 호출)
def convert_document(
    pdf_path: str,
    document_id: str,
    company_name: str,
    product_name: str,
    doc_type: str,
    version: str,
    effective_date: str,
    output_base_dir: str = DEFAULT_OUTPUT_DIR,
    max_pages: Optional[int] = None,
    backend: str = "auto"
) -> Dict[str, Any]:
    """
    PDF 문서를 JSON으로 변환

    Args:
        pdf_path: PDF 파일 경로
        document_id: 문서 ID
        company_name: 보험사명
        product_name: 상품명
        doc_type: 문서 유형
        version: 버전
        effective_date: 시행일
        output_base_dir: 출력 기본 디렉토리
        max_pages: 최대 페이지 수 (테스트용)
        backend: PDF 백엔드 ("pdfplumber", "docling", "auto")

    Returns:
        변환 결과 딕셔너리
    """
    converter = PDFConverter(backend=backend)
    return converter.convert(
        pdf_path=pdf_path,
        document_id=document_id,
        company_name=company_name,
        product_name=product_name,
        doc_type=doc_type,
        version=version,
        effective_date=effective_date,
        output_base_dir=output_base_dir,
        max_pages=max_pages
    )


if __name__ == "__main__":
    # 간단한 테스트
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_converter.py <pdf_path> [max_pages]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    result = convert_document(
        pdf_path=pdf_path,
        document_id="test-document",
        company_name="Test",
        product_name="Test Product",
        doc_type="terms",
        version="1.0",
        effective_date="2025-01-01",
        output_base_dir=DEFAULT_OUTPUT_DIR,
        max_pages=max_pages
    )

    print(f"Conversion complete:")
    print(f"  Output: {result['output_dir']}")
    print(f"  Pages: {result['processed_pages']}/{result['total_pages']}")
    print(f"  Tables: {result['tables_extracted']}")
    print(f"  Sections: {result['sections_detected']}")
