# Insurance Ontology - Hybrid RAG System

**Status**: ✅ Phase 5 Complete (86% Accuracy)
**Version**: v2.0
**Last Updated**: 2025-12-11

---

## 🎯 프로젝트 개요

한국 보험 약관 문서(PDF)를 Hybrid RAG 시스템으로 변환:
- **QA Bot**: 자연어 질의응답 (86% accuracy)
- **상품 비교**: Multi-carrier comparison
- **설계서 검증**: Plan validation

**데이터**:
- 38 PDF documents (8 carriers)
- 80,682 clauses
- 384 coverages & benefits
- 640 Neo4j nodes

**기술 스택**:
- PostgreSQL (pgvector)
- Neo4j
- OpenAI GPT-4o-mini
- Python 3.11+

---

## 🚀 빠른 시작 (프로덕션 배포)

### 1. 환경 설정
```bash
cd insurance-ontology-v2
cp .env.template .env
# .env 파일에 OPENAI_API_KEY 설정
```

### 2. 서비스 시작
```bash
docker-compose up -d
./scripts/init_db.sh
```

### 3. 전체 파이프라인 실행
```bash
# Phase 1: Document Ingestion (~10분)
python scripts/batch_ingest.py --all --batch-size 5

# Phase 2: Entity Extraction (~15분)
python -m ingestion.coverage_pipeline --carrier all
python -m ingestion.extract_benefits
python -m ingestion.load_disease_codes
python -m ingestion.link_clauses --method all

# Phase 3: Graph Sync (~3분)
python -m ingestion.graph_loader --all

# Phase 4: Vector Index (~30분)
export OPENAI_API_KEY="sk-..."
python -m vector_index.build_index --backend openai

# Phase 5: QA Evaluation (~5분)
python scripts/evaluate_qa.py \
  --qa-set data/gold_qa_set_50.json \
  --output results/evaluation.json
```

### 4. 검증
```bash
# 정확도 확인
cat results/evaluation.json | jq '.overall.accuracy'
# Expected: 86.0

# Embeddings 확인
psql $POSTGRES_URL -c "SELECT COUNT(*) FROM clause_embedding;"
# Expected: 80682

# Neo4j 확인
# http://localhost:7474
# Query: MATCH (n) RETURN labels(n), count(*)
# Expected: 640 nodes
```

**상세 가이드**: [`docs/PRODUCTION_DEPLOY.md`](./docs/PRODUCTION_DEPLOY.md)

---

## 📊 현재 상태

```
✅ Phase 0R: Clean Architecture
✅ Phase 1: Document Ingestion (38 docs, 80,682 clauses)
✅ Phase 2: Entity Extraction (384 coverages, 384 benefits)
✅ Phase 3: Neo4j Sync (640 nodes)
✅ Phase 4: Vector Index (80,682 embeddings)
✅ Phase 5: Hybrid RAG (86% accuracy)
```

**상세 현황**: [`CURRENT_STATUS.md`](./CURRENT_STATUS.md)

---

## 📁 프로젝트 구조

```
insurance-ontology-v2/
├── retrieval/              # Phase 5: Hybrid RAG
│   ├── hybrid_retriever.py     # 5-tier fallback search
│   ├── context_assembly.py     # Coverage/benefit enrichment
│   ├── prompts.py              # LLM prompts (Phase 5 v5)
│   └── llm_client.py           # OpenAI integration
├── ingestion/              # Phase 1-3: Data pipeline
│   ├── ingest_v3.py
│   ├── parsers/
│   │   └── carrier_parsers/    # 8 carrier-specific parsers
│   ├── coverage_pipeline.py
│   ├── extract_benefits.py
│   ├── link_clauses.py
│   └── graph_loader.py
├── vector_index/           # Phase 4: Embeddings
│   └── build_index.py
├── scripts/
│   ├── batch_ingest.py
│   ├── evaluate_qa.py          # QA evaluation
│   ├── health_check.sh
│   └── init_db.sh
├── data/
│   └── gold_qa_set_50.json     # 50-query test set
├── docs/
│   ├── design/
│   │   ├── DESIGN.md           # 전체 설계 (Phase 0-5)
│   │   ├── CLAUDE.md
│   │   └── CHANGELOG.md
│   ├── PRODUCTION_DEPLOY.md    # 🚀 배포 가이드
│   ├── phase2/
│   ├── phase5/                 # Phase 5 분석 문서
│   └── archive/
├── evaluation/
│   ├── evaluation_v5_fixed.log
│   └── results/
│       └── phase5_evaluation_v5_fixed.json
└── CURRENT_STATUS.md           # 최신 진행 상황
```

---

## 🔧 주요 명령어

### 시스템 상태 확인
```bash
# Health check (추천!)
./scripts/health_check.sh

# DB 상태
psql $POSTGRES_URL -c "SELECT COUNT(*) FROM document; SELECT COUNT(*) FROM clause_embedding;"
```

### QA 쿼리 실행
```bash
# CLI로 쿼리 테스트
python -m api.cli hybrid "삼성화재 암 진단금은?"

# 평가 실행
python scripts/evaluate_qa.py \
  --qa-set data/gold_qa_set_50.json \
  --output results/evaluation.json
```

