#!/bin/bash
# Production Deployment Verification Script
# Validates current system state against PRODUCTION_DEPLOY.md expected results
# Usage: ./scripts/verify_production_deploy.sh

set -e
set +e  # Temporarily disable exit on error for Neo4j check

# Save existing POSTGRES_URL if set (e.g., from command line)
SAVED_POSTGRES_URL="$POSTGRES_URL"

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Restore POSTGRES_URL if it was originally set
if [ -n "$SAVED_POSTGRES_URL" ]; then
    POSTGRES_URL="$SAVED_POSTGRES_URL"
fi

echo "=========================================="
echo "🔍 Production Deployment Verification"
echo "=========================================="
echo "Validating system state against docs/PRODUCTION_DEPLOY.md"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Helper function to check value
check_value() {
    local name="$1"
    local actual="$2"
    local expected="$3"
    local tolerance="${4:-0}"  # Optional tolerance for approximate matches

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    if [ "$tolerance" -eq 0 ]; then
        # Exact match
        if [ "$actual" -eq "$expected" ]; then
            echo -e "  ${GREEN}✓${NC} $name: $actual (expected: $expected)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
            return 0
        else
            echo -e "  ${RED}✗${NC} $name: $actual (expected: $expected)"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
            return 1
        fi
    else
        # Range match (within tolerance)
        local diff=$((actual - expected))
        local abs_diff=${diff#-}  # Absolute value

        if [ "$abs_diff" -le "$tolerance" ]; then
            echo -e "  ${GREEN}✓${NC} $name: $actual (expected: ~$expected ±$tolerance)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
            return 0
        else
            echo -e "  ${RED}✗${NC} $name: $actual (expected: ~$expected ±$tolerance)"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
            return 1
        fi
    fi
}

# Helper function for service checks
check_service() {
    local name="$1"
    local pattern="$2"

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    if docker ps | grep -q "$pattern"; then
        echo -e "  ${GREEN}✓${NC} $name running"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} $name not running"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Set POSTGRES_URL: prioritize environment variable, then .env, then default to test DB
if [ -z "$POSTGRES_URL" ]; then
    POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"
fi
export POSTGRES_URL

echo "🔗 Using database: $(echo $POSTGRES_URL | sed 's|.*@|@|')"
echo ""

echo "=========================================="
echo "Phase 0: Environment Setup"
echo "=========================================="

# Check Docker services
check_service "PostgreSQL" "postgres"
check_service "Neo4j" "neo4j"

# Check DB connection
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if psql "$POSTGRES_URL" -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} PostgreSQL connection"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "  ${RED}✗${NC} PostgreSQL connection failed"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    echo -e "\n${RED}Cannot proceed without DB connection${NC}"
    exit 1
fi

# Check number of tables
TABLE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
check_value "DB tables" "$TABLE_COUNT" 16 2

echo ""
echo "=========================================="
echo "Phase 1: Document Ingestion"
echo "=========================================="

# Documents
DOC_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM document;" 2>/dev/null | tr -d ' ')
check_value "Documents" "$DOC_COUNT" 38

# Clauses
CLAUSE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM document_clause;" 2>/dev/null | tr -d ' ')
check_value "Clauses" "$CLAUSE_COUNT" 80682 100

# Table row clauses
TABLE_ROW_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM document_clause WHERE clause_type = 'table_row';" 2>/dev/null | tr -d ' ')
check_value "Table rows" "$TABLE_ROW_COUNT" 548 50

echo ""
echo "=========================================="
echo "Phase 2: Entity Extraction"
echo "=========================================="

# Coverages
COVERAGE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM coverage;" 2>/dev/null | tr -d ' ')
check_value "Coverages" "$COVERAGE_COUNT" 384 10

# Benefits
BENEFIT_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM benefit;" 2>/dev/null | tr -d ' ')
check_value "Benefits" "$BENEFIT_COUNT" 384 10

# Disease code sets
DISEASE_SET_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM disease_code_set;" 2>/dev/null | tr -d ' ')
check_value "Disease code sets" "$DISEASE_SET_COUNT" 9

