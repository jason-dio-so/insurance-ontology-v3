# PDF 문서 변환 Tasks (Phase 3)

**시작일**: 2025-12-14
**목표 완료일**: 2025-12-16
**현재 상태**: ✅ 구현 완료

---

## 상태 범례

| 상태 | 설명 |
|------|------|
| ⬜ PENDING | 아직 시작하지 않음 |
| 🔄 IN_PROGRESS | 진행 중 |
| ✅ COMPLETED | 완료됨 |
| ❌ FAILED | 실패 (원인 기록 필요) |
| ⏸️ BLOCKED | 다른 작업에 의해 차단됨 |

---

## 개요

이 문서는 v3-task.md의 **Phase 3: 문서 변환** 작업을 상세히 다룹니다.
원본 PDF 보험 문서를 pdfplumber를 사용하여 JSON 형식으로 변환하는 전체 과정을 정의합니다.

### 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     PDF 변환 파이프라인                           │
├─────────────────────────────────────────────────────────────────┤
│  1. PDF → JSON (범용)          2. 엔티티 추출 (회사별 패턴)        │
│  ┌──────────────────────┐     ┌──────────────────────────────┐  │
│  │ utils/pdf_converter.py│ →  │ proposal_plan_extractor.py   │  │
│  │ - pdfplumber 기반    │     │ risk_event_extractor.py      │  │
│  │ - 텍스트/테이블 추출  │     │ exclusion_extractor.py       │  │
│  │ - 범용 처리          │     │ condition_extractor.py       │  │
│  └──────────────────────┘     └──────────────────────────────┘  │
│           ↓                              ↓                       │
│  data/converted_v2/            PostgreSQL (plan, risk_event 등)  │
└─────────────────────────────────────────────────────────────────┘
```

### 목표

- 38개 보험 문서(약관, 가입설계서)를 구조화된 JSON으로 변환
- 테이블, 텍스트, 메타데이터 추출
- Phase 4 (데이터 수집)의 입력 데이터 생성

### 회사별 차이 처리

| 처리 단계 | 도구 | 회사별 차이 처리 방식 |
|----------|------|---------------------|
| PDF → JSON | `pdf_converter.py` | 범용 (pdfplumber) |
| Plan 추출 | `proposal_plan_extractor.py` | 패턴 매칭 (KB/Samsung: 공백, Hyundai: 연결) |
| RiskEvent 추출 | `risk_event_extractor.py` | 패턴 매칭 (ICD 코드, 정의 조항) |
| Exclusion 추출 | `exclusion_extractor.py` | 패턴 매칭 (면책 조항) |
| Condition 추출 | `condition_extractor.py` | 패턴 매칭 (대기기간 등) |

### 선행 조건

- Phase 0: 환경 준비 완료 (Python 3.11+, 가상환경)
- Phase 2: 스키마 생성 완료 (선택적, 문서 변환 자체는 독립 가능)

### 후행 작업

- Phase 4: 데이터 수집 (Ingestion)
- 엔티티 추출기 실행

---

## 전체 Task 의존성 다이어그램

```
3.1 원본 PDF 수집
    │
    ├──→ 3.3 문서 메타데이터 작성
    │         │
    │         └──→ 3.4 PDF → JSON 변환 ──→ 3.5 변환 결과 검증
    │                    ▲
3.2 docling 설치 ────────┘
```

---

## Task 목록

| ID | Task | 상태 | 선행 | 시작일 | 완료일 |
|----|------|------|------|--------|--------|
| 3.1 | 원본 PDF 수집 | ✅ COMPLETED | - | - | 기존 완료 |
| 3.2 | pdfplumber 기반 변환기 구현 | ✅ COMPLETED | Phase 0 완료 | 2025-12-14 | 2025-12-14 |
| 3.3 | 문서 메타데이터 작성 | ✅ COMPLETED | 3.1 | - | 기존 완료 |
| 3.4 | PDF → JSON 변환 실행 | ✅ COMPLETED | 3.2, 3.3 | - | 기존 완료 |
| 3.5 | 변환 결과 검증 | ✅ COMPLETED | 3.4 | 2025-12-14 | 2025-12-14 |

---

## Task 상세

### 3.1 원본 PDF 수집

| 항목 | 내용 |
|------|------|
| 설명 | 변환할 원본 PDF 문서를 `data/raw/` 디렉토리에 회사별로 정리하여 배치 |
| 디렉토리 구조 | `data/raw/{company_code}/{파일명}.pdf` |
| 완료 기준 | 38개 PDF 파일이 회사별 디렉토리에 배치됨 |

#### 디렉토리 구조 예시

```
data/raw/
├── samsung/
│   ├── 마이헬스파트너_약관.pdf
│   ├── 마이헬스파트너_가입설계서_남.pdf
│   └── 마이헬스파트너_가입설계서_여.pdf
├── hanwha/
│   ├── 무배당스마트건강보험_약관.pdf
│   └── 무배당스마트건강보험_가입설계서.pdf
├── kb/
│   └── ...
├── db/
│   └── ...
├── hyundai/
│   └── ...
├── meritz/
│   └── ...
├── nhnh/
│   └── ...
└── heungkuk/
    └── ...
