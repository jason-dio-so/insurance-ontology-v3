# PDF 추출 파이프라인

**생성일**: 2025-12-14 | **최종 업데이트**: 2025-12-14 | **상태**: ✅ 완료

---

## 현재 상태

| 구성요소 | 상태 | 데이터 |
|----------|------|--------|
| `utils/pdf_converter.py` | ✅ | pdfplumber 기반, 38개 문서 변환 |
| `ingest_v3.py` | ✅ | ~80,000 document_clause |
| `coverage_pipeline.py` | ✅ | 294 coverages |
| `proposal_plan_extractor.py` | ✅ | 10 Plans, 614 plan_coverage |
| `risk_event_extractor.py` | ✅ | 572 risk_events |
| `exclusion_extractor.py` | ✅ | 28건 |
| `condition_extractor.py` | ✅ | 42건 |

---

## 아키텍처

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

### 파이프라인 흐름

```
examples/*.pdf → pdf_converter.py → data/converted_v2/
                                           ↓
                         ingest_v3.py → document, document_clause
                                           ↓
                    coverage_pipeline.py → coverage (294개)
                                           ↓
                proposal_plan_extractor.py → plan, plan_coverage
                risk_event_extractor.py   → risk_event
                exclusion_extractor.py    → exclusion
                condition_extractor.py    → condition
                                           ↓
                              graph_loader.py → Neo4j
```

### 회사별 차이 처리

| 처리 단계 | 도구 | 회사별 차이 처리 방식 |
|----------|------|---------------------|
| PDF → JSON | `pdf_converter.py` | 범용 (pdfplumber) |
| Plan 추출 | `proposal_plan_extractor.py` | 패턴 매칭 (KB/Samsung: 공백, Hyundai: 연결) |
| RiskEvent 추출 | `risk_event_extractor.py` | 패턴 매칭 (ICD 코드, 정의 조항) |
| Exclusion 추출 | `exclusion_extractor.py` | 패턴 매칭 (면책 조항) |
| Condition 추출 | `condition_extractor.py` | 패턴 매칭 (대기기간 등) |

---

## 실행 명령어

### PDF 변환
```bash
python scripts/convert_documents.py --output-dir data/converted_v2
python scripts/convert_documents.py --company-code samsung  # 특정 회사만
```

### 데이터 Ingestion
```bash
# 전체 ingestion
python -m ingestion.ingest_v3 data/documents_metadata.json

# Coverage 추출
python -m ingestion.coverage_pipeline

# Plan 추출
python -m ingestion.proposal_plan_extractor

# Risk Event 추출
python -m ingestion.risk_event_extractor

# Exclusion/Condition 추출
python -m ingestion.exclusion_extractor
python -m ingestion.condition_extractor
```
