# DB 전환 작업 계획

**작성일**: 2025-12-13
**목적**: 테스트 DB를 새로운 운영 DB로 전환
**현재 상태**: ✅ 완료

---

## 환경 설정 (권장안)

| 항목 | 기존 | 신규 |
|------|------|------|
| PostgreSQL 포트 | 5432 | **15432** |
| PostgreSQL DB명 | insurance_ontology | **insurance_ontology_test** |
| Neo4j Bolt 포트 | 7687 | **17687** |
| Neo4j HTTP 포트 | 7474 | **17474** |

---

## 작업 단계

### Phase A: 환경 설정 (30분) ✅

| ID | Task | 상태 | 완료일 |
|----|------|------|--------|
| A.1 | 프로젝트 루트에 `.env` 파일 생성 | ✅ DONE | 2025-12-13 |
| A.2 | 새 DB 연결 정보 정의 | ✅ DONE | 2025-12-13 |
| A.3 | docker-compose.yml 최종화 | ✅ DONE | 2025-12-13 |

### Phase B: 코드 수정 (1시간) ✅

| ID | Task | 상태 | 완료일 |
|----|------|------|--------|
| B.1 | 하드코딩된 `localhost:5432` fallback 제거 | ✅ DONE | 2025-12-13 |
| B.2 | 모든 파일에 `load_dotenv()` 표준화 | ✅ DONE | 2025-12-13 |
| B.3 | 환경변수 없을 시 에러 발생하도록 수정 | ✅ DONE | 2025-12-13 |

**수정된 파일 (16개)**:
- ingestion/ingest_v3.py, coverage_pipeline.py, extract_benefits.py, link_clauses.py, load_disease_codes.py, graph_loader.py
- vector_index/build_index.py, retriever.py
- retrieval/hybrid_retriever.py, context_assembly.py
- ontology/nl_mapping.py
- api/cli.py, compare.py, server.py
- scripts/reingest_with_structured_chunking.py, audit_parsing_quality.py

### Phase C: 데이터 마이그레이션 (30분) ✅

| ID | Task | 상태 | 완료일 |
|----|------|------|--------|
| C.1 | 기존 DB에서 데이터 pg_dump | ✅ DONE | 2025-12-13 |
| C.2 | 새 DB에 데이터 적용 | ✅ DONE | 2025-12-13 |
| C.3 | 레코드 수 검증 | ✅ DONE | 2025-12-13 |

**마이그레이션 결과**:
- document: 38
- document_clause: 134,844
- coverage: 363
- benefit: 357
- clause_coverage: 4,903
- disease_code: 131
- clause_embedding: 미마이그레이션 (1.8GB, 필요시 `python -m vector_index.build_index`로 재생성)

### Phase D: Neo4j 동기화 (20분) ✅

| ID | Task | 상태 | 완료일 |
|----|------|------|--------|
| D.1 | graph_loader.py 실행 | ✅ DONE | 2025-12-13 |
| D.2 | 노드/관계 수 검증 | ✅ DONE | 2025-12-13 |

**Neo4j 결과**:
- Nodes: 918
- Relationships: 949

### Phase E: 테스트 (30분) ✅

| ID | Task | 상태 | 결과 |
|----|------|------|-----------|
| E.1 | PostgreSQL 연결 테스트 | ✅ DONE | 38 documents |
| E.2 | Neo4j 연결 테스트 | ✅ DONE | 918 nodes |
| E.3 | 환경변수 로딩 테스트 | ✅ DONE | .env 정상 로딩 |

### Phase F: 문서 업데이트 (20분) ✅

| ID | Task | 상태 | 완료일 |
|----|------|------|--------|
| F.1 | task_upgrade.md 업데이트 | ✅ DONE | 2025-12-13 |
| F.2 | .env 파일 생성 완료 | ✅ DONE | 2025-12-13 |

---

## 영향받는 파일 목록 (17개+)

### ingestion/ (6개)
- `ingest_v3.py`
- `coverage_pipeline.py`
- `extract_benefits.py`
- `link_clauses.py`
- `load_disease_codes.py`
- `graph_loader.py`

### vector_index/ (2개)
- `build_index.py`
- `retriever.py`

### retrieval/ (2개)
- `hybrid_retriever.py`
- `context_assembly.py`

### ontology/ (1개)
- `nl_mapping.py`

### api/ (3개)
- `cli.py`
- `compare.py`
- `server.py`

### scripts/ (4개+)
- `init_db.sh`
- `init_neo4j.sh`
- `health_check.sh`
- `verify_production_deploy.sh`

---

## 진행 이력

| 날짜 | Phase | 변경 내용 |
|------|-------|----------|
| 2025-12-13 | A | .env 파일 생성 및 환경 설정 |
| 2025-12-13 | B | 16개 파일 수정 (하드코딩 URL 제거, dotenv 표준화) |
| 2025-12-13 | C | 데이터 마이그레이션 (pg_dump → 새 DB) |
| 2025-12-13 | D | Neo4j 동기화 (graph_loader.py) |
| 2025-12-13 | E | 연결 테스트 완료 |
| 2025-12-13 | F | 문서 업데이트 완료 |

---

**실제 소요 시간**: ~1.5시간

## 남은 작업

1. **임베딩 재생성** (선택사항): `python -m vector_index.build_index`
   - 1.8GB 데이터, 약 30분 소요 예상

2. **QA 테스트** (선택사항): `python scripts/evaluate_qa.py`
   - 86% 정확도 목표