```

#### 문서 분류

| 문서 유형 | 설명 | 예상 수량 |
|----------|------|----------|
| 약관 (terms) | 보험 상품 약관 전문 | ~16개 |
| 가입설계서 (proposal) | 보험료, 담보 구성 요약 | ~22개 |

---

### 3.2 pdfplumber 기반 변환기 구현 ✅

| 항목 | 내용 |
|------|------|
| 설명 | pdfplumber 기반 PDF 변환 모듈 (`utils/pdf_converter.py`) 구현 |
| 파일 | `utils/pdf_converter.py` |
| 완료 기준 | 테이블/텍스트 추출 검증 완료 |

#### 구현된 기능

| 기능 | 설명 |
|------|------|
| `PDFConverter` 클래스 | 범용 PDF 변환기 |
| `convert_document()` | 편의 함수 (스크립트에서 호출) |
| 텍스트 추출 | 페이지별 text, char_count, width, height |
| 테이블 추출 | 2D 배열, 셀 정규화 (개행→공백) |
| 섹션 감지 | 제n관, 제n조, 특별약관 패턴 |

#### 백엔드 지원

```python
# pdfplumber (기본, 설치됨)
converter = PDFConverter(backend="pdfplumber")

# docling (선택, 미설치)
converter = PDFConverter(backend="docling")

# 자동 선택
converter = PDFConverter(backend="auto")
```

#### 설치 명령어

```bash
# 필수 (이미 설치됨)
pip install pdfplumber

# 선택 (docling 사용 시)
pip install docling
```

---

### 3.3 문서 메타데이터 작성

| 항목 | 내용 |
|------|------|
| 설명 | 각 PDF 문서의 메타정보를 JSON 파일로 정의 |
| 파일 위치 | `data/documents_metadata.json` |
| 완료 기준 | 38개 문서 메타데이터 작성, JSON 문법 검증 통과 |

#### 메타데이터 스키마

```json
[
  {
    "document_id": "samsung_myhealth_terms",
    "company_code": "samsung",
    "company_name": "삼성생명",
    "product_code": "myhealth",
    "product_name": "마이헬스파트너",
    "doc_type": "terms",
    "doc_subtype": null,
    "version": "2024-01",
    "file_path": "data/raw/samsung/마이헬스파트너_약관.pdf"
  },
  {
    "document_id": "samsung_myhealth_proposal_male",
    "company_code": "samsung",
    "company_name": "삼성생명",
    "product_code": "myhealth",
    "product_name": "마이헬스파트너",
    "doc_type": "proposal",
    "doc_subtype": "male",
    "version": "2024-01",
    "file_path": "data/raw/samsung/마이헬스파트너_가입설계서_남.pdf"
  }
]
```

#### 메타데이터 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| document_id | string | Y | 고유 문서 식별자 (company_product_type_subtype) |
| company_code | string | Y | 회사 코드 (samsung, hanwha, kb 등) |
| company_name | string | Y | 회사 정식 명칭 |
| product_code | string | Y | 상품 코드 |
| product_name | string | Y | 상품 정식 명칭 |
| doc_type | string | Y | 문서 유형 (terms, proposal) |
| doc_subtype | string | N | 문서 하위 유형 (male, female, 40세 등) |
| version | string | Y | 문서 버전 (YYYY-MM 형식 권장) |
| file_path | string | Y | PDF 파일 상대 경로 |

#### 검증 명령어

```bash
# JSON 문법 검증
python -c "import json; json.load(open('data/documents_metadata.json'))"

# 파일 존재 여부 검증
python scripts/validate_metadata.py data/documents_metadata.json
```

---

### 3.4 PDF → JSON 변환 실행

| 항목 | 내용 |
|------|------|
| 설명 | docling을 사용하여 PDF를 구조화된 JSON으로 변환 |
| 명령어 | `python scripts/convert_documents.py --input data/raw --output data/converted` |
| 소요 시간 | 약 4-6시간 (38개 문서, 단일 스레드 기준) |
| 완료 기준 | 38개 문서 디렉토리 생성, 오류 없음 |

#### 변환 스크립트

```bash
# 전체 문서 변환
python scripts/convert_documents.py \
  --metadata data/documents_metadata.json \
  --output data/converted

