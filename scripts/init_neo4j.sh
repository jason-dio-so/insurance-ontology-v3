#!/bin/bash
# ============================================================================
# Neo4j Initialization Script
# ============================================================================
#
# Neo4j 데이터베이스를 초기화합니다.
#

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Neo4j Initialization${NC}"
echo -e "${GREEN}=====================================${NC}"
echo

# Check for environment variables
if [ -z "$NEO4J_URI" ] || [ -z "$NEO4J_USER" ] || [ -z "$NEO4J_PASSWORD" ]; then
    echo -e "${RED}Error: NEO4J environment variables are not set${NC}"
    echo "Please set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in your .env file"
    exit 1
fi

echo -e "${YELLOW}Using NEO4J_URI: ${NEO4J_URI}${NC}"
echo

# Cypher files directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYPHER_DIR="${SCRIPT_DIR}/../db/neo4j"

echo "Cypher directory: ${CYPHER_DIR}"
echo

# Execute Cypher files in order
echo -e "${YELLOW}Executing Cypher scripts...${NC}"
echo

for cypher_file in $(ls -1 ${CYPHER_DIR}/*.cypher 2>/dev/null | sort); do
    filename=$(basename "$cypher_file")
    echo -e "  [*] Executing ${GREEN}${filename}${NC}..."

    if docker exec insurance-neo4j cypher-shell \
        -u "$NEO4J_USER" \
        -p "$NEO4J_PASSWORD" \
        -f /dev/stdin < "$cypher_file" > /dev/null 2>&1; then
        echo -e "      ${GREEN}✓ Success${NC}"
    else
        echo -e "      ${RED}✗ Failed${NC}"
        echo -e "${RED}Error executing ${filename}${NC}"
        exit 1
    fi
done

echo
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Neo4j initialized successfully!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo

# Display schema summary
echo "Schema summary:"
docker exec insurance-neo4j cypher-shell \
    -u "$NEO4J_USER" \
    -p "$NEO4J_PASSWORD" \
    "SHOW CONSTRAINTS;" 2>/dev/null || echo "(Constraints query failed)"

echo
echo "Indexes:"
docker exec insurance-neo4j cypher-shell \
    -u "$NEO4J_USER" \
    -p "$NEO4J_PASSWORD" \
    "SHOW INDEXES;" 2>/dev/null | head -20 || echo "(Indexes query failed)"

echo
echo -e "${GREEN}Done!${NC}"
echo
echo -e "${YELLOW}To view the graph schema:${NC}"
echo "  docker exec -it insurance-neo4j cypher-shell -u ${NEO4J_USER} -p ${NEO4J_PASSWORD}"
echo "  CALL db.schema.visualization();"
