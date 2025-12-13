# 보험 온톨로지 AI 시스템 개발 보고서

**작성일**: 2025-12-12
**프로젝트**: Insurance Ontology AI System
**개발 기간**: 2025-12-10 ~ 2025-12-11

---

## 1. 프로젝트 개요

### 1.1 목표
보험 약관 PDF 문서에서 정보를 자동 추출하고, 자연어 질의에 **90% 정확도**로 응답하는 RAG(Retrieval-Augmented Generation) 시스템 구축

### 1.2 최종 성과
- **전체 정확도**: 86% (43/50 queries)
- **처리 문서**: 38개 보험 약관 (8개 보험사)
- **추출 조항**: 80,682개 clauses
- **벡터 임베딩**: 80,682개 (1536차원)

---

## 2. 사용 기술 스택

| 구분 | 기술/도구 | 버전 | 용도 |
|------|----------|------|------|
| **관계형 DB** | PostgreSQL + pgvector | 16 | 메인 데이터 저장, 벡터 검색 |
| **그래프 DB** | Neo4j | 5.x | 엔티티 관계 그래프 |
| **임베딩** | OpenAI text-embedding-3-small | - | 문서 벡터화 (1536차원) |
| **LLM** | OpenAI GPT-4 | - | 자연어 응답 생성 |
| **백엔드** | Python + FastAPI | 3.11 | API 서버 |
| **프론트엔드** | React + Next.js | - | 사용자 인터페이스 |
| **컨테이너** | Docker | - | 서비스 컨테이너화 |
| **형상관리** | Git + GitHub | - | 소스코드 관리 |

---

## 3. Phase별 작업 내역

### Phase 0R: Clean Architecture 구축
**기간**: 2025-12-10 ~ 2025-12-11

| 작업 | 사용 프로그램/파일 | 결과 |
|------|-------------------|------|
| 프로젝트 구조 설계 | 디렉토리 구조 | `insurance-ontology-v2/` 생성 |
| Ingestion 최적화 | `ingestion/ingest_v3.py` | CoverageMapper 제거, **60% 성능 향상** |
| Validation 규칙 구축 | `ingestion/parsers/base_parser.py` | 24개 검증 규칙 |
| Dual Mode 설계 | 환경변수 `COVERAGE_VALIDATION_STRICT` | NORMAL/STRICT 모드 지원 |

---

### Phase 1: Document Ingestion
**기간**: 2025-12-11

| 작업 | 사용 프로그램/파일 | 결과 |
|------|-------------------|------|
| PDF 문서 파싱 | `ingestion/ingest_v3.py` | 38개 문서 **100% 처리** |
| 하이브리드 파싱 | `ingestion/parsers/hybrid_parser_v2.py` | validation + cleaning 적용 |
| 회사별 파서 개발 | `ingestion/parsers/carrier_parsers/*.py` | 8개 보험사 맞춤 파서 |

**처리 결과**:
```
Documents:        38/38 (100%)
Total clauses:    80,682
Table row clauses: 548
Unique coverages: 348
Processing time:  ~10분
```

---

### Phase 2: Entity Extraction & Linking
**기간**: 2025-12-11

| 단계 | 사용 프로그램/파일 | 주요 로직 | 결과 |
|------|-------------------|----------|------|
| **2.1 Coverage Pipeline** | `ingestion/coverage_pipeline.py` | 담보명 추출 및 정규화 | 384개 coverage |
| **2.2 Benefit Extraction** | `ingestion/extract_benefits.py` | 한국어 금액 파싱 (lines 30-80) | 384개 benefit |
| **2.3 Clause-Coverage Linking** | `ingestion/link_clauses.py` | Exact + Fuzzy 매칭 | 674개 매핑 |
| **2.4 Disease Code Loading** | `ingestion/load_disease_codes.py` | 질병코드 로딩 | 9 sets, 131 codes |

**한국어 금액 파싱 개선**:
- Before: 99개 benefit 추출
- After: **384개 benefit 추출** (+285%)
- 파싱 패턴: "1,000만원", "3천만원", "500만원" 등

---

### Phase 3: Graph Synchronization (Neo4j)
**기간**: 2025-12-11

| 작업 | 사용 프로그램/파일 | 결과 |
|------|-------------------|------|
| PostgreSQL → Neo4j 동기화 | `ingestion/graph_loader.py` | 완료 |

