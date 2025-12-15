# 새 보험사 추가 가이드

새로운 보험사와 문서가 추가될 때 필요한 작업 순서와 관련 모듈을 설명합니다.

---

## 시뮬레이션: "AIA생명" 추가

가정: AIA생명의 암보험 관련 PDF 문서(약관, 가입설계서)가 추가되는 상황

---

## Phase 1: PDF 파일 준비

### 1.1 파일 배치

```
examples/aia/
├── AIA_약관.pdf
├── AIA_가입설계서(남).pdf
├── AIA_가입설계서(여).pdf
└── AIA_사업방법서.pdf
```

### 1.2 파일명 규칙

| 패턴 | 예시 | 설명 |
|------|------|------|
| `{회사명}_{문서타입}.pdf` | `AIA_약관.pdf` | 기본 형식 |
| `{회사명}_{문서타입}({변형}).pdf` | `AIA_가입설계서(남).pdf` | 성별/나이 변형 |
| `{회사명}_{문서타입}({변형})_{YYMM}.pdf` | `AIA_가입설계서(남)_2512.pdf` | 버전 포함 |

**문서타입 매핑:**
- `약관` → terms
- `가입설계서` → proposal
- `사업방법서` → business_spec
- `상품요약서` → product_summary
- `쉬운요약서` → easy_summary

---

## Phase 2: PDF → JSON 변환

### 2.1 관련 모듈

```
scripts/convert_documents.py (CLI 진입점)
    └── utils/pdf_converter.py (핵심 변환 로직)
```

### 2.2 수정 필요 파일

#### `scripts/convert_documents.py` (Line 41-50)

회사 코드 매핑 추가:

```python
carrier_map = {
    '삼성': 'samsung',
    'DB': 'db',
    '롯데': 'lotte',
    '한화': 'hanwha',
    '현대': 'hyundai',
    'KB': 'kb',
    '메리츠': 'meritz',
    '흥국': 'heungkuk',
    'AIA': 'aia',          # ← 추가
}
```

### 2.3 실행

```bash
# 전체 변환
python scripts/convert_documents.py --output-dir data/converted_v2

# AIA만 변환
python scripts/convert_documents.py --company-code aia --output-dir data/converted_v2
```

### 2.4 출력 결과

```
data/converted_v2/aia/
├── aia-terms/
│   ├── document.json      # 문서 메타데이터
│   ├── full_text.txt      # 전체 텍스트
│   ├── pages/             # 페이지별 텍스트
│   └── tables/            # 추출된 테이블 (JSON)
├── aia-proposal-male/
│   └── ...
└── aia-proposal-female/
    └── ...
```

---

## Phase 3: Carrier Parser 생성

### 3.1 관련 모듈

```
ingestion/parsers/
├── parser_factory.py              # 회사별 파서 라우팅
├── carrier_parsers/
│   ├── __init__.py               # 파서 export
│   ├── base_parser.py            # 추상 베이스 클래스
│   ├── samsung_parser.py         # 삼성 전용
│   ├── db_parser.py              # DB 전용
│   └── aia_parser.py             # ← 새로 생성
```

### 3.2 새 파서 생성

#### `ingestion/parsers/carrier_parsers/aia_parser.py`

```python
"""
AIA생명 전용 테이블 파서

AIA 가입설계서 테이블 구조:
| 순번 | 담보명 | 가입금액 | 보험료 | 보험기간/납입기간 |
|------|--------|----------|--------|-------------------|
| 1    | 암진단비 | 3천만원 | 15,000 | 20년/80세 |
"""

from typing import List, Dict, Optional
from .base_parser import BaseCarrierParser


class AIAParser(BaseCarrierParser):
    """AIA 테이블 파싱"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        AIA 담보 테이블 행 파싱

        컬럼 구조 (예시 - 실제 PDF 분석 후 조정 필요):
        [0]: 순번
        [1]: 담보명
        [2]: 가입금액
        [3]: 보험료
        [4]: 기간
        """
        if not cells or len(cells) < 4:
            return None

        # 빈 셀 필터링
        filtered = self.filter_empty_cells(cells)
        if len(filtered) < 3:
            return None

        # 첫 번째 셀이 순번인 경우 건너뛰기
        start_idx = 1 if self.is_row_number(filtered[0]) else 0

        coverage_name = filtered[start_idx] if len(filtered) > start_idx else ''

        # 유효한 담보명인지 검증
        if not self.is_valid_coverage_name(coverage_name):
            return None

        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'coverage_amount': filtered[start_idx + 1] if len(filtered) > start_idx + 1 else '',
            'premium': filtered[start_idx + 2] if len(filtered) > start_idx + 2 else '',
            'period': filtered[start_idx + 3] if len(filtered) > start_idx + 3 else '',
        }
```

