# 데이터 파이프라인 실행 가이드

**생성일**: 2025-12-14
**목적**: PDF 문서에서 PostgreSQL 테이블까지 전체 데이터 생성 절차

---

## 전체 실행 순서 요약

```
Step 1: PDF → JSON 변환
Step 2: JSON → 기본 테이블 (document, document_clause)
Step 3: coverage 테이블 생성
Step 4: coverage 메타데이터 설정
Step 5: plan, plan_coverage 생성
Step 6: risk_event 생성
Step 7: clause_coverage 연결 (proposal + terms)
Step 8: exclusion, condition 생성
Step 9: Neo4j 동기화 (선택)
Step 10: 벡터 임베딩 생성 (선택)
```

---

## Step 1: PDF → JSON 변환

**목적**: PDF 문서를 구조화된 JSON으로 변환

```bash
python scripts/convert_documents.py \
    --examples-dir examples/examples \
    --output-dir data/converted_v2
```

**입력**: `examples/examples/*/` (회사별 PDF 파일)
**출력**: `data/converted_v2/*/` (JSON 파일)

**생성 파일 구조**:
```
data/converted_v2/
├── 삼성/
│   ├── samsung-terms/
│   │   ├── metadata.json
│   │   ├── sections.json
│   │   ├── tables/
│   │   └── text.json
│   └── samsung-proposal/
└── ...
```

---

## Step 2: JSON → 기본 테이블

**목적**: JSON 파일을 PostgreSQL에 적재

```bash
python -m ingestion.ingest_v3 data/documents_metadata.json
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| company | 보험사 | 8 |
| product | 상품 | 8 |
| product_variant | 상품 변형 | 4 |
| document | 문서 메타데이터 | 38 |
| document_clause | 조항 내용 | ~80,000 |

---

## Step 3: coverage 테이블 생성

**목적**: document_clause에서 담보 정보 추출

```bash
python -m ingestion.coverage_pipeline
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| coverage | 담보/특약 | 294 |

**추출 항목**:
- coverage_name (담보명)
- coverage_period (보험기간)
- coverage_category (자동 분류)
- renewal_type (갱신형/비갱신형)

---

## Step 4: coverage 메타데이터 설정

**목적**: coverage에 그룹, 표준코드, 부모-자식 관계 설정

```bash
python scripts/update_coverage_metadata.py
```

**업데이트 항목**:
| 컬럼 | 설명 | 채워지는 비율 |
|------|------|-------------|
| group_id | 카테고리 그룹 연결 | 100% |
| standard_code | 신정원 표준코드 | 67% |
| parent_coverage_id | 부모-자식 관계 | 13% |

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| coverage_group | 담보 그룹 | 110 |

---

## Step 5: plan, plan_coverage 생성

**목적**: 가입설계서에서 Plan 정보 추출

```bash
python -m ingestion.proposal_plan_extractor
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| plan | 가입설계 플랜 | 10 |
| plan_coverage | 플랜-담보 연결 | 571 |

**추출 항목**:
- target_gender (성별)
- target_age (나이)
- insurance_period (보험기간)
- payment_period (납입기간)
- sum_insured, premium (가입금액, 보험료)

---

## Step 6: risk_event 생성

**목적**: 약관에서 위험 이벤트 정의 추출

```bash
python -m ingestion.risk_event_extractor
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| risk_event | 위험 이벤트 | 572 |

**추출 유형**:
- cancer (암)
- cerebrovascular (뇌혈관)
- cardiovascular (심장)
- hospitalization (입원)
- treatment (치료)

---

## Step 7: clause_coverage 연결

**목적**: document_clause와 coverage 연결

### 7-1. proposal/product_summary 연결

```bash
python -m ingestion.link_clauses
```

### 7-2. terms 문서 연결 (SQL 직접 실행)