**Neo4j 그래프 통계**:
```
Total nodes:        640
Total relationships: 623

Node Types:
- Coverage:         384
- Benefit:          384
- Company:          8
- Product:          8
- DiseaseCodeSet:   9
- DiseaseCode:      131

Relationships:
- COVERS:           384 (Coverage → Benefit)
- APPLIES_TO:       131 (Coverage → DiseaseCode)
- OFFERS:           16 (Company → Product)
```

---

### Phase 4: Vector Index Build
**기간**: 2025-12-11

| 작업 | 사용 프로그램/파일 | 설정 |
|------|-------------------|------|
| 임베딩 생성 | `vector_index/build_index.py` | Resume 기능 포함 (lines 112-146) |
| OpenAI API 연동 | OpenAI text-embedding-3-small | 1536차원 벡터 |

**결과**:
```
Total clauses embedded: 80,682
Model:                  text-embedding-3-small
Dimension:              1536
Backend:                OpenAI API
Processing time:        ~30분 (with resume)
Storage:                PostgreSQL clause_embedding 테이블
```

---

### Phase 5: QA Evaluation & Optimization

#### v1 → v2: Context Enrichment (+8%)
| 개선 사항 | 파일 및 위치 | 효과 |
|----------|-------------|------|
| Coverage/Benefit 데이터 병합 | `retrieval/context_assembly.py` (lines 211-263) | Age, Edge Case 개선 |
| Transaction Isolation | `scripts/evaluate_qa.py` (lines 75-81) | 에러 5건 → 0건 |

**정확도**: 60% → **68%** (+8%)

---

#### v2 → v3: Proposal Prioritization (+12%)
| 개선 사항 | 파일 및 위치 | 효과 |
|----------|-------------|------|
| 담보 키워드 감지 | `retrieval/hybrid_retriever.py` (lines 94-107) | 가입설계서 우선 검색 |
| Coverage query detection | 진단금, 수술비 등 키워드 | Basic/Comparison/Condition 100% |

**정확도**: 68% → **80%** (+12%)

---

#### v3 → v4: Tiered Fallback Search (+0%)
| 개선 사항 | 파일 및 위치 | 효과 |
|----------|-------------|------|
| 5-tier 검색 | `retrieval/hybrid_retriever.py` | 100% 검색 성공률 |
| Coverage Normalization | DB schema 확장 | 신정원 264개 표준코드 매핑 |
| standard_coverage_code 컬럼 | `coverage` 테이블 | 181개 (47.1%) 매핑 완료 |

**정확도**: 80% → **80%** (구조 개선, 정확도 유지)

---

#### v4 → v5: LLM Prompt Engineering (+6%) ⭐
| 개선 사항 | 파일 및 위치 | 효과 |
|----------|-------------|------|
| 금액 표시 개선 | `retrieval/context_assembly.py` | "💰 **1,000만원**" 포맷 |
| System Prompt 강화 | `retrieval/prompts.py` | 금액 추출 지침 추가 |

**정확도**: 80% → **86%** (+6%)

---

#### v6: Few-Shot 실험 (실패 → 롤백)
| 시도 | 결과 | 원인 |
|------|------|------|
| Few-shot examples 추가 | -10% 성능 저하 | Prompt 과부하, Attention Bias |
| Korean amount parsing 버그 발견 | 수정 완료 | "3,000만원" 형식 처리 개선 |

**조치**: v5로 롤백, 버그 수정만 유지

---

## 4. 카테고리별 최종 성능 (v5)

| Category | 정확도 | 개선 (v1→v5) | 상태 |
|----------|--------|-------------|------|
| **Basic** | 100% (10/10) | - | ✅ Perfect |
| **Comparison** | 100% (6/6) | - | ✅ Perfect |
| **Condition** | 100% (4/4) | - | ✅ Perfect |
| **Premium** | 100% (2/2) | - | ✅ Perfect |
| **Gender** | 100% (6/6) | +33% | ✅ Perfect |
| **Age** | 100% (4/4) | **+75%** | ✅ Perfect |
| **Edge Case** | 83.3% (5/6) | **+66%** | ✅ Good |
| **Amount** | 50% (6/12) | - | ❌ Blocker |

---

## 5. 주요 성과 요약

