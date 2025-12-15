# Utils 모듈

유틸리티 함수 및 도구 모음입니다.

---

## pdf_converter.py

PDF 문서를 JSON 형식으로 변환하는 모듈입니다. 보험 약관 PDF를 구조화된 데이터로 추출합니다.

### 주요 기능

| 기능 | 설명 |
|------|------|
| 텍스트 추출 | 페이지별 텍스트 및 문자 수 추출 |
| 테이블 추출 | PDF 내 표 데이터를 2D 배열로 변환 |
| 섹션 감지 | 약관 구조 (관, 장, 조, 특별약관) 자동 인식 |
| 메타데이터 생성 | 문서 정보 및 변환 이력 저장 |

### 지원 백엔드

```python
PDFConverter(backend="auto")  # 자동 선택 (기본값)
PDFConverter(backend="pdfplumber")  # pdfplumber 사용
PDFConverter(backend="docling")  # docling 사용 (설치 필요)
```

- **pdfplumber**: 기본 백엔드. 안정적이고 가벼움
- **docling**: IBM의 문서 변환 라이브러리 (선택적)

### 데이터 클래스

#### PageData
```python
@dataclass
class PageData:
    page: int           # 페이지 번호
    text: str           # 추출된 텍스트
    char_count: int     # 문자 수
    width: float        # 페이지 너비
    height: float       # 페이지 높이
    tables: List[str]   # 해당 페이지의 테이블 ID 목록
```

#### TableData
```python
@dataclass
class TableData:
    table_id: str              # 테이블 ID (예: table_001_01)
    page: int                  # 페이지 번호
    rows: int                  # 행 수
    cols: int                  # 열 수
    headers: Optional[List[str]]  # 헤더 행
    data: List[List[str]]      # 테이블 데이터 (2D 배열)
```

#### SectionData
```python
@dataclass
class SectionData:
    type: str        # 섹션 유형 (clause, chapter, article, special_terms)
    title: str       # 섹션 제목
    start_page: int  # 시작 페이지
    end_page: int    # 종료 페이지
    level: int       # 계층 레벨 (1=최상위)
```

### 섹션 인식 패턴

보험 약관 문서의 구조를 자동으로 인식합니다:

| 패턴 | 유형 | 예시 |
|------|------|------|
| `제N관` | chapter | 제1관 일반사항 |
| `제N장` | section | 제1장 보험계약 |
| `제N조 (제목)` | clause | 제1조 (보험금의 지급사유) |
| `N. ~특별약관` | special_terms | 1. 암진단비특별약관 |

### 사용법

#### 기본 사용
```python
from utils.pdf_converter import convert_document

result = convert_document(
    pdf_path="data/pdf/samsung_cancer_terms.pdf",
    document_id="samsung-cancer-2024",
    company_name="삼성화재",
    product_name="무배당 암보험",
    doc_type="terms",
    version="2024.01",
    effective_date="2024-01-01"
)

print(result)
# {
#     "output_dir": "data/converted_v2/삼성화재/samsung-cancer-2024",
#     "total_pages": 150,
#     "processed_pages": 150,
#     "tables_extracted": 45,
#     "sections_detected": 89
# }
```

#### 클래스 직접 사용
```python
from utils.pdf_converter import PDFConverter

converter = PDFConverter(backend="pdfplumber")
result = converter.convert(
    pdf_path="document.pdf",
    document_id="doc-001",
    company_name="보험사",
    product_name="상품명",
    doc_type="terms",
    version="1.0",
    effective_date="2025-01-01",
    max_pages=10  # 테스트용 페이지 제한
)
```

#### CLI 실행
```bash
python utils/pdf_converter.py <pdf_path> [max_pages]

# 예시
python utils/pdf_converter.py data/pdf/test.pdf 5
```

### 출력 구조

변환 결과는 다음 구조로 저장됩니다:

```
data/converted_v2/
└── {company_name}/
    └── {document_id}/
        ├── metadata.json      # 문서 메타데이터
        ├── text.json          # 페이지별 텍스트
        ├── sections.json      # 섹션/조항 정보
        ├── tables_index.json  # 테이블 인덱스
        └── tables/
            ├── table_001_01.json
            ├── table_001_02.json
            └── ...
```

#### metadata.json
```json
{
  "document_id": "samsung-cancer-2024",
  "company_name": "삼성화재",
  "product_name": "무배당 암보험",
  "doc_type": "terms",
  "version": "2024.01",
  "effective_date": "2024-01-01",
  "source_file": "/absolute/path/to/source.pdf",
  "file_size_bytes": 1234567,
  "total_pages": 150,
  "processed_pages": 150,
  "converted_at": "2025-01-15T10:30:00.000000",
  "converter_version": "2.0.0"
}
```

#### text.json
```json
{
  "pages": [
    {
      "page": 1,
      "text": "보험약관 내용...",
      "char_count": 1500,
      "width": 595.0,
      "height": 842.0,
      "tables": ["table_001_01"]
    }
  ]
}
```

#### sections.json
```json
{
  "sections": [
    {
      "type": "chapter",
      "title": "제1관 일반사항",
      "start_page": 3,
      "end_page": 3,
      "level": 1
    },
    {
      "type": "clause",
      "title": "제1조 (보험금의 지급사유)",
      "start_page": 4,
      "end_page": 4,
      "level": 2
    }
  ]
}
```

### 설정

| 상수 | 값 | 설명 |
|------|------|------|
| `DEFAULT_OUTPUT_DIR` | `data/converted_v2` | 기본 출력 디렉토리 |
| `CONVERTER_VERSION` | `2.0.0` | 변환기 버전 |

### 의존성

```bash
# 필수
pip install pdfplumber

# 선택적 (docling 백엔드 사용 시)
pip install docling
```

### 내부 메서드

| 메서드 | 설명 |
|--------|------|
| `_select_backend()` | 사용 가능한 PDF 백엔드 선택 |
| `_convert_with_pdfplumber()` | pdfplumber로 PDF 변환 |
| `_convert_with_docling()` | docling으로 PDF 변환 |
| `_clean_table()` | 테이블 데이터 정제 (공백, 개행 정리) |
| `_extract_sections()` | 텍스트에서 섹션 구조 추출 |
| `_save_metadata()` | 메타데이터 JSON 저장 |
| `_save_text()` | 텍스트 JSON 저장 |
| `_save_sections()` | 섹션 JSON 저장 |
| `_save_tables()` | 테이블 JSON 저장 |