```bash
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
INSERT INTO clause_coverage (clause_id, coverage_id, extraction_method, relevance_score)
SELECT DISTINCT
    dc.id as clause_id,
    c.id as coverage_id,
    'terms_title_match' as extraction_method,
    0.8 as relevance_score
FROM document_clause dc
JOIN document d ON dc.document_id = d.id
JOIN product p ON d.product_id = p.id
JOIN coverage c ON c.product_id = p.id
WHERE d.doc_type = 'terms'
  AND (
      dc.clause_title LIKE '%지급하지 않%'
      OR dc.clause_title LIKE '%면책%'
      OR dc.clause_title LIKE '%보장개시%'
      OR dc.clause_title LIKE '%보장 개시%'
  )
  AND dc.clause_title LIKE '%' || SUBSTRING(c.coverage_name, 1, 4) || '%'
ON CONFLICT (clause_id, coverage_id) DO NOTHING;
"
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| clause_coverage | 조항-담보 연결 | 623 |

---

## Step 8: exclusion, condition 생성

**목적**: 면책 조항과 보장 조건 추출

### 8-1. 면책조항 clause_coverage 연결

```bash
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
INSERT INTO clause_coverage (clause_id, coverage_id, extraction_method, relevance_score)
SELECT DISTINCT dc.id, c.id, 'exclusion_product_match', 0.7
FROM document_clause dc
JOIN document d ON dc.document_id = d.id
JOIN coverage c ON c.product_id = d.product_id
WHERE d.doc_type = 'terms'
  AND (dc.clause_title LIKE '%지급하지 않%' OR dc.clause_title LIKE '%면책%')
ON CONFLICT (clause_id, coverage_id) DO NOTHING;
"
```

### 8-2. exclusion 추출

```bash
python -m ingestion.exclusion_extractor
```

또는 직접 SQL:

```bash
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
WITH exclusion_clauses AS (
    SELECT DISTINCT dc.id as clause_id, dc.clause_text, d.product_id,
           c.id as coverage_id, c.coverage_name,
           ROW_NUMBER() OVER (PARTITION BY d.product_id, LEFT(dc.clause_text, 200) ORDER BY dc.id) as rn
    FROM document_clause dc
    JOIN document d ON dc.document_id = d.id
    JOIN coverage c ON c.product_id = d.product_id
    WHERE d.doc_type = 'terms'
      AND (dc.clause_title LIKE '%지급하지 않%' OR dc.clause_title LIKE '%면책%')
      AND dc.clause_text IS NOT NULL AND LENGTH(dc.clause_text) > 50
)
INSERT INTO exclusion (coverage_id, exclusion_type, exclusion_text, is_absolute, attributes)
SELECT coverage_id, 'general', LEFT(clause_text, 2000), TRUE,
       jsonb_build_object('source_clause_id', clause_id, 'coverage_name', coverage_name)
FROM exclusion_clauses WHERE rn = 1;
"
```

### 8-3. condition 추출

```bash
python -m ingestion.condition_extractor
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| exclusion | 면책 조항 | ~500 |
| condition | 보장 조건 | 196 |

**주의**: Step 7 완료 후 실행해야 함 (clause_coverage 의존)

---

## Step 8.5: benefit 생성

**목적**: 담보별 급부(지급금액) 정보 추출

```bash
python -m ingestion.extract_benefits
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| benefit | 급부 정보 | 286 |

**추출 유형**:
| benefit_type | 건수 | 설명 |
|--------------|------|------|
| diagnosis | 110 | 진단비 |
| other | 63 | 기타 |
| treatment | 42 | 치료비 |
| surgery | 41 | 수술비 |
| hospitalization | 21 | 입원비 |
| death | 9 | 사망 |

**주의**: Step 7 완료 후 실행해야 함 (clause_coverage 의존)

---

## Step 8.6: benefit_risk_event 연결

**목적**: benefit과 risk_event 간 의미론적 연결

```bash
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
INSERT INTO benefit_risk_event (benefit_id, risk_event_id)
SELECT DISTINCT b.id, re.id
FROM benefit b
CROSS JOIN risk_event re
WHERE
  (b.benefit_name LIKE '%암%' AND re.event_type = 'cancer' AND re.event_name LIKE '%암%')
  OR (b.benefit_name LIKE '%뇌%' AND re.event_type = 'cerebrovascular')
  OR ((b.benefit_name LIKE '%심장%' OR b.benefit_name LIKE '%심근%') AND re.event_type = 'cardiovascular')
  OR (b.benefit_type = 'hospitalization' AND re.event_type = 'hospitalization')
  OR (b.benefit_type = 'treatment' AND re.event_type = 'treatment'
      AND (b.benefit_name LIKE '%항암%' AND re.event_name LIKE '%암%'))
