# 설계 문서 인덱스

> 작성일: 2025-12-13

## 개요

이 디렉토리는 데이터베이스 설계 문서를 포함합니다. 각 설계 문서는 해당 구현 파일과 연결됩니다.

---

## 문서 구조

### PostgreSQL 설계 문서

```
ER_DIAGRAM.md (전체 구조 시각화) ─────────────┐
    │                                         │
    ├── DATA_DICTIONARY.md (테이블/컬럼 상세)  │
    ├── RELATIONSHIP_MAP.md (외래키 관계)      │
    └── DOMAIN_MODEL.md (비즈니스 도메인)      │
                                              ↓
                              ┌───────────────────────────────┐
                              │ 구현 파일                      │
                              │ ../postgres/001_initial_schema.sql │
                              │ ../postgres/002_seed_data.sql      │
                              └───────────────────────────────┘
```

### Neo4j 설계 문서

```
GRAPH_SCHEMA.md (그래프 모델 설계) ───────────┐
    │                                         │
    ├── NODE_DICTIONARY.md (노드 속성 상세)    │
    ├── RELATIONSHIP_DICTIONARY.md (관계 상세) │
    ├── GRAPH_PATTERNS.md (Cypher 쿼리 패턴)   │
    └── ONTOLOGY_GAP_ANALYSIS.md (갭 분석)    │
                                              ↓
                              ┌───────────────────────────────┐
                              │ 구현 파일                      │
                              │ ../neo4j/001_graph_schema.cypher   │
                              │ ../../ingestion/graph_loader.py    │
                              └───────────────────────────────┘
```

---

## 설계 → 구현 연결

| 설계 문서 | 구현 파일 | 상태 |
|-----------|-----------|------|
| **PostgreSQL** | | |
| ER_DIAGRAM.md | `../postgres/001_initial_schema.sql` | ✅ 구현됨 |
| ER_DIAGRAM.md | `../postgres/002_seed_data.sql` | ✅ 구현됨 |
| **Neo4j** | | |
| GRAPH_SCHEMA.md | `../neo4j/001_graph_schema.cypher` | ⬜ Phase 4.1 예정 |
| GRAPH_SCHEMA.md | `../../ingestion/graph_loader.py` | ✅ 구현됨 |

---

## 문서 목록

### PostgreSQL 문서

| 문서 | 설명 | 역할 |
|------|------|------|
| [ER_DIAGRAM.md](./ER_DIAGRAM.md) | E-R 다이어그램 | 전체 구조 시각화 (Mermaid) |
| [DATA_DICTIONARY.md](./DATA_DICTIONARY.md) | 데이터 사전 | 테이블/컬럼 정의, 타입, 제약조건 |
| [RELATIONSHIP_MAP.md](./RELATIONSHIP_MAP.md) | 관계 맵 | 외래키 관계, 카디널리티 |
| [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) | 도메인 모델 | 비즈니스 도메인 설명 |

### Neo4j 문서

| 문서 | 설명 | 역할 |
|------|------|------|
| [GRAPH_SCHEMA.md](./GRAPH_SCHEMA.md) | 그래프 스키마 | 노드/관계 타입, 설계 원칙 |
| [NODE_DICTIONARY.md](./NODE_DICTIONARY.md) | 노드 사전 | 노드 레이블별 속성 정의 |
| [RELATIONSHIP_DICTIONARY.md](./RELATIONSHIP_DICTIONARY.md) | 관계 사전 | 관계 타입별 정의, 방향성 |
| [GRAPH_PATTERNS.md](./GRAPH_PATTERNS.md) | 쿼리 패턴 | 자주 사용되는 Cypher 쿼리 |
| [ONTOLOGY_GAP_ANALYSIS.md](./ONTOLOGY_GAP_ANALYSIS.md) | 갭 분석 | 설계 vs 구현 차이 분석 |

---

## 문서 작성 원칙

1. **설계 문서에 구현 파일 명시**: 각 설계 문서 하단에 "구현 파일" 섹션 포함
2. **상호 참조**: 관련 문서 간 링크 유지
3. **상태 추적**: 구현 상태 (✅ 구현됨 / ⬜ 예정) 표시
4. **변경 동기화**: 구현 변경 시 설계 문서 업데이트

---

## 관련 링크

- [task.md](../../docs/task.md) - 작업 진행 상황
- [database_refactoring.md](../../docs/database_refactoring.md) - 리팩토링 상세 계획