### 3.3 파서 등록

#### `ingestion/parsers/carrier_parsers/__init__.py`

```python
from .aia_parser import AIAParser  # ← 추가

__all__ = [
    'SamsungParser', 'DBParser', 'LotteParser', 'MeritzParser',
    'KBParser', 'HanwhaParser', 'HyundaiParser', 'HeungkukParser',
    'AIAParser',  # ← 추가
]
```

#### `ingestion/parsers/parser_factory.py`

```python
from ingestion.parsers.carrier_parsers import (
    ...,
    AIAParser,  # ← 추가
)

class ParserFactory:
    PARSERS = {
        'samsung': SamsungParser,
        'db': DBParser,
        ...,
        'aia': AIAParser,  # ← 추가
    }
```

---

## Phase 4: Ontology 매핑 추가

### 4.1 관련 모듈

```
ontology/nl_mapping.py    # 자연어 → 엔티티 매핑
```

### 4.2 수정

#### `ontology/nl_mapping.py` (Line 39-79)

회사 별칭 추가:

```python
COMPANY_ALIASES = {
    # ... 기존 매핑 ...

    # AIA
    'AIA': 'AIA',
    'AIA생명': 'AIA',
    'AIA손보': 'AIA',
    '에이아이에이': 'AIA',
}
```

---

## Phase 5: 데이터 Ingestion

### 5.1 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 1: ingest_v3.py          JSON → document, document_clause         │
│  Step 2: coverage_pipeline.py  document_clause → coverage               │
│  Step 3: proposal_plan_extractor.py  → plan, plan_coverage              │
│  Step 4: risk_event_extractor.py     → risk_event                       │
│  Step 5: exclusion_extractor.py      → exclusion                        │
│  Step 6: condition_extractor.py      → condition                        │
│  Step 7: link_clauses.py             → clause_coverage (담보-조항 연결)  │
│  Step 8: graph_loader.py             PostgreSQL → Neo4j 동기화          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 실행 순서

```bash
# Step 1: 문서 메타데이터 JSON 생성 (convert_documents.py가 자동 생성)
# data/documents_metadata.json에 AIA 문서 추가됨

# Step 2: JSON → PostgreSQL (document, document_clause)
python -m ingestion.ingest_v3 data/documents_metadata.json --carrier aia

# Step 3: 담보 추출
python -m ingestion.coverage_pipeline --carrier aia
python scripts/update_coverage_metadata.py

# Step 4: Plan 추출 (가입설계서)
python -m ingestion.proposal_plan_extractor --carrier aia

# Step 5: 위험/면책/조건 추출
python -m ingestion.risk_event_extractor
python -m ingestion.exclusion_extractor
python -m ingestion.condition_extractor

# Step 6: 조항-담보 연결
python -m ingestion.link_clauses

# Step 7: Neo4j 동기화 (선택)
python -m ingestion.graph_loader
```

### 5.3 생성되는 데이터

| 테이블 | 내용 | 예상 건수 |
|--------|------|----------|
| `company` | AIA 회사 정보 | 1 |
| `product` | AIA 상품 | 1+ |
| `product_variant` | 성별/나이 변형 | 2-4 |
| `document` | PDF 문서 메타데이터 | 3-5 |
| `document_clause` | 조항 내용 | 5,000-20,000 |
| `coverage` | 담보 정보 | 30-100 |
| `plan` | 가입설계 플랜 | 2-4 |
| `plan_coverage` | 플랜별 담보 | 50-200 |

---

## Phase 6: 벡터 인덱스 구축

### 6.1 관련 모듈

