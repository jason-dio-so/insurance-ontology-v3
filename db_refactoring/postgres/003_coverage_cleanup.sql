-- ============================================================================
-- Coverage 데이터 정제 마이그레이션
-- 버전: 1.0
-- 생성일: 2025-12-13
-- 목적: coverage_name 오염 데이터 정제 (problem.md 참조)
-- ============================================================================

-- 실행 전 백업 권장:
-- pg_dump -t coverage insurance_ontology_r1 > coverage_backup.sql

BEGIN;

-- ============================================================================
-- Step 1: 신규 컬럼 추가 (이미 스키마에 없는 경우)
-- ============================================================================

DO $$
BEGIN
    -- clause_number 컬럼 추가
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'coverage' AND column_name = 'clause_number'
    ) THEN
        ALTER TABLE coverage ADD COLUMN clause_number VARCHAR(50);
        COMMENT ON COLUMN coverage.clause_number IS '조항 번호 (예: 119, 121) - coverage_name 오염 방지용';
    END IF;

    -- coverage_period 컬럼 추가
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'coverage' AND column_name = 'coverage_period'
    ) THEN
        ALTER TABLE coverage ADD COLUMN coverage_period VARCHAR(20);
        COMMENT ON COLUMN coverage.coverage_period IS '기간 정보 (예: 10년, 15년) - coverage_name 오염 방지용';
    END IF;
END $$;

-- ============================================================================
-- Step 2: 조항 번호가 포함된 담보명 분리
-- 예: "119 뇌졸중진단비" → clause_number: "119", coverage_name: "뇌졸중진단비"
-- ============================================================================

-- 2-1: 조항 번호 추출 (숫자 + 공백 + 텍스트 패턴)
UPDATE coverage
SET
    clause_number = (regexp_match(coverage_name, '^(\d+)\s+'))[1],
    coverage_name = trim(regexp_replace(coverage_name, '^\d+\s+', ''))
WHERE coverage_name ~ '^\d+\s+[가-힣]';

-- 2-2: 변경 결과 확인 (실행 시 주석 해제)
-- SELECT id, clause_number, coverage_name FROM coverage WHERE clause_number IS NOT NULL;

-- ============================================================================
-- Step 3: 기간 정보만 있는 레코드 처리
-- 예: "10년", "15년", "20년" 등
-- ============================================================================

-- 3-1: 기간 정보 레코드 삭제 (의미 없는 담보명)
DELETE FROM coverage
WHERE coverage_name ~ '^(5|10|15|20|30)년$';

-- 3-2: 기간 패턴 포함된 경우 coverage_period로 이동 (선택적)
-- 예: "10년형 암진단비" → coverage_period: "10년형", coverage_name: "암진단비"
-- UPDATE coverage
-- SET
--     coverage_period = (regexp_match(coverage_name, '^(\d+년형?)\s*'))[1],
--     coverage_name = trim(regexp_replace(coverage_name, '^\d+년형?\s*', ''))
-- WHERE coverage_name ~ '^\d+년형?\s+[가-힣]';

-- ============================================================================
-- Step 4: [갱신형] 접두사 정규화
-- 예: "[갱신형]가족 일상생활중 배상책임Ⅱ" → renewal_type: "갱신형"
-- ============================================================================

-- 4-1: [갱신형] 접두사 처리
UPDATE coverage
SET
    renewal_type = '갱신형',
    coverage_name = trim(regexp_replace(coverage_name, '^\[갱신형\]\s*', ''))
WHERE coverage_name LIKE '[갱신형]%'
  AND (renewal_type IS NULL OR renewal_type = '');

-- 4-2: [비갱신형] 접두사 처리
UPDATE coverage
SET
    renewal_type = '비갱신형',
    coverage_name = trim(regexp_replace(coverage_name, '^\[비갱신형\]\s*', ''))
WHERE coverage_name LIKE '[비갱신형]%'
  AND (renewal_type IS NULL OR renewal_type = '');

-- ============================================================================
-- Step 5: 짧은 담보명 (3자 미만) 검토 및 삭제
-- ============================================================================

-- 5-1: 검토용 쿼리 (실행 시 주석 해제)
-- SELECT id, coverage_name FROM coverage WHERE length(coverage_name) < 3;

-- 5-2: 삭제 (필요 시)
DELETE FROM coverage
WHERE length(trim(coverage_name)) < 3;

-- ============================================================================
-- Step 6: 검증
-- ============================================================================

-- 정제 후 통계
DO $$
DECLARE
    total_count INTEGER;
    with_clause_num INTEGER;
    with_period INTEGER;
    short_names INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_count FROM coverage;
    SELECT COUNT(*) INTO with_clause_num FROM coverage WHERE clause_number IS NOT NULL;
    SELECT COUNT(*) INTO with_period FROM coverage WHERE coverage_period IS NOT NULL;
    SELECT COUNT(*) INTO short_names FROM coverage WHERE length(coverage_name) < 3;

    RAISE NOTICE '=== Coverage 데이터 정제 결과 ===';
    RAISE NOTICE '전체 coverage: %', total_count;
    RAISE NOTICE 'clause_number 분리: %', with_clause_num;
    RAISE NOTICE 'coverage_period 분리: %', with_period;
    RAISE NOTICE '짧은 담보명 (< 3자): %', short_names;
END $$;

COMMIT;

-- ============================================================================
-- 롤백 스크립트 (필요 시 별도 실행)
-- ============================================================================
-- BEGIN;
-- UPDATE coverage
-- SET coverage_name = clause_number || ' ' || coverage_name
-- WHERE clause_number IS NOT NULL;
--
-- UPDATE coverage SET clause_number = NULL, coverage_period = NULL;
-- COMMIT;
