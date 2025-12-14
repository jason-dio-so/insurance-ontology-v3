# pgvector HNSW 인덱스 가이드

## 개요

이 문서는 보험 온톨로지 시스템의 pgvector HNSW 인덱스 설정 및 튜닝 가이드입니다.

## 현재 설정

| 항목 | 값 |
|------|-----|
| pgvector 버전 | 0.8.1 |
| 벡터 차원 | 1536 (OpenAI text-embedding-3-small) |
| 인덱스 타입 | HNSW |
| 거리 함수 | cosine (vector_cosine_ops) |
| m | 16 |
| ef_construction | 64 |

## HNSW 파라미터 상세

### m (최대 연결 수)

각 노드가 가질 수 있는 최대 연결 수입니다.

| 값 | 장점 | 단점 | 권장 상황 |
|----|------|------|----------|
| 8-12 | 인덱스 작음, 빌드 빠름 | recall 낮음 | < 10,000건 |
| 16 | 균형 | - | 10,000-100,000건 |
| 24-32 | recall 높음 | 인덱스 큼, 빌드 느림 | > 100,000건 |
| 48+ | 최고 recall | 매우 느림 | 정확도 최우선 |

**현재 값**: 16 (134,844건 기준 적정)

### ef_construction (빌드 시 탐색 후보 수)

인덱스 빌드 시 각 노드 삽입할 때 탐색할 후보 수입니다.

| 값 | 인덱스 품질 | 빌드 시간 | 권장 |
|----|------------|----------|------|
| 32 | 낮음 | 빠름 | 테스트용 |
| 64 | 보통 | 보통 | 일반 |
| 100-128 | 좋음 | 느림 | 프로덕션 |
| 200+ | 최고 | 매우 느림 | 정확도 최우선 |

**권장**: m의 2-4배 (m=16이면 ef_construction=64-128)

**현재 값**: 64

### ef_search (검색 시 탐색 후보 수)

검색 쿼리 실행 시 탐색할 후보 수입니다. 세션별로 설정 가능합니다.

```sql
-- 기본값 40, 더 높은 정확도 원할 때
SET hnsw.ef_search = 100;
```

| 값 | recall | 검색 시간 | 권장 |
|----|--------|----------|------|
| 20 | ~90% | 빠름 | 속도 우선 |
| 40 | ~95% | 보통 | 기본값 |
| 100 | ~98% | 느림 | 정확도 우선 |
| 200+ | ~99% | 매우 느림 | 최고 정확도 |

## 거리 함수 선택

| 함수 | 연산자 | 용도 | 특징 |
|------|--------|------|------|
| `vector_cosine_ops` | `<=>` | 텍스트 임베딩 | **권장**, 방향 유사도 |
| `vector_l2_ops` | `<->` | 이미지 임베딩 | 거리 기반 |
| `vector_ip_ops` | `<#>` | 정규화된 벡터 | 내적 |

**현재 사용**: `vector_cosine_ops` (텍스트 임베딩에 적합)

## 데이터 규모별 권장 설정

| 데이터 규모 | m | ef_construction | ef_search | 예상 recall |
|------------|---|-----------------|-----------|-------------|
| < 10,000 | 12 | 64 | 40 | 95%+ |
| 10,000-100,000 | 16 | 64 | 60 | 95%+ |
| 100,000-1M | 24 | 100 | 100 | 95%+ |
| > 1M | 32 | 200 | 200 | 95%+ |

**현재 시스템** (134,844 clauses):
- 현재: m=16, ef_construction=64 ✓
- 권장 업그레이드: m=24, ef_construction=100

## 인덱스 관리

### 인덱스 생성

```sql
CREATE INDEX idx_clause_embedding_hnsw
ON clause_embedding
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### 인덱스 재구축 (대량 삽입 후)

```sql
-- 대량 데이터 삽입 후 인덱스 품질 저하 가능
-- maintenance_work_mem 충분히 설정 후 재구축

SET maintenance_work_mem = '1GB';
REINDEX INDEX idx_clause_embedding_hnsw;
ANALYZE clause_embedding;
```

### 인덱스 삭제 후 재생성

```sql
-- 파라미터 변경 시 삭제 후 재생성 필요
DROP INDEX idx_clause_embedding_hnsw;

CREATE INDEX idx_clause_embedding_hnsw
ON clause_embedding
USING hnsw (embedding vector_cosine_ops)
WITH (m = 24, ef_construction = 100);
```

## 성능 모니터링

### 인덱스 크기 확인

```sql
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_indexes
WHERE tablename = 'clause_embedding';
```

### 검색 성능 테스트

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, embedding <=> '[0.1, 0.2, ...]'::vector as distance
FROM clause_embedding
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

### 인덱스 사용 확인

```sql
-- Index Scan using idx_clause_embedding_hnsw 가 나와야 함
EXPLAIN SELECT * FROM clause_embedding
ORDER BY embedding <=> '[...]'::vector
LIMIT 10;
```

## 트러블슈팅

### 인덱스가 사용되지 않는 경우

1. **LIMIT 없음**: HNSW는 LIMIT 절 필요
2. **통계 부족**: `ANALYZE clause_embedding;` 실행
3. **테이블 작음**: 작은 테이블은 Seq Scan이 더 빠를 수 있음

### 검색 결과가 부정확한 경우

1. ef_search 값 증가: `SET hnsw.ef_search = 200;`
2. 인덱스 재구축: `REINDEX INDEX idx_clause_embedding_hnsw;`
3. 파라미터 업그레이드 (m, ef_construction 증가)

### 인덱스 빌드가 느린 경우

```sql
-- 메모리 증가
SET maintenance_work_mem = '2GB';

-- 병렬 워커 사용 (PostgreSQL 15+)
SET max_parallel_maintenance_workers = 4;
```

## 참고 자료

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [HNSW 논문](https://arxiv.org/abs/1603.09320)
- [pgvector 튜닝 가이드](https://github.com/pgvector/pgvector#indexing)

---

**문서 버전**: 1.0
**최종 수정**: 2025-12-14