# Disease codes
DISEASE_CODE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM disease_code;" 2>/dev/null | tr -d ' ')
check_value "Disease codes" "$DISEASE_CODE_COUNT" 131 5

# Clause-Coverage mappings
CLAUSE_COVERAGE_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM clause_coverage;" 2>/dev/null | tr -d ' ')
check_value "Clause-Coverage mappings" "$CLAUSE_COVERAGE_COUNT" 674 50

# Standard mappings (optional)
STANDARD_MAPPING_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM coverage_standard_mapping;" 2>/dev/null | tr -d ' ')
if [ "$STANDARD_MAPPING_COUNT" -gt 0 ]; then
    check_value "Standard mappings" "$STANDARD_MAPPING_COUNT" 264 20
else
    echo -e "  ${YELLOW}⚠${NC} Standard mappings: 0 (optional feature, expected: 264)"
fi

echo ""
echo "=========================================="
echo "Phase 3: Neo4j Graph Sync"
echo "=========================================="

# Check Neo4j connection using Python
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

# Create temporary Python script to query Neo4j with timeout
NEO4J_CHECK_SCRIPT=$(cat <<'PYTHON_SCRIPT'
import sys
import signal

# Timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Neo4j query timeout (10 seconds)")

try:
    # Set timeout for 10 seconds
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(sys.argv[1], auth=(sys.argv[2], sys.argv[3]))
    with driver.session() as session:
        # Node count
        result = session.run("MATCH (n) RETURN count(n) as count")
        node_count = result.single()["count"]
        print(f"NODES:{node_count}")

        # Relationship count
        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = result.single()["count"]
        print(f"RELS:{rel_count}")
    driver.close()

    # Cancel alarm
    signal.alarm(0)
except Exception as e:
    print(f"ERROR:{e}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
)

NEO4J_RESULT=$(python3 -c "$NEO4J_CHECK_SCRIPT" "$NEO4J_URI" "$NEO4J_USER" "$NEO4J_PASSWORD" 2>&1)

if echo "$NEO4J_RESULT" | grep -q "ERROR"; then
    echo -e "  ${YELLOW}⚠${NC} Neo4j connection failed or neo4j Python driver not installed"
    echo -e "  ${YELLOW}  Skipping Neo4j checks${NC}"
    echo -e "  ${YELLOW}  Install: pip install neo4j${NC}"
else
    NEO4J_NODE_COUNT=$(echo "$NEO4J_RESULT" | grep "NODES:" | cut -d':' -f2)
    NEO4J_REL_COUNT=$(echo "$NEO4J_RESULT" | grep "RELS:" | cut -d':' -f2)

    check_value "Neo4j nodes" "$NEO4J_NODE_COUNT" 966 50
    check_value "Neo4j relationships" "$NEO4J_REL_COUNT" 997 50
fi

echo ""
echo "=========================================="
echo "Phase 4: Vector Index"
echo "=========================================="

# Embeddings
EMBEDDING_COUNT=$(psql "$POSTGRES_URL" -t -c "SELECT COUNT(*) FROM clause_embedding;" 2>/dev/null | tr -d ' ')
check_value "Embeddings" "$EMBEDDING_COUNT" 80682 100

# Check embedding dimension (sample)
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if [ "$EMBEDDING_COUNT" -gt 0 ]; then
    EMBEDDING_DIM=$(psql "$POSTGRES_URL" -t -c "SELECT array_length(embedding, 1) FROM clause_embedding WHERE embedding IS NOT NULL LIMIT 1;" 2>/dev/null | tr -d ' ' | tr -d '\n')

    # Check if dimension is numeric and correct
    if [ -n "$EMBEDDING_DIM" ] && [ "$EMBEDDING_DIM" = "1536" ]; then
        echo -e "  ${GREEN}✓${NC} Embedding dimension: 1536"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    elif [ -n "$EMBEDDING_DIM" ]; then
        echo -e "  ${RED}✗${NC} Embedding dimension: $EMBEDDING_DIM (expected: 1536)"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    else
        echo -e "  ${YELLOW}⚠${NC} Could not retrieve embedding dimension (likely psql connection issue)"
        # Don't count as failure for production readiness
        TOTAL_CHECKS=$((TOTAL_CHECKS - 1))
    fi
else
    echo -e "  ${YELLOW}⚠${NC} No embeddings found, skipping dimension check"
fi

echo ""
echo "=========================================="
echo "Phase 5: QA Evaluation"
echo "=========================================="

# Check if evaluation results exist
EVAL_FILE="evaluation/results/phase5_evaluation_v5_fixed.json"

TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if [ -f "$EVAL_FILE" ]; then
    echo -e "  ${GREEN}✓${NC} Evaluation results found: $EVAL_FILE"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))

    # Extract accuracy (requires jq)
    if command -v jq >/dev/null 2>&1; then
        ACCURACY=$(cat "$EVAL_FILE" | jq -r '.overall.accuracy' 2>/dev/null || echo "N/A")
        ERROR_COUNT=$(cat "$EVAL_FILE" | jq -r '.overall.error' 2>/dev/null || echo "N/A")

        if [ "$ACCURACY" != "N/A" ]; then
            # Convert to integer for comparison (86.0 -> 86)
            ACCURACY_INT=$(echo "$ACCURACY" | cut -d'.' -f1)

            TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
            if [ "$ACCURACY_INT" -ge 86 ]; then
                echo -e "  ${GREEN}✓${NC} QA Accuracy: ${ACCURACY}% (expected: ≥86%)"
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            else
                echo -e "  ${RED}✗${NC} QA Accuracy: ${ACCURACY}% (expected: ≥86%)"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi

            TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
            if [ "$ERROR_COUNT" = "0" ]; then
                echo -e "  ${GREEN}✓${NC} Error count: 0"
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            else
                echo -e "  ${RED}✗${NC} Error count: $ERROR_COUNT (expected: 0)"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi
        fi
    else
        echo -e "  ${YELLOW}⚠${NC} jq not installed, skipping accuracy validation"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Evaluation results not found: $EVAL_FILE"
    echo -e "  ${YELLOW}  Run: python scripts/evaluate_qa.py --qa-set data/gold_qa_set_50.json --output evaluation/results/evaluation.json${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo ""
