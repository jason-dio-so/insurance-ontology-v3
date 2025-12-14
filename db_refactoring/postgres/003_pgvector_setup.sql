-- ============================================================================
-- pgvector 설정 및 벡터 검색 인덱스
-- ============================================================================
-- 버전: 1.0
-- 생성일: 2025-12-14
-- 설명: pgvector 확장, 임베딩 테이블, HNSW 인덱스 설정
-- 용도: 독립 실행 가능한 pgvector 설정 파일
-- ============================================================================

-- ============================================================================
-- 1. pgvector 확장 설치
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

COMMENT ON EXTENSION vector IS 'vector 데이터 타입 및 ivfflat, hnsw 액세스 방법';

-- ============================================================================
-- 2. 임베딩 테이블 (clause_embedding)
-- ============================================================================
--
-- 주의: 001_initial_schema.sql에 이미 정의됨
-- 이 섹션은 독립 실행 시에만 사용
--
-- 현재 설정:
--   - 차원: 1536 (OpenAI text-embedding-3-small / ada-002)
--   - 대안: 384 (FastEmbed BGE-Small), 768 (BGE-Base), 3072 (text-embedding-3-large)
--

/*
CREATE TABLE IF NOT EXISTS public.clause_embedding (
    id integer NOT NULL,
    clause_id integer NOT NULL,
    embedding public.vector(1536),  -- 임베딩 모델에 따라 차원 조정
    model_name character varying(100),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),

    CONSTRAINT clause_embedding_pkey PRIMARY KEY (id),
    CONSTRAINT clause_embedding_clause_id_key UNIQUE (clause_id),
    CONSTRAINT clause_embedding_clause_id_fkey
        FOREIGN KEY (clause_id) REFERENCES public.document_clause(id) ON DELETE CASCADE
);

CREATE SEQUENCE IF NOT EXISTS public.clause_embedding_id_seq
    AS integer START WITH 1 INCREMENT BY 1;

ALTER TABLE public.clause_embedding
    ALTER COLUMN id SET DEFAULT nextval('public.clause_embedding_id_seq'::regclass);
*/

-- ============================================================================
-- 3. HNSW 인덱스 설정
-- ============================================================================
--
-- HNSW (Hierarchical Navigable Small World) 파라미터:
--
-- m (기본값: 16)
--   - 각 노드의 최대 연결 수
--   - 높을수록: 검색 정확도 ↑, 인덱스 크기 ↑, 빌드 시간 ↑
--   - 권장: 12-48 (데이터 규모에 따라)
--
-- ef_construction (기본값: 64)
--   - 인덱스 빌드 시 탐색 후보 수
--   - 높을수록: 인덱스 품질 ↑, 빌드 시간 ↑
--   - 권장: 64-200 (m의 2-4배)
--
-- 거리 함수 (vector_cosine_ops):
--   - vector_cosine_ops: 코사인 유사도 (텍스트 임베딩 권장)
--   - vector_l2_ops: 유클리드 거리
--   - vector_ip_ops: 내적 (정규화된 벡터용)
--

-- 기존 인덱스 삭제 (재생성 시)
-- DROP INDEX IF EXISTS idx_clause_embedding_hnsw;

-- HNSW 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_clause_embedding_hnsw
ON public.clause_embedding
USING hnsw (embedding public.vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

COMMENT ON INDEX idx_clause_embedding_hnsw IS
'HNSW 벡터 검색 인덱스 (m=16, ef_construction=64, cosine similarity)';

-- ============================================================================
-- 4. 보조 인덱스
-- ============================================================================

-- clause_id 조회용
CREATE INDEX IF NOT EXISTS idx_clause_embedding_clause
ON public.clause_embedding USING btree (clause_id);

-- metadata JSONB 검색용 (필터링된 벡터 검색)
CREATE INDEX IF NOT EXISTS idx_clause_embedding_metadata_gin
ON public.clause_embedding USING gin (metadata);

-- ============================================================================
-- 5. 검색 시 ef_search 설정
-- ============================================================================
--
-- ef_search: 검색 시 탐색 후보 수
--   - 기본값: 40
--   - 높을수록: 정확도 ↑, 검색 시간 ↑
--   - 세션별 설정 가능
--
-- 사용 예:
--   SET hnsw.ef_search = 100;
--   SELECT * FROM clause_embedding
--   ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
--   LIMIT 10;

-- ============================================================================
-- 6. 데이터 규모별 권장 파라미터
-- ============================================================================
--
-- | 데이터 규모    | m   | ef_construction | ef_search | 예상 recall |
-- |---------------|-----|-----------------|-----------|-------------|
-- | < 10,000      | 12  | 64              | 40        | 95%+        |
-- | 10,000-100,000| 16  | 64              | 60        | 95%+        |
-- | 100,000-1M    | 24  | 100             | 100       | 95%+        |
-- | > 1M          | 32  | 200             | 200       | 95%+        |
--
-- 현재 설정 (134,844 clauses 기준):
--   m = 16, ef_construction = 64 (적정)
--   필요시 m = 24, ef_construction = 100으로 업그레이드 권장

-- ============================================================================
-- 7. 유틸리티 함수
-- ============================================================================

-- 벡터 검색 함수 (편의용)
CREATE OR REPLACE FUNCTION public.search_similar_clauses(
    query_embedding vector(1536),
    match_count integer DEFAULT 10,
    similarity_threshold float DEFAULT 0.7
)
RETURNS TABLE (
    clause_id integer,
    similarity float,
    clause_text text,
    document_id integer
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ce.clause_id,
        1 - (ce.embedding <=> query_embedding) as similarity,
        dc.clause_text,
        dc.document_id
    FROM clause_embedding ce
    JOIN document_clause dc ON dc.id = ce.clause_id
    WHERE 1 - (ce.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY ce.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.search_similar_clauses IS
'벡터 유사도 검색 함수: query_embedding과 유사한 조항 검색';

-- 인덱스 통계 조회 함수
CREATE OR REPLACE FUNCTION public.get_vector_index_stats()
RETURNS TABLE (
    index_name text,
    table_name text,
    index_size text,
    index_type text
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.indexname::text,
        i.tablename::text,
        pg_size_pretty(pg_relation_size(i.indexrelid))::text as index_size,
        am.amname::text as index_type
    FROM pg_indexes i
    JOIN pg_class c ON c.relname = i.indexname
    JOIN pg_am am ON am.oid = c.relam
    WHERE i.tablename = 'clause_embedding'
    ORDER BY pg_relation_size(i.indexrelid) DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.get_vector_index_stats IS
'clause_embedding 테이블의 인덱스 통계 조회';

-- ============================================================================
-- 8. 인덱스 재구축 (대량 삽입 후)
-- ============================================================================
--
-- 대량 임베딩 삽입 후 인덱스 재구축 권장:
--
-- REINDEX INDEX idx_clause_embedding_hnsw;
-- ANALYZE clause_embedding;
--
-- 또는 maintenance_work_mem 증가 후 재구축:
--
-- SET maintenance_work_mem = '1GB';
-- REINDEX INDEX idx_clause_embedding_hnsw;

-- ============================================================================
-- 끝
-- ============================================================================