# 특정 회사만 변환
python scripts/convert_documents.py \
  --metadata data/documents_metadata.json \
  --output data/converted \
  --company samsung

# 병렬 처리 (멀티 프로세스)
python scripts/convert_documents.py \
  --metadata data/documents_metadata.json \
  --output data/converted \
  --workers 4

# 오류 발생 문서 재시도
python scripts/convert_documents.py \
  --metadata data/documents_metadata.json \
  --output data/converted \
  --retry-failed
```

#### 출력 디렉토리 구조

```
data/converted/
├── samsung_myhealth_terms/
│   ├── metadata.json      # 문서 메타데이터
│   ├── text.json          # 추출된 텍스트 (섹션별)
│   ├── tables/            # 추출된 테이블
│   │   ├── table_001.json
│   │   ├── table_002.json
│   │   └── ...
│   └── pages/             # 페이지별 원본 텍스트
│       ├── page_001.txt
│       └── ...
├── samsung_myhealth_proposal_male/
│   └── ...
└── ...
```

#### text.json 스키마

```json
{
  "document_id": "samsung_myhealth_terms",
  "title": "마이헬스파트너 보험약관",
  "sections": [
    {
      "section_id": 1,
      "title": "제1관 총칙",
      "level": 1,
      "content": "...",
      "page_start": 3,
      "page_end": 5
    },
    {
      "section_id": 2,
      "title": "제1조(목적)",
      "level": 2,
      "parent_id": 1,
      "content": "이 보험계약(이하 \"계약\"이라 합니다)은...",
      "page_start": 3,
      "page_end": 3
    }
  ],
  "total_pages": 120,
  "extracted_at": "2025-12-14T10:30:00"
}
```

#### table JSON 스키마

```json
{
  "table_id": "table_001",
  "page": 15,
  "title": "보험금 지급사유 및 지급금액",
  "headers": ["담보명", "지급사유", "지급금액"],
  "rows": [
    ["암진단비", "암 진단 확정 시", "3,000만원"],
    ["뇌출혈진단비", "뇌출혈 진단 확정 시", "2,000만원"]
  ],
  "raw_text": "..."
}
```

---

### 3.5 변환 결과 검증

| 항목 | 내용 |
|------|------|
| 설명 | 변환된 JSON 파일의 품질 및 완전성 검증 |
| 명령어 | `python scripts/validate_conversion.py data/converted` |
| 완료 기준 | 모든 검증 항목 통과, 품질 리포트 생성 |

#### 검증 항목

| 검증 항목 | 기준 | 설명 |
|----------|------|------|
| 디렉토리 존재 | 38개 | 모든 문서에 대한 출력 디렉토리 |
| metadata.json | 필수 | 각 디렉토리에 메타데이터 파일 존재 |
| text.json | 필수 | 텍스트 추출 결과 존재 |
| 섹션 수 | ≥ 5 | 최소 섹션 수 (약관 기준) |
| 테이블 수 | ≥ 1 (proposal) | 가입설계서는 최소 1개 테이블 |
| 빈 텍스트 없음 | 필수 | content가 비어있는 섹션 없음 |

#### 검증 스크립트

```bash
# 전체 검증
python scripts/validate_conversion.py data/converted

# 상세 리포트 출력
python scripts/validate_conversion.py data/converted --verbose

# JSON 리포트 생성
python scripts/validate_conversion.py data/converted --output conversion_report.json
```

#### 검증 리포트 예시

```
=== 변환 결과 검증 ===

총 문서: 38
성공: 36
경고: 2
실패: 0

[경고] hanwha_smart_terms: 테이블 추출 0개 (예상: 1개 이상)
[경고] kb_lifeplus_proposal: 섹션 수 3개 (예상: 5개 이상)