```
vector_index/
├── build_index.py        # 인덱스 빌더
└── openai_embedder.py    # OpenAI 임베딩
```

### 6.2 실행

```bash
# 벡터 인덱스 재구축
python -m vector_index.build_index

# 특정 회사만 (지원되는 경우)
python -m vector_index.build_index --carrier aia
```

---

## Phase 7: 검증

### 7.1 CLI 테스트

```bash
# 검색 테스트
python -m api.cli "AIA 암진단비 보장금액은?"

# 디버그 모드
python -m api.cli --debug "AIA생명 약관에서 면책사항은?"
```

### 7.2 QA 평가

```bash
# AIA 관련 QA 추가 후 평가
python scripts/evaluate_qa.py \
    --qa-set data/gold_qa_set_50.json \
    --output evaluation/results/aia_evaluation.json
```

---

## 체크리스트

### 필수 수정 파일

| 파일 | 수정 내용 | 우선순위 |
|------|----------|----------|
| `scripts/convert_documents.py` | carrier_map에 회사 추가 | P0 |
| `ingestion/parsers/carrier_parsers/aia_parser.py` | 새 파서 생성 | P0 |
| `ingestion/parsers/carrier_parsers/__init__.py` | 파서 export | P0 |
| `ingestion/parsers/parser_factory.py` | PARSERS에 등록 | P0 |
| `ontology/nl_mapping.py` | COMPANY_ALIASES 추가 | P1 |

### 선택 수정 파일

| 파일 | 수정 내용 | 필요 조건 |
|------|----------|----------|
| `ingestion/parsers/form_parser.py` | KEY_PATTERNS 확장 | 특수 양식 테이블 |
| `data/gold_qa_set_50.json` | QA 테스트 케이스 추가 | 평가 필요 시 |

---

## 파이프라인 다이어그램

```
                          ┌─────────────────┐
                          │  PDF Documents  │
                          │  (examples/aia/)│
                          └────────┬────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  scripts/convert_documents.py │
                    │  + utils/pdf_converter.py    │
                    └──────────────┬──────────────┘
                                   │
                          ┌────────▼────────┐
                          │  JSON Files     │
                          │ (data/converted)│
                          └────────┬────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────────▼─────────┐
    │   ingest_v3.py    │ │ table_parser  │ │   text_parser     │
    │ (document/clause) │ │ + carrier_*   │ │ (terms articles)  │
    └─────────┬─────────┘ └───────┬───────┘ └─────────┬─────────┘
              │                   │                   │
              └─────────────┬─────┴─────┬─────────────┘
                            │           │
                   ┌────────▼───┐ ┌─────▼────────┐
                   │ PostgreSQL │ │  Neo4j (옵션) │
                   └────────┬───┘ └──────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
    ┌─────────▼───┐ ┌───────▼─────┐ ┌─────▼──────┐
    │coverage_    │ │proposal_plan│ │risk_event_ │
    │pipeline.py  │ │_extractor   │ │extractor   │
    └─────────────┘ └─────────────┘ └────────────┘
                            │
                   ┌────────▼────────┐
                   │ vector_index/   │
                   │ build_index.py  │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  hybrid_        │
                   │  retriever.py   │
                   │  + nl_mapping   │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │    api/cli.py   │
                   │    api/server   │
                   └─────────────────┘
```

---

## 문제 해결

### PDF 테이블 추출 오류

```bash
# 테이블 추출 결과 확인
cat data/converted_v2/aia/aia-proposal-male/tables/table_001_01.json

# 깨진 테이블 발견 시: broken_tables_report.json에 기록
```

### 파서 컬럼 매핑 오류

```python
# 디버깅: 실제 추출된 셀 확인
from ingestion.parsers.parser_factory import ParserFactory

parser = ParserFactory.get_parser('aia')
cells = ['1', '암진단비', '3천만원', '15,000', '20년/80세']
result = parser.parse_coverage_row(cells)
print(result)
```

### NL 매핑 확인

```python
from ontology.nl_mapping import NLMapper

mapper = NLMapper()
entities = mapper.extract_entities("AIA생명 암진단비")
print(entities)
# 예상: {"companies": ["AIA"], "coverages": ["암진단비"], ...}
```