ON CONFLICT (benefit_id, risk_event_id) DO NOTHING;
"
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| benefit_risk_event | 급부-위험 연결 | ~25,000 |

**주의**: Step 6 (risk_event), Step 8.5 (benefit) 완료 후 실행

---

## Step 9: Neo4j 동기화 (선택)

**목적**: PostgreSQL 데이터를 Neo4j 그래프 DB로 동기화

```bash
python -m ingestion.graph_loader
```

---

## Step 10: 벡터 임베딩 생성 (선택)

**목적**: document_clause 텍스트를 벡터로 변환하여 의미 검색 지원

```bash
# fastembed 사용 (무료, 로컬, 384차원)
python vector_index/build_index.py --backend fastembed

# OpenAI 사용 (유료, 1536차원)
python vector_index/build_index.py --backend openai
```

**생성 테이블**:
| 테이블 | 설명 | 예상 행 수 |
|--------|------|-----------|
| clause_embedding | 조항 벡터 임베딩 | ~59,383 |

**옵션**:
| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| --backend | fastembed | 임베딩 모델 (fastembed, bge, jina, openai) |
| --batch-size | 100 | 배치 크기 |
| --min-length | 50 | 최소 텍스트 길이 (노이즈 필터링) |
| --limit | 전체 | 테스트용 제한 |

**필요 환경변수**:
```bash
# .env 파일
POSTGRES_URL=postgresql://postgres:postgres@localhost:15432/insurance_ontology_test

# OpenAI 사용 시
OPENAI_API_KEY=sk-...
```

**주의**:
- 59,383건 처리에 fastembed 기준 약 1-2시간 소요
- OpenAI 사용 시 약 $1-2 비용 발생
- 50자 미만 조항은 노이즈로 간주하여 기본 제외

---

## 전체 실행 스크립트

