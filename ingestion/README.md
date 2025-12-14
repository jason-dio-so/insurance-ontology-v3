# Ingestion 파이프라인 가이드

## 실행 순서

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. ingest_v3.py          JSON → document, document_clause          │
│  2. coverage_pipeline.py  document_clause → coverage                │
│  3. proposal_plan_extractor.py  → plan, plan_coverage               │
│  4. risk_event_extractor.py     → risk_event                        │
│  5. exclusion_extractor.py      → exclusion                         │
│  6. condition_extractor.py      → condition                         │
│  7. link_clauses.py             → clause_coverage (담보-조항 연결)     │
│  8. graph_loader.py             PostgreSQL → Neo4j 동기화            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. ingest_v3.py (메인 Ingestion)

**역할**: JSON 파일 → PostgreSQL (document, document_clause)

**입력**: `data/converted_v2/*/` (PDF에서 변환된 JSON)
**출력**: `document` (~38개), `document_clause` (~80,000개)

```bash
# 전체 ingestion
python -m ingestion.ingest_v3 data/documents_metadata.json

# 특정 회사만
python -m ingestion.ingest_v3 data/documents_metadata.json --carrier samsung
```

**생성 테이블**:
- `company` - 보험사 정보
- `product` - 상품 정보
- `product_variant` - 상품 변형 (성별, 나이대)
- `document` - 문서 메타데이터
- `document_clause` - 조항 내용 (article, table_row 등)

---

## 2. coverage_pipeline.py (담보 추출)

**역할**: document_clause → coverage 테이블

**입력**: `document_clause.structured_data.coverage_name`
**출력**: `coverage` (294개)

```bash
python -m ingestion.coverage_pipeline
python -m ingestion.coverage_pipeline --carrier samsung
```

**추출 항목**:
| 컬럼 | 소스 |
|------|------|
| coverage_name | structured_data.coverage_name |
| coverage_period | structured_data.period |
| coverage_category | 자동 추론 (암진단, 수술 등) |
| renewal_type | 갱신형/비갱신형 파싱 |

**후속 작업**:
```bash
# group_id, standard_code, parent_coverage_id 설정
python scripts/update_coverage_metadata.py
```

---

## 3. proposal_plan_extractor.py (가입설계서 → Plan)

**역할**: proposal 문서 → plan, plan_coverage 테이블

**입력**: proposal 문서의 테이블 데이터
**출력**: `plan` (10개), `plan_coverage` (571개)

```bash
python -m ingestion.proposal_plan_extractor
python -m ingestion.proposal_plan_extractor --carrier samsung
```

**추출 항목**:
- Plan: 성별, 나이, 보험기간, 납입기간, 총보험료
- plan_coverage: 담보별 가입금액, 보험료

---

## 4. risk_event_extractor.py (위험 이벤트 추출)

**역할**: 약관에서 위험 이벤트 정의 추출

**입력**: terms 문서의 "정의" 조항
**출력**: `risk_event` (572개)

```bash
python -m ingestion.risk_event_extractor
```

**추출 항목**:
| event_type | 예시 |
|------------|------|
| cancer | 암, 유사암, 고액암 |
| cerebrovascular | 뇌졸중, 뇌출혈 |
| cardiovascular | 급성심근경색, 허혈성심장질환 |
| hospitalization | 입원 |
| treatment | 수술, 치료 |

---

## 5. exclusion_extractor.py (면책 조항 추출)

**역할**: 약관에서 면책 사유 추출

**입력**: "보험금을 지급하지 않는 사유" 조항
**출력**: `exclusion` (28개)

```bash
python -m ingestion.exclusion_extractor
```

**추출 항목**:
- exclusion_type: general, conditional, absolute
- coverage_id: 해당 담보와 연결

---

## 6. condition_extractor.py (보장조건 추출)

**역할**: 약관에서 보장조건 추출

**입력**: "보장개시", "면책기간" 조항
**출력**: `condition` (42개)

```bash
python -m ingestion.condition_extractor
```

**추출 항목**:
- condition_type: waiting_period, general
- waiting_period_days: 90일 등
- coverage_id: 해당 담보와 연결

---

## 7. link_clauses.py (조항-담보 연결)

**역할**: document_clause와 coverage 연결

**입력**: document_clause, coverage
**출력**: `clause_coverage` (연결 테이블)

```bash
python -m ingestion.link_clauses
```

**매칭 방식**:
1. Exact Match: coverage_name 정확히 일치
2. Fuzzy Match: 유사도 기반 매칭

---

## 8. graph_loader.py (Neo4j 동기화)

**역할**: PostgreSQL → Neo4j 그래프 DB 동기화

```bash
python -m ingestion.graph_loader
python -m ingestion.graph_loader --entity coverage  # 특정 엔티티만
```

**동기화 엔티티**:
- Company, Product, ProductVariant
- Coverage, Plan, RiskEvent
- Exclusion, Condition

---

## 기타 스크립트

### load_disease_codes.py
ICD/KCD 질병코드 추출 및 로드

```bash
python -m ingestion.load_disease_codes
```

### extract_benefits.py
급부(benefit) 정보 추출 (현재 미사용)

---

## 전체 실행 순서 (처음부터)

```bash
# 1. PDF → JSON 변환
python scripts/convert_documents.py

# 2. JSON → PostgreSQL
python -m ingestion.ingest_v3 data/documents_metadata.json

# 3. 담보 추출
python -m ingestion.coverage_pipeline
python scripts/update_coverage_metadata.py

# 4. Plan 추출
python -m ingestion.proposal_plan_extractor

# 5. 위험/면책/조건 추출
python -m ingestion.risk_event_extractor
python -m ingestion.exclusion_extractor
python -m ingestion.condition_extractor

# 6. 조항-담보 연결
python -m ingestion.link_clauses

# 7. Neo4j 동기화
python -m ingestion.graph_loader
```

---

## 데이터 현황

| 테이블 | 건수 | 소스 |
|--------|------|------|
| document | 38 | ingest_v3.py |
| document_clause | ~80,000 | ingest_v3.py |
| coverage | 294 | coverage_pipeline.py |
| plan | 10 | proposal_plan_extractor.py |
| plan_coverage | 571 | proposal_plan_extractor.py |
| risk_event | 572 | risk_event_extractor.py |
| exclusion | 28 | exclusion_extractor.py |
| condition | 42 | condition_extractor.py |
