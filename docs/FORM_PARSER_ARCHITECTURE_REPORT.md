# FormParser 아키텍처 분석 보고서

## 1. 현황 분석

### 1.1 현재 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase 0: PDF 변환                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ pdf_converter.py (pdfplumber)                                           │ │
│ │   PDF → tables/*.json, text.json                                        │ │
│ │   ⚠️ DB 가입조건 테이블: 좌/우 병합으로 데이터 손상                        │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Ingestion (ingest_v3.py)                                           │
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                       │
│ │  TextParser   │ │  TableParser  │ │ HybridParser  │                       │
│ │  (terms)      │ │  (proposal)   │ │ (business_spec│                       │
│ │               │ │               │ │  product_sum) │                       │
│ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘                       │
│         │                 │                 │                               │
│         └────────────┬────┴────────────────┘                               │
│                      ↓                                                      │
│              document_clause                                                │
│              (article, table_row, text_block)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase 2: 후처리                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ proposal_plan_extractor.py                                              │ │
│ │   ├── FormParser (가입조건 테이블 → plan 메타데이터)                     │ │
│ │   └── JSON tables 재로드 (data/converted_v2 직접 접근)                  │ │
│ │                                                                         │ │
│ │   Output: plan, plan_coverage 테이블                                    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 테이블 파서 비교

| 파서 | 대상 | 감지 기준 | 추출 데이터 | 사용 위치 |
|------|------|----------|-------------|----------|
| **TableParser** | 담보 테이블 | 키워드 2+ (담보, 보장, 가입금액...) | coverage_name, amount, premium | ingest_v3.py |
| **FormParser** | 양식 테이블 | 빈 셀 60%+, 컬럼 5+, 행 5+ | key-value pairs (피보험자, 만기...) | proposal_plan_extractor.py |
| **HybridParser** | 섹션+테이블 | 문서 구조 기반 | section chunks + table rows | ingest_v3.py |

### 1.3 proposal 문서의 테이블 유형

```
proposal 문서 (가입설계서)
├── 가입조건 테이블 (Form Table) ← FormParser
│   ├── 피보험자: 홍길동 (850407-1******)
│   ├── 상해급수: 1급
│   ├── 만기/납기: 100세만기 / 20년납
│   └── 보장보험료: 162,843원
│
└── 담보 테이블 (Benefit Table) ← TableParser + CarrierParser
    ├── 암진단비: 3,000만원 / 15,000원
    ├── 뇌졸중진단비: 2,000만원 / 8,500원
    └── ...
```

---

## 2. 문제점 분석

### 2.1 데이터 흐름 비효율

```
현재:
  JSON tables → ingest_v3 (TableParser) → document_clause
                                              ↓
  JSON tables → proposal_plan_extractor (FormParser) → plan  ← 중복 로드!

문제:
  1. 동일한 JSON 파일을 2번 로드
  2. Form 테이블이 document_clause에 table_row로 저장됨 (잘못된 유형)
  3. 나중에 다시 원본 JSON에서 FormParser로 재파싱
```

### 2.2 broken_tables와의 관계

```json
// broken_tables_report.json
{
  "broken_tables": {
    "files": [
      {
        "document": "db-proposal-*",
        "table_file": "table_007_01.json",  // 가입조건 테이블
        "issue": "좌/우 병합으로 인한 텍스트 순서 오류",
        "sample": "피 보가 입험담 자보[만기/납"  // 깨진 데이터
      }
    ]
  }
}
```

**핵심 인사이트:**
- broken_tables 3건 = 모두 **Form Table (가입조건)**
- pdf_converter.py 단계에서 이미 손상됨
- FormParser가 어디서 실행되든 손상된 데이터는 복구 불가

### 2.3 현재 FormParser의 한계

| 항목 | 현재 상태 | 문제점 |
|------|----------|--------|
| 호출 위치 | proposal_plan_extractor.py | ingest_v3.py와 분리 |
| 데이터 소스 | data/converted_v2 JSON 직접 로드 | document_clause 활용 안 함 |
| chunk_type | 없음 (plan 테이블만 생성) | form_field 타입 미존재 |
| 깨진 데이터 | 처리 불가 | pdf_converter.py 문제 |

---

## 3. 아키텍처 옵션 비교

### Option A: 현재 유지 (proposal_plan_extractor.py에서 호출)

```
장점:
  - 기존 코드 변경 없음
  - plan 추출 로직이 한 곳에 집중

단점:
  - JSON 중복 로드
  - Form 테이블이 table_row로 잘못 저장
  - 파이프라인 일관성 저하
```

### Option B: ingest_v3.py에서 호출

```
변경:
  ingest_v3.py
  ├── terms → TextParser
  ├── proposal → TableParser + FormParser  ← 통합
  └── business_spec → HybridParser

장점:
  - 1회 파싱으로 효율적
  - 새로운 chunk_type: 'form_field' 추가 가능
  - 파이프라인 일관성

단점:
  - ingest_v3.py 복잡도 증가
  - proposal_plan_extractor.py 로직 이동 필요
  - form_field → plan 변환 로직 필요
```

### Option C: pdf_converter.py에서 호출 (가장 빠른 단계)

```
변경:
  pdf_converter.py
  └── extract_tables()
      ├── is_form_table() → form_data.json 별도 저장
      └── 일반 테이블 → table_*.json

장점:
  - 가장 이른 단계에서 분류
  - 테이블 유형별 최적화 가능

단점:
  - pdf_converter.py 의존성 증가 (psycopg2 불필요한데 추가?)
  - 변환 단계에서 비즈니스 로직 처리 (관심사 분리 위반)
  - 깨진 테이블 문제는 여전히 해결 안 됨
```

### Option D: 깨진 테이블 문제 선 해결 후 결정

```
변경 순서:
  1. pdf_converter.py에서 좌/우 테이블 분리 추출 로직 추가
  2. Form 테이블 정상 추출 확인
  3. 그 후 FormParser 호출 위치 결정

장점:
  - 근본 원인 해결
  - 정상 데이터로 아키텍처 결정 가능

단점:
  - 추가 개발 필요 (페이지 크롭 로직)
  - DB 가입설계서 전용 처리
```

---

## 4. 정량적 분석

### 4.1 Form 테이블 분포

```
문서 타입별 Form Table 비율:
┌────────────────┬──────────┬──────────┬────────┐
│ 문서타입        │ 전체     │ Form     │ 비율   │
├────────────────┼──────────┼──────────┼────────┤
│ terms          │ 15,425   │ 6        │ 0.04%  │
│ proposal       │ 538      │ 15       │ 2.79%  │
│ business_spec  │ 3,203    │ 0        │ 0.00%  │
│ product_summary│ 1,885    │ 5        │ 0.27%  │
│ easy_summary   │ 42       │ 0        │ 0.00%  │
└────────────────┴──────────┴──────────┴────────┘

결론: Form 테이블은 proposal에 집중 (2.79%)
```

### 4.2 영향 범위

| 옵션 | 수정 파일 수 | 복잡도 | 깨진 데이터 해결 |
|------|-------------|--------|-----------------|
| A (유지) | 0 | 낮음 | ❌ |
| B (ingest_v3) | 3-4 | 중간 | ❌ |
| C (pdf_converter) | 2-3 | 중간 | ❌ |
| D (크롭 선행) | 1-2 + 후속작업 | 높음 | ✅ |

---

## 5. 권장 사항

### 5.1 단기 (현재)

**Option A 유지** - 현재 구조 유지

이유:
1. Form 테이블 비율이 낮음 (proposal의 2.79%)
2. 깨진 데이터 문제가 미해결 상태
3. 아키텍처 변경 ROI가 낮음

### 5.2 중기 (깨진 테이블 해결 시)

**Option D → Option B**

1. pdf_converter.py에 DB 가입설계서 7페이지 전용 크롭 로직 추가
2. Form 테이블 정상 추출 확인
3. ingest_v3.py에 FormParser 통합
4. 새로운 chunk_type: `form_field` 추가

```python
# ingest_v3.py 변경안
PARSER_MAPPING = {
    'terms': 'text',
    'proposal': 'table+form',  # TableParser + FormParser
    'business_spec': 'hybrid',
    'product_summary': 'hybrid',
    'easy_summary': 'hybrid',
}
```

### 5.3 장기 (이상적 구조)

```
pdf_converter.py
    ├── 일반 테이블 → tables/*.json
    └── 양식 테이블 감지 → form_detected: true 플래그

ingest_v3.py
    ├── TextParser (terms)
    ├── TableParser (proposal - 담보)
    ├── FormParser (proposal - 가입조건)  ← form_detected 기반
    └── HybridParser (business_spec, product_summary)

document_clause
    ├── clause_type: 'article' (약관 조항)
    ├── clause_type: 'table_row' (담보 테이블)
    ├── clause_type: 'form_field' (양식 필드)  ← 신규
    └── clause_type: 'text_block' (일반 텍스트)

proposal_plan_extractor.py
    └── document_clause (form_field) → plan 테이블
        (JSON 직접 로드 불필요)
```

---

## 6. 결론

### 핵심 발견

1. **FormParser 호출 위치보다 데이터 품질이 우선**
   - DB 가입조건 테이블이 pdf_converter.py에서 이미 깨짐
   - FormParser가 어디서 실행되든 깨진 데이터는 복구 불가

2. **Form 테이블 영향 범위는 제한적**
   - 전체 21,093개 테이블 중 26개 (0.12%)
   - proposal에 집중 (15개, 2.79%)

3. **아키텍처 변경 시점**
   - 깨진 테이블 문제 해결 후 진행 권장
   - 현재는 proposal_plan_extractor.py에서 호출 유지

### 액션 아이템

| 우선순위 | 작업 | 효과 |
|---------|------|------|
| P0 | pdf_converter.py 크롭 로직 (DB 7페이지) | 깨진 데이터 해결 |
| P1 | ingest_v3.py에 FormParser 통합 | 중복 로드 제거 |
| P2 | chunk_type: form_field 추가 | 데이터 모델 일관성 |
| P3 | proposal_plan_extractor.py 리팩토링 | document_clause 활용 |

---

## 부록: 관련 파일 목록

| 파일 | 역할 | FormParser 관련성 |
|------|------|-------------------|
| `utils/pdf_converter.py` | PDF → JSON | 깨진 테이블 원인 |
| `ingestion/ingest_v3.py` | JSON → document_clause | 통합 후보 위치 |
| `ingestion/parsers/form_parser.py` | Form 테이블 파싱 | 핵심 모듈 |
| `ingestion/parsers/table_parser.py` | 담보 테이블 파싱 | 병행 사용 |
| `ingestion/proposal_plan_extractor.py` | plan 추출 | 현재 호출 위치 |
| `data/converted_v2/broken_tables_report.json` | 깨진 테이블 목록 | 데이터 품질 이슈 |
