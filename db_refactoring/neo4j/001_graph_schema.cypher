// =============================================================================
// Neo4j Graph Schema - Insurance Ontology
// =============================================================================
// 생성일: 2025-12-13
// 설명: Neo4j 제약조건, 인덱스 정의
// 적용: cypher-shell -u neo4j -p $NEO4J_PASSWORD -f 001_graph_schema.cypher
// =============================================================================

// -----------------------------------------------------------------------------
// 1. 제약조건 (UNIQUE) - 자동으로 인덱스 생성됨
// -----------------------------------------------------------------------------

// Company
CREATE CONSTRAINT company_id IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT company_code IF NOT EXISTS
FOR (c:Company) REQUIRE c.code IS UNIQUE;

// Product
CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT product_code IF NOT EXISTS
FOR (p:Product) REQUIRE p.code IS UNIQUE;

// ProductVariant
CREATE CONSTRAINT product_variant_id IF NOT EXISTS
FOR (pv:ProductVariant) REQUIRE pv.id IS UNIQUE;

// Coverage
CREATE CONSTRAINT coverage_id IF NOT EXISTS
FOR (c:Coverage) REQUIRE c.id IS UNIQUE;

// Benefit
CREATE CONSTRAINT benefit_id IF NOT EXISTS
FOR (b:Benefit) REQUIRE b.id IS UNIQUE;

// Document
CREATE CONSTRAINT document_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT document_document_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.document_id IS UNIQUE;

// DiseaseCodeSet
CREATE CONSTRAINT disease_code_set_id IF NOT EXISTS
FOR (dcs:DiseaseCodeSet) REQUIRE dcs.id IS UNIQUE;

// DiseaseCode
CREATE CONSTRAINT disease_code_id IF NOT EXISTS
FOR (dc:DiseaseCode) REQUIRE dc.id IS UNIQUE;

// RiskEvent (온톨로지 확장)
CREATE CONSTRAINT risk_event_id IF NOT EXISTS
FOR (re:RiskEvent) REQUIRE re.id IS UNIQUE;

// Condition (온톨로지 확장)
CREATE CONSTRAINT condition_id IF NOT EXISTS
FOR (cond:Condition) REQUIRE cond.id IS UNIQUE;

// Exclusion (온톨로지 확장)
CREATE CONSTRAINT exclusion_id IF NOT EXISTS
FOR (ex:Exclusion) REQUIRE ex.id IS UNIQUE;

// Plan (가입설계)
CREATE CONSTRAINT plan_id IF NOT EXISTS
FOR (pl:Plan) REQUIRE pl.id IS UNIQUE;

// -----------------------------------------------------------------------------
// 2. 인덱스 - 검색 성능 향상
// -----------------------------------------------------------------------------

// Company 인덱스
CREATE INDEX company_name IF NOT EXISTS
FOR (c:Company) ON (c.name);

// Product 인덱스
CREATE INDEX product_name IF NOT EXISTS
FOR (p:Product) ON (p.name);

// Coverage 인덱스
CREATE INDEX coverage_name IF NOT EXISTS
FOR (c:Coverage) ON (c.name);

CREATE INDEX coverage_category IF NOT EXISTS
FOR (c:Coverage) ON (c.category);

// Benefit 인덱스
CREATE INDEX benefit_name IF NOT EXISTS
FOR (b:Benefit) ON (b.name);

CREATE INDEX benefit_type IF NOT EXISTS
FOR (b:Benefit) ON (b.type);

// Document 인덱스
CREATE INDEX document_doc_type IF NOT EXISTS
FOR (d:Document) ON (d.doc_type);

// DiseaseCode 인덱스
CREATE INDEX disease_code_code IF NOT EXISTS
FOR (dc:DiseaseCode) ON (dc.code);

CREATE INDEX disease_code_type IF NOT EXISTS
FOR (dc:DiseaseCode) ON (dc.type);

// RiskEvent 인덱스 (온톨로지 확장)
CREATE INDEX risk_event_event_type IF NOT EXISTS
FOR (re:RiskEvent) ON (re.event_type);

CREATE INDEX risk_event_event_name IF NOT EXISTS
FOR (re:RiskEvent) ON (re.event_name);

// Condition 인덱스 (온톨로지 확장)
CREATE INDEX condition_condition_type IF NOT EXISTS
FOR (cond:Condition) ON (cond.condition_type);

// Exclusion 인덱스 (온톨로지 확장)
CREATE INDEX exclusion_exclusion_type IF NOT EXISTS
FOR (ex:Exclusion) ON (ex.exclusion_type);

// Plan 인덱스 (가입설계)
CREATE INDEX plan_product_id IF NOT EXISTS
FOR (pl:Plan) ON (pl.product_id);

CREATE INDEX plan_target_gender IF NOT EXISTS
FOR (pl:Plan) ON (pl.target_gender);

CREATE INDEX plan_target_age IF NOT EXISTS
FOR (pl:Plan) ON (pl.target_age);

// -----------------------------------------------------------------------------
// 3. 노드 레이블 및 관계 타입 참조
// -----------------------------------------------------------------------------
//
// 노드 레이블:
//   - Company: 보험사 (id, code, name, business_type)
//   - Product: 보험 상품 (id, code, name, business_type)
//   - ProductVariant: 상품 변형 (id, code, name, target_gender, target_age_range)
//   - Coverage: 담보 (id, code, name, category, renewal_type, is_basic)
//   - Benefit: 급부 (id, name, amount, amount_text, type)
//   - Document: 문서 (id, document_id, doc_type, doc_subtype, version, total_pages)
//   - DiseaseCodeSet: 질병코드 집합 (id, name, description, version)
//   - DiseaseCode: 질병 코드 (id, code, type, description)
//   - RiskEvent: 위험 이벤트 (id, event_type, event_name, severity_level, icd_code_pattern)
//   - Condition: 급여 조건 (id, condition_type, value, unit)
//   - Exclusion: 면책 조건 (id, exclusion_type, description)
//   - Plan: 가입설계 (id, plan_name, target_gender, target_age, insurance_period, payment_period, total_premium)
//
// 관계 타입:
//   - HAS_PRODUCT: Company -> Product
//   - HAS_VARIANT: Product -> ProductVariant
//   - OFFERS: Product -> Coverage
//   - HAS_BENEFIT: Coverage -> Benefit
//   - HAS_DOCUMENT: Company/Product/ProductVariant -> Document
//   - CONTAINS: DiseaseCodeSet -> DiseaseCode
//   - PARENT_OF: Coverage -> Coverage (담보 계층)
//   - TRIGGERS: Benefit -> RiskEvent (급부가 위험이벤트 트리거)
//   - HAS_CONDITION: Benefit -> Condition (급부의 조건)
//   - HAS_EXCLUSION: Coverage -> Exclusion (담보의 면책 조건)
//   - FOR_PRODUCT: Plan -> Product (가입설계가 속한 상품)
//   - HAS_VARIANT: Plan -> ProductVariant (가입설계의 상품변형)
//   - INCLUDES: Plan -> Coverage (가입설계에 포함된 담보, 관계 속성: sum_insured, premium)
//   - FROM_DOCUMENT: Plan -> Document (가입설계의 출처 문서)
//
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// 4. 검증 쿼리
// -----------------------------------------------------------------------------
// SHOW CONSTRAINTS;
// SHOW INDEXES;
// MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY label;
// MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY type;
// -----------------------------------------------------------------------------