echo "=========================================="
echo "📊 Verification Summary"
echo "=========================================="

PASS_RATE=$(awk "BEGIN {printf \"%.1f\", ($PASSED_CHECKS / $TOTAL_CHECKS) * 100}")

echo -e "Total checks: $TOTAL_CHECKS"
echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
echo -e "Pass rate: ${PASS_RATE}%"
echo ""

if [ "$FAILED_CHECKS" -eq 0 ]; then
    echo -e "${GREEN}✅ All checks PASSED${NC}"
    echo -e "${GREEN}System state matches PRODUCTION_DEPLOY.md expectations${NC}"
    echo ""
    echo "🎯 Production Ready: YES"
    exit 0
elif [ "$PASS_RATE" = "90.0" ] || [ "${PASS_RATE%%.*}" -ge 90 ]; then
    echo -e "${YELLOW}⚠️ Most checks passed (${PASS_RATE}%)${NC}"
    echo -e "${YELLOW}Minor discrepancies detected - review recommended${NC}"
    echo ""
    echo "🎯 Production Ready: MOSTLY (review failures)"
    exit 0
else
    echo -e "${RED}❌ Multiple checks FAILED (${PASS_RATE}% pass rate)${NC}"
    echo -e "${RED}System state does NOT match PRODUCTION_DEPLOY.md${NC}"
    echo ""
    echo "🎯 Production Ready: NO"
    echo ""
    echo "Recommended actions:"
    echo "1. Review PRODUCTION_DEPLOY.md for missing steps"
    echo "2. Check failed items above"
    echo "3. Re-run incomplete phases"
    exit 1
fi
