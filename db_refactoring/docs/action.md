# 001_initial_schema.sql 테이블 추가 작업 보고서

## 작업 대상 파일

| 파일 | 경로 | 작업 내용 |
|------|------|----------|
| **001_initial_schema.sql** | `db_refactoring/postgres/001_initial_schema.sql` | 4개 테이블 및 관련 객체 추가 |
| **ER_DIAGRAM.md** | `db_refactoring/docs/ER_DIAGRAM.md` | 4개 테이블 다이어그램 추가 |
| **verify_schema.py** | `db_refactoring/scripts/verify_schema.py` | 변경 불필요 (이미 19개 테이블 기대) |

---

## 1. 001_initial_schema.sql 수정

### 1.1 테이블 정의 추가 (Line 435 이후, clause_embedding 다음)

```sql
-- ----------------------------------------------------------------------------
-- 16. risk_event (위험 이벤트)
-- ----------------------------------------------------------------------------

CREATE TABLE public.risk_event (
    id integer NOT NULL,
    event_type character varying(50),
    event_name character varying(200) NOT NULL,
    severity_level integer,
    icd_code_pattern character varying(100),
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.risk_event IS '위험 이벤트 (진단, 수술, 입원, 사망 등)';
COMMENT ON COLUMN public.risk_event.event_type IS '이벤트 타입 (diagnosis, surgery, hospitalization, death)';
COMMENT ON COLUMN public.risk_event.severity_level IS '심각도 (1-5)';
COMMENT ON COLUMN public.risk_event.icd_code_pattern IS 'ICD/KCD 코드 패턴';

CREATE SEQUENCE public.risk_event_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.risk_event_id_seq OWNED BY public.risk_event.id;

-- ----------------------------------------------------------------------------
-- 17. benefit_risk_event (급부-위험이벤트 M:N 매핑)
-- ----------------------------------------------------------------------------

CREATE TABLE public.benefit_risk_event (
    id integer NOT NULL,
    benefit_id integer NOT NULL,
    risk_event_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.benefit_risk_event IS '급부-위험이벤트 M:N 매핑';

CREATE SEQUENCE public.benefit_risk_event_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.benefit_risk_event_id_seq OWNED BY public.benefit_risk_event.id;

-- ----------------------------------------------------------------------------
-- 18. plan (가입설계)
-- ----------------------------------------------------------------------------

CREATE TABLE public.plan (
    id integer NOT NULL,
    document_id integer,
    product_id integer,
    variant_id integer,
    plan_name character varying(200),
    target_gender character varying(10),
    target_age integer,
    insurance_period character varying(50),
    payment_period character varying(50),
    payment_cycle character varying(20),
    total_premium numeric(15,2),
    attributes jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.plan IS '가입설계서 (상품요약서에서 추출)';
COMMENT ON COLUMN public.plan.target_gender IS '대상 성별 (male, female)';
COMMENT ON COLUMN public.plan.target_age IS '대상 연령';
COMMENT ON COLUMN public.plan.insurance_period IS '보험기간 (예: 100세만기)';
COMMENT ON COLUMN public.plan.payment_period IS '납입기간 (예: 20년납)';
COMMENT ON COLUMN public.plan.payment_cycle IS '납입주기 (월납, 연납)';

CREATE SEQUENCE public.plan_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.plan_id_seq OWNED BY public.plan.id;

-- ----------------------------------------------------------------------------
-- 19. plan_coverage (가입설계-담보 연결)
-- ----------------------------------------------------------------------------

CREATE TABLE public.plan_coverage (
    id integer NOT NULL,
    plan_id integer NOT NULL,
    coverage_id integer NOT NULL,
    sum_insured numeric(15,2),
    sum_insured_text character varying(100),
    premium numeric(15,2),
    is_basic boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.plan_coverage IS '가입설계-담보 연결 (가입금액, 보험료 포함)';
COMMENT ON COLUMN public.plan_coverage.sum_insured IS '가입금액';
COMMENT ON COLUMN public.plan_coverage.sum_insured_text IS '가입금액 텍스트 (예: 1,000만원)';
COMMENT ON COLUMN public.plan_coverage.premium IS '보험료';
COMMENT ON COLUMN public.plan_coverage.is_basic IS '기본 담보 여부';

CREATE SEQUENCE public.plan_coverage_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

ALTER SEQUENCE public.plan_coverage_id_seq OWNED BY public.plan_coverage.id;
```

---

### 1.2 기본값 설정 추가 (Line 486 근처, 기존 ALTER TABLE 섹션)

```sql
ALTER TABLE ONLY public.risk_event ALTER COLUMN id SET DEFAULT nextval('public.risk_event_id_seq'::regclass);
ALTER TABLE ONLY public.benefit_risk_event ALTER COLUMN id SET DEFAULT nextval('public.benefit_risk_event_id_seq'::regclass);
ALTER TABLE ONLY public.plan ALTER COLUMN id SET DEFAULT nextval('public.plan_id_seq'::regclass);
ALTER TABLE ONLY public.plan_coverage ALTER COLUMN id SET DEFAULT nextval('public.plan_coverage_id_seq'::regclass);
```

---

### 1.3 기본키 제약조건 추가 (Line 506 근처, PRIMARY KEY 섹션)

```sql
ALTER TABLE ONLY public.risk_event ADD CONSTRAINT risk_event_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.benefit_risk_event ADD CONSTRAINT benefit_risk_event_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.plan ADD CONSTRAINT plan_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.plan_coverage ADD CONSTRAINT plan_coverage_pkey PRIMARY KEY (id);
```

