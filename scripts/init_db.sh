#!/bin/bash
# ============================================================================
# Database Initialization Script
# ============================================================================
#
# PostgreSQL 데이터베이스를 초기화합니다.
#

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Database Initialization${NC}"
echo -e "${GREEN}=====================================${NC}"
echo

# Check for POSTGRES_URL environment variable
if [ -z "$POSTGRES_URL" ]; then
    echo -e "${RED}Error: POSTGRES_URL environment variable is not set${NC}"
    echo "Please set POSTGRES_URL in your .env file or export it"
    exit 1
fi

echo -e "${YELLOW}Using POSTGRES_URL: ${POSTGRES_URL}${NC}"
echo

# Extract database name from URL
DB_NAME=$(echo $POSTGRES_URL | sed -n 's|.*\/\([^?]*\).*|\1|p')
echo -e "Database: ${GREEN}${DB_NAME}${NC}"
echo

# SQL files directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="${SCRIPT_DIR}/../db/postgres"

echo "SQL directory: ${SQL_DIR}"
echo

# Execute SQL files in order
echo -e "${YELLOW}Executing SQL migrations...${NC}"
echo

for sql_file in $(ls -1 ${SQL_DIR}/*.sql | sort); do
    filename=$(basename "$sql_file")
    echo -e "  [*] Executing ${GREEN}${filename}${NC}..."

    if psql "$POSTGRES_URL" -f "$sql_file" > /dev/null 2>&1; then
        echo -e "      ${GREEN}✓ Success${NC}"
    else
        echo -e "      ${RED}✗ Failed${NC}"
        echo -e "${RED}Error executing ${filename}${NC}"
        exit 1
    fi
done

echo
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Database initialized successfully!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo

# Display table counts
echo "Table summary:"
psql "$POSTGRES_URL" -c "\dt" 2>/dev/null | grep -E "company|product|coverage"

echo
echo "Coverage categories:"
psql "$POSTGRES_URL" -c "SELECT category_code, category_name_kr FROM coverage_category ORDER BY display_order;" 2>/dev/null || echo "(Table not yet created)"

echo
echo -e "${GREEN}Done!${NC}"