품질 통계:
- 평균 섹션 수: 45.2
- 평균 테이블 수: 8.3
- 총 추출 텍스트: 2.5MB
```

---

## 변환 스크립트 템플릿

### scripts/convert_documents.py

```python
#!/usr/bin/env python3
"""PDF 문서를 JSON으로 변환하는 스크립트"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from docling.document_converter import DocumentConverter

def convert_document(pdf_path: Path, output_dir: Path, metadata: dict) -> dict:
    """단일 PDF 문서 변환"""
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))

    # 출력 디렉토리 생성
    doc_output = output_dir / metadata["document_id"]
    doc_output.mkdir(parents=True, exist_ok=True)

    # metadata.json 저장
    meta_out = {**metadata, "converted_at": datetime.now().isoformat()}
    (doc_output / "metadata.json").write_text(json.dumps(meta_out, ensure_ascii=False, indent=2))

    # text.json 저장
    text_data = extract_text_structure(result)
    (doc_output / "text.json").write_text(json.dumps(text_data, ensure_ascii=False, indent=2))

    # tables 저장
    tables_dir = doc_output / "tables"
    tables_dir.mkdir(exist_ok=True)
    for i, table in enumerate(extract_tables(result)):
        (tables_dir / f"table_{i+1:03d}.json").write_text(
            json.dumps(table, ensure_ascii=False, indent=2)
        )

    return {"status": "success", "document_id": metadata["document_id"]}

def main():
    parser = argparse.ArgumentParser(description="PDF to JSON 변환")
    parser.add_argument("--metadata", required=True, help="메타데이터 JSON 파일")
    parser.add_argument("--output", required=True, help="출력 디렉토리")
    parser.add_argument("--company", help="특정 회사만 변환")
    parser.add_argument("--workers", type=int, default=1, help="병렬 처리 워커 수")
    args = parser.parse_args()

    metadata_list = json.loads(Path(args.metadata).read_text())
    output_dir = Path(args.output)

    for meta in metadata_list:
        if args.company and meta["company_code"] != args.company:
            continue

        pdf_path = Path(meta["file_path"])
        print(f"변환 중: {meta['document_id']}")

        try:
            result = convert_document(pdf_path, output_dir, meta)
            print(f"  ✓ 완료")
        except Exception as e:
            print(f"  ✗ 실패: {e}")

if __name__ == "__main__":
    main()
```

---

## 트러블슈팅

| 문제 | 원인 | 해결 방법 |
|------|------|----------|
| `ModuleNotFoundError: docling` | docling 미설치 | `pip install docling` |
| 메모리 부족 (OOM) | 대용량 PDF | `--workers 1` 사용, 배치 크기 줄임 |
| 테이블 추출 실패 | 복잡한 테이블 레이아웃 | pdfplumber fallback 사용 |
| 한글 깨짐 | 인코딩 문제 | `ensure_ascii=False` 확인 |
| 변환 시간 초과 | 페이지 수 많음 | 문서 분할 또는 타임아웃 증가 |

### 대용량 문서 처리

```bash
# 메모리 제한 환경에서 순차 처리
python scripts/convert_documents.py \
  --metadata data/documents_metadata.json \
  --output data/converted \
  --workers 1 \
  --batch-size 1

# 특정 문서만 재처리
python scripts/convert_documents.py \
  --metadata data/documents_metadata.json \
  --output data/converted \
  --document-id samsung_myhealth_terms
```

---

## 진행 이력

| 날짜 | Task ID | 변경 내용 | 비고 |
|------|---------|----------|------|
| 2025-12-14 | - | pdf_ext.md 파일 생성 | v3-task.md Phase 3 상세화 |
| 2025-12-14 | 3.2 | utils/pdf_converter.py 구현 | pdfplumber 기반, docling 지원 |
| 2025-12-14 | 3.5 | 변환 결과 검증 완료 | 기존 data/converted와 호환성 확인 |

---

## 실패한 Task 기록

> 실패한 작업이 발생하면 아래 형식으로 기록합니다.

<!--
### [Task ID] Task 이름

**실패 일시**: YYYY-MM-DD HH:MM
**실패 원인**:
- 원인 1
- 원인 2

**시도한 해결 방법**:
1. 해결 시도 1 → 결과
2. 해결 시도 2 → 결과

**최종 해결 방법**:
- 해결 방법 설명

**교훈**:
- 향후 유사 문제 방지를 위한 교훈
-->

---

## 일정 요약

| Task | 작업 | 예상 소요 | 상태 |
|------|------|----------|------|
| 3.1 | 원본 PDF 수집 | 1시간 | ✅ 기존 완료 |
| 3.2 | pdf_converter.py 구현 | 2시간 | ✅ 완료 |
| 3.3 | 문서 메타데이터 작성 | 1-2시간 | ✅ 기존 완료 |
| 3.4 | PDF → JSON 변환 | 4-6시간 | ✅ 기존 완료 |
| 3.5 | 변환 결과 검증 | 1시간 | ✅ 완료 |
| **총계** | | **~10시간** | ✅ 완료 |

---

## 참고 문서

- [v3-task.md](./v3-task.md) - 전체 시스템 구축 가이드
- [task.md](./task.md) - DB 리팩토링 Task 관리
- [docling 공식 문서](https://github.com/DS4SD/docling) - PDF 변환 라이브러리

---

**문서 버전**: 1.0
**최종 수정**: 2025-12-14
**변경 이력**:
- v1.0 (2025-12-14): 초기 작성 (v3-task.md Phase 3 기반)