```bash
#!/bin/bash
# 전체 파이프라인 실행 스크립트

set -e  # 오류 시 중단

echo "=== Step 1: PDF → JSON ==="
python scripts/convert_documents.py --examples-dir examples/examples --output-dir data/converted_v2

echo "=== Step 2: JSON → 기본 테이블 ==="
python -m ingestion.ingest_v3 data/documents_metadata.json

echo "=== Step 3: coverage 생성 ==="
python -m ingestion.coverage_pipeline

echo "=== Step 4: coverage 메타데이터 ==="
python scripts/update_coverage_metadata.py

echo "=== Step 5: plan, plan_coverage 생성 ==="
python -m ingestion.proposal_plan_extractor

echo "=== Step 6: risk_event 생성 ==="
python -m ingestion.risk_event_extractor

echo "=== Step 7-1: clause_coverage (proposal) ==="
python -m ingestion.link_clauses

echo "=== Step 7-2: clause_coverage (terms) ==="
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
INSERT INTO clause_coverage (clause_id, coverage_id, extraction_method, relevance_score)
SELECT DISTINCT dc.id, c.id, 'terms_title_match', 0.8
FROM document_clause dc
JOIN document d ON dc.document_id = d.id
JOIN product p ON d.product_id = p.id
JOIN coverage c ON c.product_id = p.id
WHERE d.doc_type = 'terms'
  AND (dc.clause_title LIKE '%지급하지 않%' OR dc.clause_title LIKE '%면책%' OR dc.clause_title LIKE '%보장개시%')
  AND dc.clause_title LIKE '%' || SUBSTRING(c.coverage_name, 1, 4) || '%'
ON CONFLICT (clause_id, coverage_id) DO NOTHING;
"

echo "=== Step 8: exclusion, condition 생성 ==="
python -m ingestion.exclusion_extractor
python -m ingestion.condition_extractor

echo "=== Step 8.5: benefit 생성 ==="
python -m ingestion.extract_benefits

echo "=== Step 8.6: benefit_risk_event 연결 ==="
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
INSERT INTO benefit_risk_event (benefit_id, risk_event_id)
SELECT DISTINCT b.id, re.id FROM benefit b CROSS JOIN risk_event re
WHERE (b.benefit_name LIKE '%암%' AND re.event_type = 'cancer' AND re.event_name LIKE '%암%')
  OR (b.benefit_name LIKE '%뇌%' AND re.event_type = 'cerebrovascular')
  OR ((b.benefit_name LIKE '%심장%' OR b.benefit_name LIKE '%심근%') AND re.event_type = 'cardiovascular')
  OR (b.benefit_type = 'hospitalization' AND re.event_type = 'hospitalization')
ON CONFLICT (benefit_id, risk_event_id) DO NOTHING;
"

echo "=== Step 9: Neo4j 동기화 ==="
python -m ingestion.graph_loader

echo "=== Step 10: 벡터 임베딩 생성 ==="
python vector_index/build_index.py --backend fastembed --min-length 50

echo "=== 완료! ==="
```

---

## 최종 테이블 상태 확인

```bash
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "
SELECT 'company' as tbl, COUNT(*) FROM company
UNION ALL SELECT 'product', COUNT(*) FROM product
UNION ALL SELECT 'product_variant', COUNT(*) FROM product_variant
UNION ALL SELECT 'document', COUNT(*) FROM document
UNION ALL SELECT 'document_clause', COUNT(*) FROM document_clause
UNION ALL SELECT 'coverage', COUNT(*) FROM coverage
UNION ALL SELECT 'coverage_group', COUNT(*) FROM coverage_group
UNION ALL SELECT 'plan', COUNT(*) FROM plan
UNION ALL SELECT 'plan_coverage', COUNT(*) FROM plan_coverage
UNION ALL SELECT 'risk_event', COUNT(*) FROM risk_event
UNION ALL SELECT 'exclusion', COUNT(*) FROM exclusion
UNION ALL SELECT 'condition', COUNT(*) FROM condition
UNION ALL SELECT 'clause_coverage', COUNT(*) FROM clause_coverage
UNION ALL SELECT 'benefit', COUNT(*) FROM benefit
UNION ALL SELECT 'benefit_risk_event', COUNT(*) FROM benefit_risk_event
UNION ALL SELECT 'clause_embedding', COUNT(*) FROM clause_embedding
ORDER BY tbl;
"
```

**예상 결과**:
```
        tbl          |  cnt
---------------------+-------
 benefit             |   286
 benefit_risk_event  | 24968
 clause_coverage     | 89907
 clause_embedding    | 59383
 company             |     8
 condition           |   196
 coverage            |   294
 coverage_group      |   110
 document            |    38
 document_clause     | 80602
 exclusion           |   500
 plan                |    10
 plan_coverage       |   571
 product             |     8
 product_variant     |     4
 risk_event          |   572
```

---

## 문제 해결

### plan_coverage가 0인 경우
```bash
# plan 삭제 후 재생성
docker exec insurance_postgres_test psql -U postgres -d insurance_ontology_test -c "DELETE FROM plan;"
python -m ingestion.proposal_plan_extractor
```

### exclusion/condition이 0인 경우
Step 7 (clause_coverage 연결)이 완료되었는지 확인 후 재실행

### coverage_group이 비어있는 경우
```bash
python scripts/update_coverage_metadata.py
```