---

### 1.4 유니크 제약조건 추가 (Line 522 근처, UNIQUE 섹션)

```sql
ALTER TABLE ONLY public.benefit_risk_event ADD CONSTRAINT benefit_risk_event_benefit_id_risk_event_id_key UNIQUE (benefit_id, risk_event_id);
ALTER TABLE ONLY public.plan_coverage ADD CONSTRAINT plan_coverage_plan_id_coverage_id_key UNIQUE (plan_id, coverage_id);
```

---

### 1.5 인덱스 추가 (Line 568 근처, INDEXES 섹션)

```sql
-- risk_event 인덱스
CREATE INDEX idx_risk_event_event_type ON public.risk_event USING btree (event_type);
CREATE INDEX idx_risk_event_event_name ON public.risk_event USING btree (event_name);

-- benefit_risk_event 인덱스
CREATE INDEX idx_benefit_risk_event_benefit ON public.benefit_risk_event USING btree (benefit_id);
CREATE INDEX idx_benefit_risk_event_risk_event ON public.benefit_risk_event USING btree (risk_event_id);

-- plan 인덱스
CREATE INDEX idx_plan_product ON public.plan USING btree (product_id);
CREATE INDEX idx_plan_document ON public.plan USING btree (document_id);

-- plan_coverage 인덱스
CREATE INDEX idx_plan_coverage_plan ON public.plan_coverage USING btree (plan_id);
CREATE INDEX idx_plan_coverage_coverage ON public.plan_coverage USING btree (coverage_id);
```

---

### 1.6 트리거 추가 (Line 583 근처, TRIGGERS 섹션)

```sql
CREATE TRIGGER update_risk_event_updated_at BEFORE UPDATE ON public.risk_event FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_plan_updated_at BEFORE UPDATE ON public.plan FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
```

---

### 1.7 외래키 제약조건 추가 (Line 630 근처, FOREIGN KEYS 섹션 끝)

```sql
-- benefit_risk_event 외래키
ALTER TABLE ONLY public.benefit_risk_event ADD CONSTRAINT benefit_risk_event_benefit_id_fkey FOREIGN KEY (benefit_id) REFERENCES public.benefit(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.benefit_risk_event ADD CONSTRAINT benefit_risk_event_risk_event_id_fkey FOREIGN KEY (risk_event_id) REFERENCES public.risk_event(id) ON DELETE CASCADE;

-- plan 외래키
ALTER TABLE ONLY public.plan ADD CONSTRAINT plan_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id);
ALTER TABLE ONLY public.plan ADD CONSTRAINT plan_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id);
ALTER TABLE ONLY public.plan ADD CONSTRAINT plan_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.product_variant(id);

-- plan_coverage 외래키
ALTER TABLE ONLY public.plan_coverage ADD CONSTRAINT plan_coverage_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.plan(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.plan_coverage ADD CONSTRAINT plan_coverage_coverage_id_fkey FOREIGN KEY (coverage_id) REFERENCES public.coverage(id) ON DELETE CASCADE;
```

---

## 2. ER_DIAGRAM.md 수정

### 2.1 섹션 2.5 추가 (질병코드 도메인 다음)

```markdown
### 2.5 온톨로지 확장 도메인

\`\`\`mermaid
erDiagram
    risk_event {
        int id PK
        varchar event_type
        varchar event_name
        int severity_level
        varchar icd_code_pattern
        text description
    }

    benefit_risk_event {
        int id PK
        int benefit_id FK
        int risk_event_id FK
    }

    plan {
        int id PK
        int document_id FK
        int product_id FK
        int variant_id FK
        varchar plan_name
        varchar target_gender
        int target_age
        varchar insurance_period
        varchar payment_period
        varchar payment_cycle
        numeric total_premium
        jsonb attributes
    }

    plan_coverage {
        int id PK
        int plan_id FK
        int coverage_id FK
        numeric sum_insured
        varchar sum_insured_text
        numeric premium
        boolean is_basic
    }

    benefit ||--o{ benefit_risk_event : "triggers"
    risk_event ||--o{ benefit_risk_event : "triggered_by"
    document ||--o{ plan : "contains"
    product ||--o{ plan : "has"
    plan ||--o{ plan_coverage : "includes"
    coverage ||--o{ plan_coverage : "included_in"
\`\`\`
```

---

## 3. 작업 요약

| 섹션 | 파일 위치 | 추가 항목 |
|------|----------|----------|
| 테이블 정의 | `001_initial_schema.sql` Line ~435 | 4개 CREATE TABLE |
| 기본값 설정 | `001_initial_schema.sql` Line ~486 | 4개 ALTER COLUMN |
| 기본키 | `001_initial_schema.sql` Line ~506 | 4개 PRIMARY KEY |
| 유니크 | `001_initial_schema.sql` Line ~522 | 2개 UNIQUE |
| 인덱스 | `001_initial_schema.sql` Line ~568 | 8개 CREATE INDEX |
| 트리거 | `001_initial_schema.sql` Line ~583 | 2개 TRIGGER |
| 외래키 | `001_initial_schema.sql` Line ~630 | 7개 FOREIGN KEY |
| ER 다이어그램 | `ER_DIAGRAM.md` 섹션 2.5 | Mermaid 다이어그램 |

---

## 4. 검증 방법

```bash
# 스키마 검증 (19개 테이블 확인)
python db_refactoring/scripts/verify_schema.py --verbose
```
