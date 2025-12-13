-- ============================================================================
-- 보험 온톨로지 데이터베이스 스키마
-- 버전: 1.0
-- 생성일: 2025-12-13
-- 설명: 보험 상품 온톨로지 시스템용 PostgreSQL 스키마
-- ============================================================================

-- 원본 DB 버전: PostgreSQL 16.11 (Debian 16.11-1.pgdg12+1)
-- pg_dump 버전: 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
-- SET transaction_timeout = 0;  -- PostgreSQL 16+ only
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- ============================================================================
-- 확장 (EXTENSIONS)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

COMMENT ON EXTENSION vector IS 'vector 데이터 타입 및 ivfflat, hnsw 액세스 방법';

-- ============================================================================
-- 함수 (FUNCTIONS)
-- ============================================================================

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

SET default_tablespace = '';
SET default_table_access_method = heap;

-- ============================================================================
-- 테이블 (TABLES)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. company (보험사 마스터)
-- ----------------------------------------------------------------------------

CREATE TABLE public.company (
    id integer NOT NULL,
    company_code character varying(20) NOT NULL,
    company_name character varying(100) NOT NULL,
    business_type character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.company IS '보험사 마스터';
COMMENT ON COLUMN public.company.company_code IS '회사 코드 (samsung, db, lotte, kb, hyundai, hanwha, heungkuk, meritz)';
COMMENT ON COLUMN public.company.business_type IS '사업 유형 (손해보험, 생명보험)';

CREATE SEQUENCE public.company_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.company_id_seq OWNED BY public.company.id;

-- ----------------------------------------------------------------------------
-- 2. product (보험 상품 마스터)
-- ----------------------------------------------------------------------------

CREATE TABLE public.product (
    id integer NOT NULL,
    company_id integer NOT NULL,
    product_code character varying(50) NOT NULL,
    product_name character varying(200) NOT NULL,
    business_type character varying(50),
    version character varying(20),
    effective_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.product IS '보험 상품 마스터';
COMMENT ON COLUMN public.product.product_code IS '상품 코드';
COMMENT ON COLUMN public.product.business_type IS '상품 유형 (장기손해, 장기상해 등)';
COMMENT ON COLUMN public.product.version IS '상품 버전';
COMMENT ON COLUMN public.product.effective_date IS '적용 시작일';

CREATE SEQUENCE public.product_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.product_id_seq OWNED BY public.product.id;

-- ----------------------------------------------------------------------------
-- 3. product_variant (상품 변형)
-- ----------------------------------------------------------------------------

CREATE TABLE public.product_variant (
    id integer NOT NULL,
    product_id integer NOT NULL,
    variant_name character varying(100),
    variant_code character varying(50),
    target_gender character varying(10),
    target_age_range character varying(20),
    min_age integer,
    max_age integer,
    attributes jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.product_variant IS '상품 변형 (성별/연령 분리, 1형/2형, 1종/3종/4종 등)';
COMMENT ON COLUMN public.product_variant.variant_name IS '변형명 (예: 남성용, 여성용, 40세이하)';
COMMENT ON COLUMN public.product_variant.variant_code IS '변형 코드 (예: male, female, age_40_under)';
COMMENT ON COLUMN public.product_variant.target_gender IS '대상 성별 (male, female, NULL)';
COMMENT ON COLUMN public.product_variant.target_age_range IS '대상 연령대 (≤40, ≥41, 30-39, NULL)';
COMMENT ON COLUMN public.product_variant.attributes IS '추가 속성 (JSONB): refund_type, jong_type 등';

CREATE SEQUENCE public.product_variant_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.product_variant_id_seq OWNED BY public.product_variant.id;

-- ----------------------------------------------------------------------------
-- 4. coverage_category (담보 카테고리)
-- ----------------------------------------------------------------------------

CREATE TABLE public.coverage_category (
    id integer NOT NULL,
    category_code character varying(50) NOT NULL,
    category_name_kr character varying(100) NOT NULL,
    category_name_en character varying(100),
    description text,
    display_order integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.coverage_category IS '담보 카테고리 (암진단군, 2대질병진단군 등)';
COMMENT ON COLUMN public.coverage_category.category_code IS '카테고리 코드 (cancer_diagnosis, major_disease 등)';
COMMENT ON COLUMN public.coverage_category.category_name_kr IS '카테고리명 (한글)';

CREATE SEQUENCE public.coverage_category_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.coverage_category_id_seq OWNED BY public.coverage_category.id;

-- ----------------------------------------------------------------------------
-- 5. coverage_group (특별약관군)
-- ----------------------------------------------------------------------------

CREATE TABLE public.coverage_group (
    id integer NOT NULL,
    company_id integer,
    category_id integer,
    group_number integer,
    group_code character varying(50) NOT NULL,
    group_name_kr character varying(200) NOT NULL,
    group_name_en character varying(200),
    is_renewable boolean DEFAULT false,
    version character varying(20),
    page_number integer,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.coverage_group IS '특별약관군 (무배당암 진단 보장 특별약관군 등)';
COMMENT ON COLUMN public.coverage_group.group_number IS '약관 목차 번호 (예: 4, 5, ...)';
COMMENT ON COLUMN public.coverage_group.group_code IS '약관군 코드';
COMMENT ON COLUMN public.coverage_group.is_renewable IS '갱신형 여부';

CREATE SEQUENCE public.coverage_group_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.coverage_group_id_seq OWNED BY public.coverage_group.id;

-- ----------------------------------------------------------------------------
-- 6. coverage (담보/특별약관)
-- ----------------------------------------------------------------------------

CREATE TABLE public.coverage (
    id integer NOT NULL,
    product_id integer NOT NULL,
    group_id integer,
    coverage_code character varying(200),
    coverage_name TEXT NOT NULL,
    coverage_category character varying(100),
    renewal_type character varying(20),
    is_basic boolean DEFAULT false,
    clause_number character varying(50),
    coverage_period character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    parent_coverage_id integer
);

COMMENT ON TABLE public.coverage IS '담보 (특별약관 단위)';
COMMENT ON COLUMN public.coverage.group_id IS '소속 특별약관군';
COMMENT ON COLUMN public.coverage.renewal_type IS '갱신형, 비갱신형';
COMMENT ON COLUMN public.coverage.is_basic IS '기본형 담보 여부';
COMMENT ON COLUMN public.coverage.clause_number IS '조항 번호 (예: 119, 121) - coverage_name 오염 방지용';
COMMENT ON COLUMN public.coverage.coverage_period IS '기간 정보 (예: 10년, 15년) - coverage_name 오염 방지용';

CREATE SEQUENCE public.coverage_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.coverage_id_seq OWNED BY public.coverage.id;

-- ----------------------------------------------------------------------------
-- 7. benefit (담보별 보장 급부)
-- ----------------------------------------------------------------------------

CREATE TABLE public.benefit (
    id integer NOT NULL,
    coverage_id integer NOT NULL,
    benefit_name character varying(200) NOT NULL,
    benefit_type character varying(200),
    benefit_amount_text text,
    benefit_amount numeric(15,2),
    payment_frequency character varying(50),
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.benefit IS '담보별 보장 급부';
COMMENT ON COLUMN public.benefit.benefit_type IS '급부 타입 (진단금, 수술비, 입원일당 등)';
COMMENT ON COLUMN public.benefit.payment_frequency IS '지급 빈도 (1회, 연 1회, 진단시 1회 등)';

CREATE SEQUENCE public.benefit_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.benefit_id_seq OWNED BY public.benefit.id;

-- ----------------------------------------------------------------------------
-- 8. condition (담보별 보장 조건)
-- ----------------------------------------------------------------------------

CREATE TABLE public.condition (
    id integer NOT NULL,
    coverage_id integer NOT NULL,
    condition_type character varying(50),
    condition_text text NOT NULL,
    min_age integer,
    max_age integer,
    waiting_period_days integer,
    attributes jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.condition IS '담보별 보장 조건';
COMMENT ON COLUMN public.condition.condition_type IS '조건 타입 (diagnosis, age, waiting_period 등)';
COMMENT ON COLUMN public.condition.waiting_period_days IS '면책/감액 기간 (일)';

CREATE SEQUENCE public.condition_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.condition_id_seq OWNED BY public.condition.id;

-- ----------------------------------------------------------------------------
-- 9. exclusion (담보별 보장 제외 사항)
-- ----------------------------------------------------------------------------

CREATE TABLE public.exclusion (
    id integer NOT NULL,
    coverage_id integer NOT NULL,
    exclusion_type character varying(50),
    exclusion_text text NOT NULL,
    is_absolute boolean DEFAULT true,
    attributes jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.exclusion IS '담보별 보장 제외 사항';
COMMENT ON COLUMN public.exclusion.exclusion_type IS '제외 타입 (disease, cause, situation 등)';
COMMENT ON COLUMN public.exclusion.is_absolute IS '절대적 제외 여부';

CREATE SEQUENCE public.exclusion_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.exclusion_id_seq OWNED BY public.exclusion.id;

-- ----------------------------------------------------------------------------
-- 10. disease_code_set (질병코드 집합)
-- ----------------------------------------------------------------------------

CREATE TABLE public.disease_code_set (
    id integer NOT NULL,
    set_name character varying(100) NOT NULL,
    description text,
    version character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.disease_code_set IS '질병코드 집합 (암, 뇌출혈, 급성심근경색 등)';

CREATE SEQUENCE public.disease_code_set_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.disease_code_set_id_seq OWNED BY public.disease_code_set.id;

-- ----------------------------------------------------------------------------
-- 11. disease_code (질병코드)
-- ----------------------------------------------------------------------------

CREATE TABLE public.disease_code (
    id integer NOT NULL,
    code_set_id integer NOT NULL,
    code character varying(20) NOT NULL,
    code_type character varying(10),
    description_kr character varying(500),
    description_en character varying(500),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.disease_code IS '질병코드 (KCD, ICD)';
COMMENT ON COLUMN public.disease_code.code_type IS '코드 체계 (KCD, ICD)';

CREATE SEQUENCE public.disease_code_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.disease_code_id_seq OWNED BY public.disease_code.id;

-- ----------------------------------------------------------------------------
-- 12. document (약관/사업방법서/상품요약서 문서)
-- ----------------------------------------------------------------------------

CREATE TABLE public.document (
    id integer NOT NULL,
    document_id character varying(100) NOT NULL,
    company_id integer,
    product_id integer,
    variant_id integer,
    doc_type character varying(50),
    doc_subtype character varying(50),
    version character varying(50),
    file_path character varying(500),
    total_pages integer,
    attributes jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);

COMMENT ON TABLE public.document IS '약관, 사업방법서, 상품요약서, 가입설계서 문서';
COMMENT ON COLUMN public.document.document_id IS '문서 고유 ID (예: samsung-myhealthpartner-terms-v1-20250901)';
COMMENT ON COLUMN public.document.variant_id IS '연결된 상품 변형 ID (롯데 성별/DB 연령 분리)';
COMMENT ON COLUMN public.document.doc_type IS '문서 타입 (terms, business_spec, product_summary, proposal, easy_summary)';
COMMENT ON COLUMN public.document.doc_subtype IS '문서 서브타입 (male, female, age_40_under, age_41_over 등)';
COMMENT ON COLUMN public.document.attributes IS '추가 메타데이터 (JSONB)';

CREATE SEQUENCE public.document_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.document_id_seq OWNED BY public.document.id;

-- ----------------------------------------------------------------------------
-- 13. document_clause (문서 조항/청크)
-- ----------------------------------------------------------------------------

CREATE TABLE public.document_clause (
    id integer NOT NULL,
    document_id integer NOT NULL,
    clause_number character varying(50),
    clause_title character varying(500),
    clause_text text NOT NULL,
    clause_type character varying(50),
    structured_data jsonb,
    section_type character varying(100),
    page_number integer,
    hierarchy_level integer DEFAULT 0,
    parent_clause_id integer,
    attributes jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);

COMMENT ON TABLE public.document_clause IS '문서 조항/청크 (제n조 단위 + 테이블 행)';
COMMENT ON COLUMN public.document_clause.clause_type IS 'v2: 조항 타입 (table_row, text_block, list_item, heading, article)';
COMMENT ON COLUMN public.document_clause.structured_data IS 'v2: 구조화 데이터 {coverage_name, coverage_amount, premium, target_gender, target_age_range, ...}';
COMMENT ON COLUMN public.document_clause.section_type IS '섹션 타입 (보통약관, 특별약관, 별표 등)';

CREATE SEQUENCE public.document_clause_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.document_clause_id_seq OWNED BY public.document_clause.id;

-- ----------------------------------------------------------------------------
-- 14. clause_coverage (조항-담보 M:N 매핑)
-- ----------------------------------------------------------------------------

CREATE TABLE public.clause_coverage (
    id integer NOT NULL,
    clause_id integer NOT NULL,
    coverage_id integer NOT NULL,
    relevance_score double precision DEFAULT 1.0,
    extraction_method character varying(50),
    created_at timestamp without time zone DEFAULT now()
);

COMMENT ON TABLE public.clause_coverage IS 'v2: 조항-담보 M:N 매핑 (필터링된 벡터 검색용)';
COMMENT ON COLUMN public.clause_coverage.relevance_score IS '관련도 점수 (0.0~1.0)';
COMMENT ON COLUMN public.clause_coverage.extraction_method IS '추출 방법 (exact_match, fuzzy_match, llm)';

CREATE SEQUENCE public.clause_coverage_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.clause_coverage_id_seq OWNED BY public.clause_coverage.id;

-- ----------------------------------------------------------------------------
-- 15. clause_embedding (조항 벡터 임베딩)
-- ----------------------------------------------------------------------------

CREATE TABLE public.clause_embedding (
    id integer NOT NULL,
    clause_id integer NOT NULL,
    embedding public.vector(1536),
    model_name character varying(100),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);

COMMENT ON TABLE public.clause_embedding IS 'v2: 조항 벡터 임베딩 (FastEmbed BGE-Small 384d)';
COMMENT ON COLUMN public.clause_embedding.embedding IS '벡터 임베딩 (384차원)';
COMMENT ON COLUMN public.clause_embedding.metadata IS 'v2: 검색 필터용 메타데이터 {coverage_ids, clause_type, doc_type, ...}';

CREATE SEQUENCE public.clause_embedding_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.clause_embedding_id_seq OWNED BY public.clause_embedding.id;

-- ============================================================================
-- 뷰 (VIEWS)
-- ============================================================================

CREATE VIEW public.document_stats AS
 SELECT d.doc_type,
    d.doc_subtype,
    count(DISTINCT d.id) AS total_documents,
    count(dc.id) AS total_clauses,
    count(
        CASE
            WHEN ((dc.clause_type)::text = 'table_row'::text) THEN 1
            ELSE NULL::integer
        END) AS table_row_clauses,
    count(
        CASE
            WHEN ((dc.clause_type)::text = 'text_block'::text) THEN 1
            ELSE NULL::integer
        END) AS text_block_clauses,
    count(
        CASE
            WHEN (dc.structured_data IS NOT NULL) THEN 1
            ELSE NULL::integer
        END) AS structured_clauses,
    avg(d.total_pages) AS avg_pages
   FROM (public.document d
     LEFT JOIN public.document_clause dc ON ((d.id = dc.document_id)))
  GROUP BY d.doc_type, d.doc_subtype;

COMMENT ON VIEW public.document_stats IS 'v2: 문서 통계 (타입별 문서/조항 수, clause_type 분포)';

-- ============================================================================
-- 기본값 설정 (시퀀스 연결)
-- ============================================================================

ALTER TABLE ONLY public.benefit ALTER COLUMN id SET DEFAULT nextval('public.benefit_id_seq'::regclass);
ALTER TABLE ONLY public.clause_coverage ALTER COLUMN id SET DEFAULT nextval('public.clause_coverage_id_seq'::regclass);
ALTER TABLE ONLY public.clause_embedding ALTER COLUMN id SET DEFAULT nextval('public.clause_embedding_id_seq'::regclass);
ALTER TABLE ONLY public.company ALTER COLUMN id SET DEFAULT nextval('public.company_id_seq'::regclass);
ALTER TABLE ONLY public.condition ALTER COLUMN id SET DEFAULT nextval('public.condition_id_seq'::regclass);
ALTER TABLE ONLY public.coverage ALTER COLUMN id SET DEFAULT nextval('public.coverage_id_seq'::regclass);
ALTER TABLE ONLY public.coverage_category ALTER COLUMN id SET DEFAULT nextval('public.coverage_category_id_seq'::regclass);
ALTER TABLE ONLY public.coverage_group ALTER COLUMN id SET DEFAULT nextval('public.coverage_group_id_seq'::regclass);
ALTER TABLE ONLY public.disease_code ALTER COLUMN id SET DEFAULT nextval('public.disease_code_id_seq'::regclass);
ALTER TABLE ONLY public.disease_code_set ALTER COLUMN id SET DEFAULT nextval('public.disease_code_set_id_seq'::regclass);
ALTER TABLE ONLY public.document ALTER COLUMN id SET DEFAULT nextval('public.document_id_seq'::regclass);
ALTER TABLE ONLY public.document_clause ALTER COLUMN id SET DEFAULT nextval('public.document_clause_id_seq'::regclass);
ALTER TABLE ONLY public.exclusion ALTER COLUMN id SET DEFAULT nextval('public.exclusion_id_seq'::regclass);
ALTER TABLE ONLY public.product ALTER COLUMN id SET DEFAULT nextval('public.product_id_seq'::regclass);
ALTER TABLE ONLY public.product_variant ALTER COLUMN id SET DEFAULT nextval('public.product_variant_id_seq'::regclass);

-- ============================================================================
-- 기본키 제약조건 (PRIMARY KEY)
-- ============================================================================

ALTER TABLE ONLY public.benefit ADD CONSTRAINT benefit_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.clause_coverage ADD CONSTRAINT clause_coverage_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.clause_embedding ADD CONSTRAINT clause_embedding_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.company ADD CONSTRAINT company_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.condition ADD CONSTRAINT condition_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.coverage ADD CONSTRAINT coverage_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.coverage_category ADD CONSTRAINT coverage_category_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.coverage_group ADD CONSTRAINT coverage_group_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.disease_code ADD CONSTRAINT disease_code_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.disease_code_set ADD CONSTRAINT disease_code_set_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.document ADD CONSTRAINT document_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.document_clause ADD CONSTRAINT document_clause_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.exclusion ADD CONSTRAINT exclusion_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.product ADD CONSTRAINT product_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.product_variant ADD CONSTRAINT product_variant_pkey PRIMARY KEY (id);

-- ============================================================================
-- 유니크 제약조건 (UNIQUE)
-- ============================================================================

ALTER TABLE ONLY public.clause_coverage ADD CONSTRAINT clause_coverage_clause_id_coverage_id_key UNIQUE (clause_id, coverage_id);
ALTER TABLE ONLY public.clause_embedding ADD CONSTRAINT clause_embedding_clause_id_key UNIQUE (clause_id);
ALTER TABLE ONLY public.company ADD CONSTRAINT company_company_code_key UNIQUE (company_code);
ALTER TABLE ONLY public.coverage ADD CONSTRAINT coverage_product_id_coverage_code_key UNIQUE (product_id, coverage_code);
ALTER TABLE ONLY public.coverage_category ADD CONSTRAINT coverage_category_category_code_key UNIQUE (category_code);
ALTER TABLE ONLY public.coverage_group ADD CONSTRAINT coverage_group_company_id_group_code_version_key UNIQUE (company_id, group_code, version);
ALTER TABLE ONLY public.disease_code ADD CONSTRAINT disease_code_code_set_id_code_key UNIQUE (code_set_id, code);
ALTER TABLE ONLY public.disease_code_set ADD CONSTRAINT disease_code_set_set_name_key UNIQUE (set_name);
ALTER TABLE ONLY public.document ADD CONSTRAINT document_document_id_key UNIQUE (document_id);
ALTER TABLE ONLY public.product ADD CONSTRAINT product_company_id_product_code_version_key UNIQUE (company_id, product_code, version);
ALTER TABLE ONLY public.product_variant ADD CONSTRAINT product_variant_product_id_variant_code_key UNIQUE (product_id, variant_code);

-- ============================================================================
-- 인덱스 (INDEXES)
-- ============================================================================

-- clause_coverage 인덱스
CREATE INDEX idx_clause_coverage_clause ON public.clause_coverage USING btree (clause_id);
CREATE INDEX idx_clause_coverage_coverage ON public.clause_coverage USING btree (coverage_id);

-- clause_embedding 인덱스 (벡터 검색용 HNSW 포함)
CREATE INDEX idx_clause_embedding_clause ON public.clause_embedding USING btree (clause_id);
CREATE INDEX idx_clause_embedding_hnsw ON public.clause_embedding USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');
CREATE INDEX idx_clause_embedding_metadata_gin ON public.clause_embedding USING gin (metadata);

-- document_clause 인덱스
CREATE INDEX idx_clause_document ON public.document_clause USING btree (document_id);
CREATE INDEX idx_clause_parent ON public.document_clause USING btree (parent_clause_id);
CREATE INDEX idx_clause_section ON public.document_clause USING btree (section_type);
CREATE INDEX idx_clause_type ON public.document_clause USING btree (clause_type);
CREATE INDEX idx_structured_coverage_amount ON public.document_clause USING btree (((structured_data ->> 'coverage_amount'::text))) WHERE (structured_data IS NOT NULL);
CREATE INDEX idx_structured_data_gin ON public.document_clause USING gin (structured_data) WHERE (structured_data IS NOT NULL);
CREATE INDEX idx_structured_premium ON public.document_clause USING btree (((structured_data ->> 'premium'::text))) WHERE (structured_data IS NOT NULL);

-- company 인덱스
CREATE INDEX idx_company_code ON public.company USING btree (company_code);

-- coverage 인덱스
CREATE INDEX idx_coverage_group ON public.coverage USING btree (group_id);
CREATE INDEX idx_coverage_name ON public.coverage USING btree (coverage_name);
CREATE INDEX idx_coverage_parent ON public.coverage USING btree (parent_coverage_id);
CREATE INDEX idx_coverage_product ON public.coverage USING btree (product_id);

-- document 인덱스
CREATE INDEX idx_document_company ON public.document USING btree (company_id);
CREATE INDEX idx_document_product ON public.document USING btree (product_id);
CREATE INDEX idx_document_type ON public.document USING btree (doc_type);
CREATE INDEX idx_document_variant ON public.document USING btree (variant_id);

-- product 인덱스
CREATE INDEX idx_product_code ON public.product USING btree (product_code);
CREATE INDEX idx_product_company ON public.product USING btree (company_id);

-- product_variant 인덱스
CREATE INDEX idx_variant_age_range ON public.product_variant USING btree (target_age_range);
CREATE INDEX idx_variant_gender ON public.product_variant USING btree (target_gender);
CREATE INDEX idx_variant_product ON public.product_variant USING btree (product_id);

-- ============================================================================
-- 트리거 (TRIGGERS)
-- ============================================================================

CREATE TRIGGER update_company_updated_at BEFORE UPDATE ON public.company FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_coverage_category_updated_at BEFORE UPDATE ON public.coverage_category FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_coverage_group_updated_at BEFORE UPDATE ON public.coverage_group FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_coverage_updated_at BEFORE UPDATE ON public.coverage FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_product_updated_at BEFORE UPDATE ON public.product FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_product_variant_updated_at BEFORE UPDATE ON public.product_variant FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- 외래키 제약조건 (FOREIGN KEYS)
-- ============================================================================

-- benefit 외래키
ALTER TABLE ONLY public.benefit ADD CONSTRAINT benefit_coverage_id_fkey FOREIGN KEY (coverage_id) REFERENCES public.coverage(id);

-- clause_coverage 외래키
ALTER TABLE ONLY public.clause_coverage ADD CONSTRAINT clause_coverage_clause_id_fkey FOREIGN KEY (clause_id) REFERENCES public.document_clause(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.clause_coverage ADD CONSTRAINT clause_coverage_coverage_id_fkey FOREIGN KEY (coverage_id) REFERENCES public.coverage(id) ON DELETE CASCADE;

-- clause_embedding 외래키
ALTER TABLE ONLY public.clause_embedding ADD CONSTRAINT clause_embedding_clause_id_fkey FOREIGN KEY (clause_id) REFERENCES public.document_clause(id) ON DELETE CASCADE;

-- condition 외래키
ALTER TABLE ONLY public.condition ADD CONSTRAINT condition_coverage_id_fkey FOREIGN KEY (coverage_id) REFERENCES public.coverage(id);

-- coverage 외래키
ALTER TABLE ONLY public.coverage ADD CONSTRAINT coverage_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.coverage_group(id);
ALTER TABLE ONLY public.coverage ADD CONSTRAINT coverage_parent_coverage_id_fkey FOREIGN KEY (parent_coverage_id) REFERENCES public.coverage(id);
ALTER TABLE ONLY public.coverage ADD CONSTRAINT coverage_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id);

-- coverage_group 외래키
ALTER TABLE ONLY public.coverage_group ADD CONSTRAINT coverage_group_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.coverage_category(id);
ALTER TABLE ONLY public.coverage_group ADD CONSTRAINT coverage_group_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.company(id);

-- disease_code 외래키
ALTER TABLE ONLY public.disease_code ADD CONSTRAINT disease_code_code_set_id_fkey FOREIGN KEY (code_set_id) REFERENCES public.disease_code_set(id);

-- document 외래키
ALTER TABLE ONLY public.document ADD CONSTRAINT document_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.company(id);
ALTER TABLE ONLY public.document ADD CONSTRAINT document_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id);
ALTER TABLE ONLY public.document ADD CONSTRAINT document_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.product_variant(id);

-- document_clause 외래키
ALTER TABLE ONLY public.document_clause ADD CONSTRAINT document_clause_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.document_clause ADD CONSTRAINT document_clause_parent_clause_id_fkey FOREIGN KEY (parent_clause_id) REFERENCES public.document_clause(id);

-- exclusion 외래키
ALTER TABLE ONLY public.exclusion ADD CONSTRAINT exclusion_coverage_id_fkey FOREIGN KEY (coverage_id) REFERENCES public.coverage(id);

-- product 외래키
ALTER TABLE ONLY public.product ADD CONSTRAINT product_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.company(id);

-- product_variant 외래키
ALTER TABLE ONLY public.product_variant ADD CONSTRAINT product_variant_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id);

-- ============================================================================
-- 스키마 끝
-- ============================================================================
