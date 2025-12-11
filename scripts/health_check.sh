#!/bin/bash
# Quick Health Check for Insurance Ontology Project
# Usage: ./scripts/health_check.sh

set -e

echo "=========================================="
echo "🏥 Insurance Ontology Health Check"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check current directory
echo -e "\n📁 Work Directory:"
pwd
if [[ $(pwd) == *"insurance-ontology-v2"* ]]; then
    echo -e "${GREEN}✓ Correct directory${NC}"
else
    echo -e "${YELLOW}⚠ Expected: insurance-ontology-v2${NC}"
fi

# Check Docker services
echo -e "\n🐳 Docker Services:"
if docker ps | grep -q "insurance-postgres"; then
    echo -e "${GREEN}✓ PostgreSQL running${NC}"
else
    echo -e "${RED}✗ PostgreSQL not running${NC}"
fi

if docker ps | grep -q "insurance-neo4j"; then
    echo -e "${GREEN}✓ Neo4j running${NC}"
else
    echo -e "${YELLOW}⚠ Neo4j not running${NC}"
fi

if docker ps | grep -q "insurance-qdrant"; then
    echo -e "${GREEN}✓ Qdrant running${NC}"
else
    echo -e "${YELLOW}⚠ Qdrant not running${NC}"
fi

# Check database
echo -e "\n💾 Database Status:"
POSTGRES_URL="${POSTGRES_URL:-postgresql://postgres:postgres@localhost:5432/insurance_ontology_test}"

if psql "$POSTGRES_URL" -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Database connected${NC}"

    # Get counts
    DOC_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM document;" 2>/dev/null | tr -d ' ')
    CLAUSE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM document_clause;" 2>/dev/null | tr -d ' ')
    COVERAGE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(DISTINCT structured_data->>'coverage_name') FROM document_clause WHERE clause_type='table_row' AND structured_data->>'coverage_name' IS NOT NULL;" 2>/dev/null | tr -d ' ')

    echo "  Documents: $DOC_COUNT (expected: 38)"
    echo "  Clauses: $CLAUSE_COUNT (expected: ~80,682)"
    echo "  Unique Coverages: $COVERAGE_COUNT (expected: 348)"

    # Validate
    if [ "$DOC_COUNT" -eq 38 ] && [ "$CLAUSE_COUNT" -gt 70000 ] && [ "$COVERAGE_COUNT" -gt 300 ]; then
        echo -e "${GREEN}✓ Phase 1 완료 (NORMAL Mode)${NC}"
    elif [ "$DOC_COUNT" -eq 0 ]; then
        echo -e "${YELLOW}⚠ Phase 1 미완료${NC}"
    else
        echo -e "${YELLOW}⚠ 부분 완료 또는 데이터 이상${NC}"
    fi
else
    echo -e "${RED}✗ Database connection failed${NC}"
fi

# Check checkpoint
echo -e "\n🔖 Checkpoint Status:"
if [ -f "data/checkpoints/phase1_progress.json" ]; then
    COMPLETED_COUNT=$(cat data/checkpoints/phase1_progress.json | grep -o '"completed"' | wc -l)
    FAILED_COUNT=$(cat data/checkpoints/phase1_progress.json | grep -o '"failed"' | wc -l)
    LAST_UPDATE=$(cat data/checkpoints/phase1_progress.json | grep "last_updated" | cut -d'"' -f4)

    echo -e "${GREEN}✓ Checkpoint exists${NC}"
    echo "  Completed: $(cat data/checkpoints/phase1_progress.json | grep -o 'lotte-\|hanwha-\|kb-\|heungkuk-\|meritz-\|hyundai-\|samsung-\|db-' | wc -l | tr -d ' ') documents"
    echo "  Last updated: $LAST_UPDATE"
else
    echo -e "${YELLOW}⚠ No checkpoint found${NC}"
fi

# Check key files
echo -e "\n📄 Key Files:"
FILES=(
    "ingestion/ingest_v3.py"
    "ingestion/parsers/hybrid_parser_v2.py"
    "ingestion/parsers/carrier_parsers/base_parser.py"
    "scripts/batch_ingest.py"
    "data/documents_metadata.json"
    "CURRENT_STATUS.md"
    "VALIDATION_MODES.md"
    "RECOVERY_GUIDE.md"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file"
    fi
done

# Summary
echo -e "\n=========================================="
echo "📊 Summary:"
echo "=========================================="

if [ "$DOC_COUNT" -eq 38 ] && [ "$CLAUSE_COUNT" -gt 70000 ]; then
    echo -e "${GREEN}✅ System is healthy - Phase 1 complete${NC}"
    echo "Next step: Phase 2 (Coverage Pipeline)"
    echo "Command: python -m ingestion.coverage_pipeline --carrier all"
elif [ "$DOC_COUNT" -gt 0 ] && [ "$DOC_COUNT" -lt 38 ]; then
    echo -e "${YELLOW}⚠️ Partial completion - Resume recommended${NC}"
    echo "Command: python3 scripts/batch_ingest.py --resume --batch-size 5"
else
    echo -e "${YELLOW}⚠️ Phase 1 not started or incomplete${NC}"
    echo "Command: python3 scripts/batch_ingest.py --all --batch-size 5"
fi

echo ""
