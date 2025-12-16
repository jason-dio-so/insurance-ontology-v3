# Insurance Ontology - Hybrid RAG System

**Status**: ✅ Phase 6 Complete (API Server + Frontend)
**Version**: v3.0
**Last Updated**: 2025-12-16

---

## 프로젝트 개요

한국 보험 약관 문서(PDF)를 Hybrid RAG 시스템으로 변환:
- **QA Bot**: 자연어 질의응답 (100% accuracy)
- **상품 비교**: 전체 보험사 비교 (8개 보험사)
- **API 서버**: FastAPI 기반 REST API
- **Frontend**: React + Vite 웹 인터페이스

**데이터**:
- 38 PDF documents (8 carriers)
- 80,602 document clauses
- 67,841 clause embeddings (pgvector)
- 249 coverages, 243 benefits
- Neo4j: 1,687 nodes

**기술 스택**:
- PostgreSQL 15 (pgvector)
- Neo4j 5.15
- OpenAI GPT-4o-mini
- FastAPI + Uvicorn
- React + Vite + TailwindCSS
- Python 3.11+

---

## 빠른 시작

### 1. 환경 설정
```bash
cd insurance-ontology-v3
cp .env.example .env
# .env 파일에 필수 환경변수 설정
```

### 2. Docker 서비스 시작
```bash
docker-compose up -d
```

| 서비스 | 포트 | 용도 |
|--------|------|------|
| PostgreSQL | 15432 | 메인 DB + pgvector |
| Neo4j HTTP | 17474 | 브라우저 UI |
| Neo4j Bolt | 17687 | 드라이버 연결 |

### 3. 백엔드 서버 시작
```bash
./start_backend.sh
# 또는
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

### 4. 프론트엔드 시작
```bash
./start_frontend.sh
# 또는
cd frontend && npm install && npm run dev
```
- Web UI: http://localhost:5173

---

## 프로젝트 구조

```
insurance-ontology-v3/
├── api/                    # FastAPI 서버
│   ├── server.py               # 메인 API 엔드포인트
│   ├── cli.py                  # CLI 인터페이스
│   ├── compare.py              # 상품 비교 로직
│   └── info_extractor.py       # 정보 추출
├── frontend/               # React 웹 UI
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   ├── package.json
│   └── vite.config.ts
├── retrieval/              # Hybrid RAG
│   ├── hybrid_retriever.py     # 5-tier fallback search
│   ├── context_assembly.py     # Coverage/benefit enrichment
│   ├── prompts.py              # LLM 프롬프트
│   └── llm_client.py           # OpenAI 연동
├── ingestion/              # 데이터 파이프라인
│   ├── ingest_v3.py
│   ├── parsers/
│   │   ├── form_parser.py
│   │   └── hybrid_parser_v2.py
│   ├── coverage_pipeline.py
│   ├── extract_benefits.py
│   ├── graph_loader.py
│   └── link_clauses.py
├── ontology/               # 온톨로지 매핑
│   └── nl_mapping.py           # 자연어 → 온톨로지
├── vector_index/           # 벡터 인덱스
│   ├── build_index.py
│   └── openai_embedder.py
├── db_refactoring/         # DB 스키마 관리
│   ├── postgres/               # PostgreSQL DDL
│   ├── neo4j/                  # Cypher 스키마
│   └── migrations/             # Alembic 마이그레이션
├── scripts/                # 유틸리티 스크립트
│   ├── batch_ingest.py
│   └── evaluate_qa.py
├── utils/                  # 공통 유틸리티
├── docs/                   # 문서
├── data/                   # 데이터 (gitignore)
│   ├── backup/                 # DB 백업
│   └── converted_v2/           # 변환된 문서
├── docker-compose.yml      # Docker 설정
├── requirements.txt        # Python 의존성
├── start_backend.sh        # 백엔드 시작 스크립트
└── start_frontend.sh       # 프론트엔드 시작 스크립트
```

---

## API 엔드포인트

### 시스템
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/` | 기본 헬스 체크 |
| GET | `/health` | 상세 헬스 체크 (DB 연결 상태) |

