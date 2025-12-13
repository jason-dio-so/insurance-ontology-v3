-- ============================================================================
-- 보험 온톨로지 시드 데이터
-- 버전: 1.0
-- 생성일: 2025-12-13
-- 설명: 초기 시드 데이터 (coverage_category, disease_code_set, company)
-- ============================================================================

-- ============================================================================
-- 1. coverage_category (담보 카테고리)
-- ============================================================================

INSERT INTO public.coverage_category (category_code, category_name_kr, category_name_en, description, display_order) VALUES
('death_disability', '사망/장해/장애군', 'Death/Disability/Handicap', NULL, 1),
('dementia_long_term_care', '치매 및 장기요양군', 'Dementia & Long-term Care', NULL, 2),
('cancer_diagnosis', '암진단군', 'Cancer Diagnosis', NULL, 3),
('major_disease_diagnosis', '2대질병진단군', 'Major Disease Diagnosis (Stroke/Heart)', NULL, 4),
('specific_disease_diagnosis', '특정질병진단군', 'Specific Disease Diagnosis', NULL, 5),
('hospitalization', '입원군', 'Hospitalization', NULL, 6),
('surgery', '수술군', 'Surgery', NULL, 7),
('outpatient', '통원군', 'Outpatient', NULL, 8),
('other_benefits', '기타보장군', 'Other Benefits', NULL, 9);

-- ============================================================================
-- 2. disease_code_set (질병코드 집합)
-- ============================================================================

INSERT INTO public.disease_code_set (set_name, description, version) VALUES
('악성신생물', '암(악성신생물) 분류표', 'KCD-8'),
('제자리신생물', '제자리신생물 및 양성신생물', 'KCD-8'),
('기타피부암', '기타피부암', 'KCD-8'),
('갑상선암', '갑상선의 악성신생물', 'KCD-8'),
('뇌출혈', '뇌출혈 (뇌내출혈, 거미막하출혈 등)', 'KCD-8'),
('뇌경색', '뇌경색', 'KCD-8'),
('뇌졸중', '뇌졸중 (뇌혈관질환)', 'KCD-8'),
('급성심근경색', '급성심근경색증', 'KCD-8'),
('허혈성심장질환', '허혈성 심장질환', 'KCD-8');

-- ============================================================================
-- 3. company (보험사)
-- ============================================================================

INSERT INTO public.company (company_code, company_name, business_type) VALUES
('samsung', '삼성', NULL),
('db', 'DB', NULL),
('lotte', '롯데', NULL),
('kb', 'KB', NULL),
('hyundai', '현대', NULL),
('hanwha', '한화', NULL),
('heungkuk', '흥국', NULL),
('meritz', '메리츠', NULL);

-- ============================================================================
-- 시드 데이터 끝
-- ============================================================================
