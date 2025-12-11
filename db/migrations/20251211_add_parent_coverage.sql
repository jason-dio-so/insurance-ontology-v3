-- Migration: Add parent_coverage_id to support coverage hierarchy
-- Date: 2025-12-11
-- Purpose: Enable InfoExtractor to find general definition clauses (e.g., 제28조)
--
-- Example hierarchy:
--   일반암 (parent)
--     ├─ 일반암진단비Ⅱ
--     ├─ 일반암수술비
--     └─ 일반암주요치료비
--
-- Rollback: See ROLLBACK section at bottom

-- ============================================================================
-- FORWARD MIGRATION
-- ============================================================================

-- Step 1: Add parent_coverage_id column
ALTER TABLE coverage
ADD COLUMN parent_coverage_id INTEGER REFERENCES coverage(id);

-- Step 2: Create index
CREATE INDEX idx_coverage_parent ON coverage(parent_coverage_id);

-- Step 3: Create parent coverages (6 records)
-- These represent general coverage categories that have common definition clauses

-- 일반암 (General Cancer)
INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
SELECT 1, '일반암', 'general_cancer', 'diagnosis', true
WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '일반암' AND is_basic = true);

-- 뇌혈관질환 (Cerebrovascular Disease)
INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
SELECT 1, '뇌혈관질환', 'cerebrovascular', 'diagnosis', true
WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '뇌혈관질환' AND is_basic = true);

-- 뇌졸중 (Stroke)
INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
SELECT 1, '뇌졸중', 'stroke', 'diagnosis', true
WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '뇌졸중' AND is_basic = true);

-- 뇌출혈 (Cerebral Hemorrhage)
INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
SELECT 1, '뇌출혈', 'cerebral_hemorrhage', 'diagnosis', true
WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '뇌출혈' AND is_basic = true);

-- 허혈심장질환 (Ischemic Heart Disease)
INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
SELECT 1, '허혈심장질환', 'ischemic_heart', 'diagnosis', true
WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '허혈심장질환' AND is_basic = true);

-- 급성심근경색 (Acute Myocardial Infarction)
INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
SELECT 1, '급성심근경색', 'acute_mi', 'diagnosis', true
WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '급성심근경색' AND is_basic = true);

-- Step 4: Map child coverages to parent coverages

-- 일반암XXX → 일반암 parent
UPDATE coverage
SET parent_coverage_id = (SELECT id FROM coverage WHERE coverage_name = '일반암' AND is_basic = true)
WHERE coverage_name LIKE '%일반암%'
  AND coverage_name != '일반암'
  AND parent_coverage_id IS NULL;

-- 뇌혈관질환XXX → 뇌혈관질환 parent
UPDATE coverage
SET parent_coverage_id = (SELECT id FROM coverage WHERE coverage_name = '뇌혈관질환' AND is_basic = true)
WHERE coverage_name LIKE '%뇌혈관질환%'
  AND coverage_name != '뇌혈관질환'
  AND parent_coverage_id IS NULL;

-- 뇌졸중XXX → 뇌졸중 parent
UPDATE coverage
SET parent_coverage_id = (SELECT id FROM coverage WHERE coverage_name = '뇌졸중' AND is_basic = true)
WHERE coverage_name LIKE '%뇌졸중%'
  AND coverage_name != '뇌졸중'
  AND parent_coverage_id IS NULL;

-- 뇌출혈XXX → 뇌출혈 parent
UPDATE coverage
SET parent_coverage_id = (SELECT id FROM coverage WHERE coverage_name = '뇌출혈' AND is_basic = true)
WHERE coverage_name LIKE '%뇌출혈%'
  AND coverage_name != '뇌출혈'
  AND parent_coverage_id IS NULL;

-- 허혈심장질환XXX → 허혈심장질환 parent
UPDATE coverage
SET parent_coverage_id = (SELECT id FROM coverage WHERE coverage_name = '허혈심장질환' AND is_basic = true)
WHERE (coverage_name LIKE '%허혈심장질환%' OR coverage_name LIKE '%허혈성심장질환%')
  AND coverage_name NOT IN ('허혈심장질환', '허혈성심장질환')
  AND parent_coverage_id IS NULL;

-- 급성심근경색XXX → 급성심근경색 parent
UPDATE coverage
SET parent_coverage_id = (SELECT id FROM coverage WHERE coverage_name = '급성심근경색' AND is_basic = true)
WHERE coverage_name LIKE '%급성심근경색%'
  AND coverage_name != '급성심근경색'
  AND parent_coverage_id IS NULL;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check parent coverages created
SELECT coverage_name, coverage_code, is_basic
FROM coverage
WHERE is_basic = true AND coverage_code IN (
  'general_cancer', 'cerebrovascular', 'stroke',
  'cerebral_hemorrhage', 'ischemic_heart', 'acute_mi'
)
ORDER BY coverage_name;

-- Check child-parent mappings
SELECT
  parent.coverage_name as parent,
  COUNT(*) as child_count
FROM coverage child
JOIN coverage parent ON child.parent_coverage_id = parent.id
GROUP BY parent.id, parent.coverage_name
ORDER BY child_count DESC;

-- ============================================================================
-- ROLLBACK
-- ============================================================================

/*
-- To rollback this migration, run:

-- Step 1: Remove child-parent mappings
UPDATE coverage SET parent_coverage_id = NULL WHERE parent_coverage_id IS NOT NULL;

-- Step 2: Delete parent coverages
DELETE FROM coverage
WHERE coverage_name IN ('일반암', '뇌혈관질환', '뇌졸중', '뇌출혈', '허혈심장질환', '급성심근경색')
  AND is_basic = true
  AND coverage_code IN ('general_cancer', 'cerebrovascular', 'stroke', 'cerebral_hemorrhage', 'ischemic_heart', 'acute_mi');

-- Step 3: Drop index
DROP INDEX IF EXISTS idx_coverage_parent;

-- Step 4: Drop column
ALTER TABLE coverage DROP COLUMN IF EXISTS parent_coverage_id;

*/