| 지표 | 시작 (v1) | 최종 (v5) | 개선폭 |
|------|----------|----------|--------|
| **전체 정확도** | 60% | 86% | **+26%** |
| Gender 카테고리 | 67% | 100% | +33% |
| Age 카테고리 | 25% | 100% | **+75%** |
| Edge Case | 17% | 83% | **+66%** |
| 에러 발생 | 5건 | 0건 | **-100%** |
| Latency (P95) | 7,011ms | 6,845ms | -166ms |

**6개 카테고리 100% 달성**: Basic, Comparison, Condition, Premium, Gender, Age

---

## 6. 데이터베이스 현황

### PostgreSQL 테이블
| 테이블 | 레코드 수 | 용량 | 비고 |
|--------|----------|------|------|
| clause_embedding | 80,682 | 1,812 MB | 벡터 임베딩 |
| document_clause | 80,682 | 72 MB | 조항 텍스트 |
| clause_coverage | 674 | 984 KB | 조항-담보 매핑 |
| coverage | 384 | 256 KB | 181개 standard code |
| benefit | 384 | 104 KB | 보장금액 |
| document | 38 | 144 KB | 약관 문서 |
| company | 8 | 88 KB | 보험사 |
| product | 8 | 72 KB | 상품 |
| disease_code | 131 | 48 KB | 질병코드 |

### Neo4j 그래프
- **Nodes**: 640개
- **Relationships**: 623개
- **동기화 상태**: PostgreSQL과 일치

---

## 7. 핵심 파일 목록

### Ingestion (데이터 수집)
| 파일 | 역할 |
|------|------|
| `ingestion/ingest_v3.py` | PDF 문서 파싱 메인 |
| `ingestion/parsers/hybrid_parser_v2.py` | 하이브리드 파서 (validation 포함) |
| `ingestion/parsers/carrier_parsers/*.py` | 8개 보험사별 파서 |
| `ingestion/coverage_pipeline.py` | 담보 추출 파이프라인 |
| `ingestion/extract_benefits.py` | 보장금액 추출 (한국어 파싱) |
| `ingestion/link_clauses.py` | 조항-담보 매핑 |
| `ingestion/graph_loader.py` | Neo4j 동기화 |

### Retrieval (검색)
| 파일 | 역할 |
|------|------|
| `retrieval/hybrid_retriever.py` | 하이브리드 검색 (벡터 + 키워드) |
| `retrieval/context_assembly.py` | 컨텍스트 조립 및 포맷팅 |
| `retrieval/prompts.py` | LLM 시스템 프롬프트 |

### API & Scripts
| 파일 | 역할 |
|------|------|
| `api/server.py` | FastAPI 서버 |
| `api/compare.py` | 상품 비교 API |
| `scripts/evaluate_qa.py` | QA 평가 스크립트 |
| `vector_index/build_index.py` | 벡터 인덱스 빌드 |

---

## 8. 교훈 및 향후 과제

### 8.1 핵심 교훈

1. **Context Enrichment 효과**
   - 구조화된 데이터(coverage/benefit)를 컨텍스트에 추가하면 Age/Edge Case 대폭 개선

2. **Proposal Prioritization 중요성**
   - 가입설계서 우선 검색으로 정확한 금액 정보 제공 → +12% 개선

3. **"More instruction ≠ Better performance"**
   - Few-shot examples 추가가 오히려 -10% 성능 저하 유발
   - 과도한 instruction은 LLM 혼란 초래

4. **Transaction Isolation 필수**
   - 1개 에러가 5개 실패로 번지는 cascade 방지

### 8.2 향후 과제

| 우선순위 | 과제 | 예상 효과 |
|---------|------|----------|
| 1 | Amount 카테고리 개선 (50% → 80%) | +4% overall |
| 2 | Latency 최적화 (P95 < 5,000ms) | 사용자 경험 개선 |
| 3 | Standard Coverage 매핑 확대 (47% → 70%) | 회사간 비교 강화 |
| 4 | Production DB 적용 | 실서비스 배포 |

---

## 9. 결론

본 프로젝트는 2일간의 집중 개발을 통해 **60% → 86%**의 정확도 개선을 달성했습니다.
6개 QA 카테고리에서 100% 정확도를 달성하였으며, 90% 목표까지 **단 2개 쿼리**만 남았습니다.

주요 기술적 성과:
- 80,682개 조항의 벡터 임베딩 구축
- 5단계 Tiered Fallback 검색 시스템
- 신정원 표준코드 기반 담보 정규화
- 한국어 금액 파싱 최적화

---

**작성자**: Claude Code
**마지막 업데이트**: 2025-12-12