### 검색
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/hybrid-search` | 하이브리드 검색 (메인 API) |
| POST | `/api/test-search` | 디버깅용 간단 검색 |
| POST | `/api/compare` | 상품 비교 |

### 데이터 조회
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/companies` | 보험사 목록 |
| GET | `/api/companies/{name}/products` | 보험사별 상품 목록 |
| GET | `/api/companies/{name}/coverages` | 보험사별 담보 목록 |
| GET | `/api/companies/{name}/products/{product}/coverages` | 상품별 담보 목록 |
| GET | `/api/coverages` | 전체 담보 목록 |

### 사용 예시
```bash
# CLI로 쿼리 테스트
python -m api.cli hybrid "삼성화재 암 진단금은?"

# 하이브리드 검색 API
curl -X POST http://localhost:8000/api/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{"query": "삼성 현대 암진단비 비교해줘"}'

# 보험사 목록 조회
curl http://localhost:8000/api/companies

# 보험사별 담보 조회
curl http://localhost:8000/api/companies/삼성/coverages
```

---

## 환경 변수

`.env` 파일 필수 설정:

```env
# PostgreSQL
POSTGRES_URL=postgresql://postgres:postgres@127.0.0.1:15432/insurance_ontology_test
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=15432

# Neo4j
NEO4J_URI=bolt://127.0.0.1:17687
NEO4J_USER=neo4j
NEO4J_PASSWORD=testpassword

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

---

## 개발 가이드

### 의존성 설치
```bash
# Python
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### DB 마이그레이션
```bash
cd db_refactoring
alembic upgrade head
```

### 테스트 실행
```bash
pytest
```

### 코드 포맷팅
```bash
black .
```

---

## 데이터 현황

### PostgreSQL
| 테이블 | 건수 |
|--------|------|
| document_clause | 80,602 |
| clause_embedding | 67,841 |
| coverage | 249 |
| benefit | 243 |
| document | 38 |
| plan | 10 |
| company | 8 |
| product | 8 |

### Neo4j
| 노드 | 건수 |
|------|------|
| RiskEvent | 572 |
| Exclusion | 408 |
| Coverage | 249 |
| Benefit | 243 |
| DiseaseCode | 131 |
| Document | 38 |
| Plan | 10 |
| DiseaseCodeSet | 9 |
| Company | 8 |
| Product | 8 |
| Condition | 7 |
| ProductVariant | 4 |
| **총계** | **1,687** |

---

## Git 관리

| Remote | Repository | 용도 |
|--------|------------|------|
| origin | jason-dio-so/insurance-ontology-v3 | 개인 작업 |
| upstream | Team-SpaceY/insurance-ontology-v3 | 팀 공유 |

```bash
# 개인 push
git push origin master

# 팀 공유
git push upstream master

# 팀 변경사항 가져오기
git fetch upstream && git merge upstream/master
```

---

## 문서

| 문서 | 설명 |
|------|------|
| [docs/pipeline_guide.md](./docs/pipeline_guide.md) | 데이터 파이프라인 가이드 |
| [docs/NEW_COMPANY_GUIDE.md](./docs/NEW_COMPANY_GUIDE.md) | 신규 보험사 온보딩 |
| [docs/database_refactoring.md](./docs/database_refactoring.md) | DB 스키마 설계 |
| [docs/FORM_PARSER_ARCHITECTURE_REPORT.md](./docs/FORM_PARSER_ARCHITECTURE_REPORT.md) | Form Parser 아키텍처 |
| [FRONTEND_GUIDE.md](./FRONTEND_GUIDE.md) | 프론트엔드 개발 가이드 |

---

## 주의사항

- **API Key**: `.env`에 `OPENAI_API_KEY` 필수
- **Docker**: PostgreSQL(15432), Neo4j(17474, 17687) 포트 사용
- **데이터**: `data/` 디렉토리는 gitignore (백업 포함)
- **examples/**: symlink로 연결된 PDF 원본 (대용량)

---

**마지막 업데이트**: 2025-12-16
**버전**: v3.0
**상태**: Production Ready
