# PDF 추출 파이프라인 Tasks

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

## 최근 변경 (2025-12-14)

### 1. Coverage 필터 개선
`base_parser.py`의 노이즈 필터 강화:

| 필터 | 대상 |
|------|------|
| 띄어쓰기 비율 | >25% 제외 |
| 깨진 한글 | "비급 여 (전 액본 인부 담포 함)" |
| 플랜 타입 | "운전자형", "납입면제형" |
| (급여) suffix | 의료행위 코드 |
| 법률비용 | 특약 타입 |

**결과**: 533개 → 294개 (45% 노이즈 제거)

### 2. 스키마 통합 (r1 → v3)
4개 테이블 추가:

| 테이블 | 용도 | 레코드 |
|--------|------|--------|
| `plan` | 가입설계 메타데이터 | 10개 |
| `plan_coverage` | 가입설계-담보 연결 | 614개 |
| `risk_event` | 위험 이벤트 정의 | 572개 |
| `benefit_risk_event` | 급부-위험이벤트 매핑 | 0개 |

### 3. clause_number 추출 수정
숫자 prefix 필터 비활성화 → `_clean_coverage_name()`에서 분리:
```
"119 뇌졸중진단비" → clause_number: "119", coverage_name: "뇌졸중진단비"
```

---

## 파이프라인

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

### Neo4j 동기화
```bash
python -m ingestion.graph_loader --all
python db_refactoring/scripts/verify_neo4j_sync.py  # 검증
```

---

## 회사별 데이터 현황

### Coverage 수
| 회사 | Coverage | Plan Coverage |
|------|----------|---------------|
| hyundai | 48개 | 75개 |
| hanwha | 46개 | 71개 |
| lotte | 38개 | 134개 (2 plans) |
| samsung | 36개 | 39개 |
| kb | 35개 | 73개 |
| db | 32개 | 106개 (2 plans) |
| meritz | 31개 | 52개 |
| heungkuk | 24개 | 64개 |
| **총합** | **294개** | **614개** |

### 회사별 패턴 차이
| 회사 | 패턴 예시 | 처리 |
|------|----------|------|
| Samsung/KB | `20년납 100세만기` | 공백 구분 |
| Hyundai | `20년납100세만기` | 연결 |
| Lotte | `100세만기/20년납` | 역순 |

→ `proposal_plan_extractor.py`에서 정규식 패턴으로 처리

---

## 출력 구조

```
data/converted_v2/{company}/{doc_id}/
├── metadata.json, text.json, sections.json
├── tables_index.json
└── tables/*.json
```

---

## 수정 파일 목록 (2025-12-14)

| 파일 | 변경 내용 |
|------|----------|
| `base_parser.py` | 노이즈 필터 추가, 숫자 prefix 필터 비활성화 |
| `coverage_pipeline.py` | 필드명 수정 (coverage_amount, period) |
| `proposal_plan_extractor.py` | 경로 매핑 추가 (company_code → 한글 디렉토리) |
| `001_initial_schema.sql` | r1 스키마로 교체 (4개 테이블 추가) |

---

## 참고

- [pdf_ext.md](./pdf_ext.md) - 상세 설계
- [parser_refact_tasks.md](./parser_refact_tasks.md) - 엔티티 추출 상세
- [session_20241214_summary.md](./session_20241214_summary.md) - 2024-12-14 작업 요약