### 재실행 (필요 시)
```bash
# DB 초기화
./scripts/init_db.sh

# 특정 Phase만 재실행
python scripts/batch_ingest.py --all              # Phase 1
python -m ingestion.coverage_pipeline --carrier all  # Phase 2.1
python -m vector_index.build_index --backend openai # Phase 4
```

---

## 📖 문서

| 문서 | 용도 |
|------|------|
| [README.md](./README.md) | 본 문서 (빠른 시작) |
| [CURRENT_STATUS.md](./CURRENT_STATUS.md) | 최신 진행 상황 (Phase 5 완료) |
| [docs/design/DESIGN.md](./docs/design/DESIGN.md) | 전체 설계 (Phase 0-5, 981줄) |
| [docs/PRODUCTION_DEPLOY.md](./docs/PRODUCTION_DEPLOY.md) | 🚀 프로덕션 배포 가이드 |
| [docs/phase5/](./docs/phase5/) | Phase 5 분석 문서 (v2-v6) |
| [RECOVERY_GUIDE.md](./RECOVERY_GUIDE.md) | 시스템 복구 가이드 |
| [VALIDATION_MODES.md](./VALIDATION_MODES.md) | Validation 모드 설명 |

---

## 📊 Phase 5 성능

### 전체 결과
```
Overall Accuracy: 86.0% (43/50 queries) ✅
Errors:           0
Avg Latency:      3,770ms
P95 Latency:      8,690ms
```

### Category별 성능
| Category | Accuracy | Status |
|----------|----------|--------|
| Basic | 100% (10/10) | ✅ Perfect |
| Comparison | 100% (6/6) | ✅ Perfect |
| Condition | 100% (4/4) | ✅ Perfect |
| Premium | 100% (2/2) | ✅ Perfect |
| Gender | 100% (6/6) | ✅ Perfect |
| Age | 100% (4/4) | ✅ Perfect |
| Edge Case | 83.3% (5/6) | ✅ Good |
| Amount | 50% (6/12) | ⚠️ Known limitation |

**상세 분석**: [`docs/phase5/PHASE5_V5_SUMMARY.md`](./docs/phase5/PHASE5_V5_SUMMARY.md)

---

## 🔑 핵심 기능

### 1. Hybrid RAG Architecture
```
Query → NL Mapper → Vector Search → Context Assembly → LLM → Answer
```

### 2. 5-Tier Fallback Search
- Zero-result queries: 0% (was 12% in v3)
- Automatic fallback: proposal → business_spec → terms → all

### 3. Korean Amount Parsing
- Handles formats: "3,000만원", "1억", "500만원"
- SQL-based parsing for efficient filtering

### 4. Coverage Normalization
- 264 standard mappings (8 carriers → 28 codes)
- Cross-company comparison enabled

---

## ⚠️ 주의사항

### Database
- **현재 사용**: `insurance_ontology_test` (TEST DB)
- **Production**: 프로덕션 배포 시 DB 이름 변경 필요

### API Key
- **필수**: `.env` 파일에 `OPENAI_API_KEY` 설정
- **Phase 4-5**: OpenAI API 필요 (Vector index + QA)

### Backup
- **Backup 위치**: `/Users/cheollee/insurance-ontology-claude-backup-2025-12-10/`
- **용도**: 참고용 아카이브
- **작업**: `insurance-ontology-v2/`에서만 진행

---

## 🆘 도움말

### 시스템 다운 시
1. **Health check**: `./scripts/health_check.sh`
2. **복구 가이드**: [`RECOVERY_GUIDE.md`](./RECOVERY_GUIDE.md)
3. **현재 상태 확인**: [`CURRENT_STATUS.md`](./CURRENT_STATUS.md)

### 에러 발생 시
```bash
# Docker 확인
docker ps

# DB 연결 확인
psql $POSTGRES_URL -c "SELECT 1;"

# Checkpoint 확인
cat data/checkpoints/phase1_progress.json
```

---

## 🎯 다음 단계 (Phase 6)

### Option 1: API 서버 배포
- FastAPI 엔드포인트 구축
- RESTful API 제공

### Option 2: 90% Accuracy 달성
- LLM 모델 업그레이드 (gpt-4-turbo)
- Post-processing amount extraction
- Context size 최적화

### Option 3: Frontend 연동
- React/Next.js UI
- 실시간 QA 인터페이스

---

## 📋 체크리스트

**프로덕션 배포 준비 완료**:
- [x] Phase 0: Clean Architecture
- [x] Phase 1: Document Ingestion (38 docs)
- [x] Phase 2: Entity Extraction (384 coverages)
- [x] Phase 3: Neo4j Sync (640 nodes)
- [x] Phase 4: Vector Index (80,682 embeddings)
- [x] Phase 5: Hybrid RAG (86% accuracy)
- [x] Korean Amount Parsing Fix
- [x] Coverage Normalization (264 codes)
- [x] Documentation (DESIGN.md, PRODUCTION_DEPLOY.md)
- [x] Zero Errors

**프로덕션 준비 상태**: ✅ **YES**

---

**마지막 업데이트**: 2025-12-11 12:00 KST
**현재 Phase**: Phase 5 Complete ✅
**정확도**: 86% (43/50 queries)
**Production Ready**: Yes
