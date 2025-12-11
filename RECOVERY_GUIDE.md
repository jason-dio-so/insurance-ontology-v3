# 🚨 시스템 다운 시 복구 가이드

## Quick Recovery Checklist (5분 내 복구)

### 1️⃣ 현재 상태 확인 (1분)
```bash
# 작업 디렉토리 확인
cd /Users/cheollee/insurance-ontology-v2
ls -la

# Docker 서비스 확인
docker ps | grep -E "postgres|neo4j|qdrant"

# DB 상태 확인
psql postgresql://postgres:postgres@localhost:5432/insurance_ontology_test \
  -c "SELECT COUNT(*) FROM document; SELECT COUNT(*) FROM document_clause;"

# Checkpoint 확인
cat data/checkpoints/phase1_progress.json | grep -E "completed|failed" | head -5
```

**예상 결과**:
- Documents: 38
- Clauses: ~80,682
- Checkpoint: 38 completed, 0 failed

---

### 2️⃣ 서비스 재시작 (필요 시)
```bash
# Docker 서비스 다운된 경우
cd /Users/cheollee/insurance-ontology-claude-backup-2025-12-10
./scripts/start_hybrid_services.sh

# 서비스 확인
docker ps
# Expected: postgres, neo4j, qdrant 모두 Up 상태
```

---

### 3️⃣ 작업 재개 위치 확인 (1분)

#### Phase 1 완료 확인
```bash
psql postgresql://postgres:postgres@localhost:5432/insurance_ontology_test \
  -c "SELECT COUNT(DISTINCT structured_data->>'coverage_name') AS unique_coverages FROM document_clause WHERE clause_type = 'table_row';"
```

**결과 해석**:
- `0` → Phase 1 미완료 → Step 4A 실행
- `348` → Phase 1 완료 (NORMAL) → Step 4B 실행
- `250-270` → Phase 1 완료 (STRICT) → Step 4B 실행

---

### 4️⃣ 작업 재개

#### A. Phase 1 미완료 시
```bash
cd /Users/cheollee/insurance-ontology-v2
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"

# Checkpoint 확인
cat data/checkpoints/phase1_progress.json 2>/dev/null

# Resume 실행 (checkpoint 있으면 이어서 진행)
python3 scripts/batch_ingest.py --resume --batch-size 5

# Checkpoint 없으면 처음부터
python3 scripts/batch_ingest.py --all --batch-size 5
```

#### B. Phase 1 완료, Phase 2 진행
```bash
cd /Users/cheollee/insurance-ontology-v2
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"

# Coverage Pipeline 실행
python -m ingestion.coverage_pipeline --carrier all
```

---

## 상세 복구 시나리오

### 시나리오 1: 작업 중 터미널 종료
**증상**: 터미널이 갑자기 닫힘, 명령어 실행 중단

**복구**:
```bash
# 1. 새 터미널 열기
cd /Users/cheollee/insurance-ontology-v2

# 2. 환경변수 재설정
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"

# 3. Checkpoint 확인
cat data/checkpoints/phase1_progress.json

# 4. 재개
python3 scripts/batch_ingest.py --resume --batch-size 5
```

**Checkpoint 작동 원리**:
- 각 batch(5개 문서) 완료 후 자동 저장
- `--resume` 플래그로 이어서 진행
- 중복 처리 방지

---

### 시나리오 2: Docker 서비스 다운
**증상**: `connection refused`, `could not connect to server`

**복구**:
```bash
# 1. Docker 프로세스 확인
docker ps -a | grep -E "postgres|neo4j|qdrant"

# 2. 서비스 재시작
cd /Users/cheollee/insurance-ontology-claude-backup-2025-12-10
./scripts/start_hybrid_services.sh

# 3. 상태 확인 (30초 대기)
sleep 30
docker ps | grep -E "postgres|neo4j|qdrant"

# 4. DB 연결 테스트
psql postgresql://postgres:postgres@localhost:5432/insurance_ontology_test -c "SELECT 1;"

# 5. 작업 재개 (Step 4 참고)
```

---

### 시나리오 3: DB 데이터 손상/부분 완료
**증상**:
- Clause count가 이상함 (예: 40,000 vs 예상 80,682)
- 일부 문서만 처리됨 (예: 20/38)

**복구**:
```bash
# 1. 현재 상태 확인
psql postgresql://postgres:postgres@localhost:5432/insurance_ontology_test -c "
  SELECT COUNT(*) AS docs FROM document;
  SELECT COUNT(*) AS clauses FROM document_clause;
"

# 2. Checkpoint 확인
cat data/checkpoints/phase1_progress.json | grep completed | wc -l

# 3A. 부분 완료 → Resume
python3 scripts/batch_ingest.py --resume --batch-size 5

# 3B. 데이터 이상 → 초기화 후 재실행
docker exec -i $(docker ps -q -f name=insurance-postgres) \
  psql -U postgres -d insurance_ontology_test \
  -c "TRUNCATE TABLE document_clause, document CASCADE;"

rm -f data/checkpoints/phase1_progress.json

python3 scripts/batch_ingest.py --all --batch-size 5
```

---

### 시나리오 4: 디스크 공간 부족
**증상**: `No space left on device`, `disk full`

**복구**:
```bash
# 1. 공간 확인
df -h

# 2. Docker 정리
docker system prune -af --volumes
# ⚠️ 주의: 모든 unused Docker data 삭제

# 3. 로그 정리
rm -rf /Users/cheollee/insurance-ontology-v2/__pycache__
find /Users/cheollee/insurance-ontology-v2 -name "*.pyc" -delete

# 4. 작업 재개
```

---

### 시나리오 5: Python 패키지 오류
**증상**: `ModuleNotFoundError`, `ImportError`

**복구**:
```bash
# 1. 작업 디렉토리 확인
cd /Users/cheollee/insurance-ontology-v2
pwd
# Expected: /Users/cheollee/insurance-ontology-v2

# 2. 패키지 재설치
pip3 install -r requirements.txt

# 3. Python path 확인
python3 -c "import sys; print('\n'.join(sys.path))"

# 4. 모듈 import 테스트
python3 -c "from ingestion.ingest_v3 import DocumentIngestionPipeline; print('OK')"

# 5. 작업 재개
```

---

### 시나리오 6: Claude Code 세션 종료 후 재시작
**증상**: 이전 작업 내용을 모름

**복구 (이 가이드를 읽고 있는 Claude에게)**:
```bash
# 1. 현재 상태 파일 읽기
cat /Users/cheollee/insurance-ontology-v2/CURRENT_STATUS.md

# 2. 작업 디렉토리 확인
cd /Users/cheollee/insurance-ontology-v2
ls -la

# 3. DB 상태 확인
psql postgresql://postgres:postgres@localhost:5432/insurance_ontology_test \
  -c "SELECT COUNT(*) FROM document; SELECT COUNT(*) FROM document_clause; SELECT COUNT(DISTINCT structured_data->>'coverage_name') FROM document_clause WHERE clause_type='table_row';"

# 4. 결과 해석
# - documents: 38, clauses: ~80,682, coverages: 348 → Phase 1 완료
# - documents: 0 → Phase 1 미완료
# - coverage table에 데이터 있음 → Phase 2 진행 중

# 5. CURRENT_STATUS.md의 "다음 단계" 섹션 참고
```

---

## 핵심 파일 위치 (빠른 참조)

### 코드
```
/Users/cheollee/insurance-ontology-v2/ingestion/ingest_v3.py
/Users/cheollee/insurance-ontology-v2/ingestion/parsers/hybrid_parser_v2.py
/Users/cheollee/insurance-ontology-v2/ingestion/parsers/carrier_parsers/base_parser.py
/Users/cheollee/insurance-ontology-v2/scripts/batch_ingest.py
```

### 데이터
```
/Users/cheollee/insurance-ontology-v2/data/documents_metadata.json
/Users/cheollee/insurance-ontology-v2/data/checkpoints/phase1_progress.json
```

### 문서
```
/Users/cheollee/insurance-ontology-v2/CURRENT_STATUS.md     ← 가장 중요!
/Users/cheollee/insurance-ontology-v2/VALIDATION_MODES.md
/Users/cheollee/insurance-ontology-v2/RECOVERY_GUIDE.md    ← 본 문서
```

### Backup (참고용)
```
/Users/cheollee/insurance-ontology-claude-backup-2025-12-10/
```

---

## 상태 검증 명령어 모음

### Quick Health Check (한 번에 실행)
```bash
#!/bin/bash
echo "=== Docker Services ==="
docker ps | grep -E "postgres|neo4j|qdrant"

echo -e "\n=== Database Status ==="
psql postgresql://postgres:postgres@localhost:5432/insurance_ontology_test -c "
  SELECT 'Documents:' AS metric, COUNT(*)::TEXT AS value FROM document
  UNION ALL
  SELECT 'Clauses:', COUNT(*)::TEXT FROM document_clause
  UNION ALL
  SELECT 'Unique Coverages:', COUNT(DISTINCT structured_data->>'coverage_name')::TEXT
  FROM document_clause WHERE clause_type='table_row';"

echo -e "\n=== Checkpoint Status ==="
if [ -f data/checkpoints/phase1_progress.json ]; then
    echo "Checkpoint exists:"
    cat data/checkpoints/phase1_progress.json | grep -E "completed|failed|last_updated"
else
    echo "No checkpoint found"
fi

echo -e "\n=== Work Directory ==="
pwd
ls -la | head -10
```

**저장**:
```bash
# 위 스크립트를 파일로 저장
cat > /Users/cheollee/insurance-ontology-v2/scripts/health_check.sh << 'EOF'
[위 스크립트 내용 복사]
EOF

chmod +x /Users/cheollee/insurance-ontology-v2/scripts/health_check.sh

# 실행
cd /Users/cheollee/insurance-ontology-v2
./scripts/health_check.sh
```

---

## 예상 결과 (정상 상태)

### Phase 1 완료 (NORMAL Mode)
```
=== Docker Services ===
insurance-postgres    Up 4 hours    5432/tcp
insurance-neo4j       Up 4 hours    7474/tcp, 7687/tcp
insurance-qdrant      Up 4 hours    6333-6334/tcp

=== Database Status ===
metric              | value
--------------------+-------
Documents:          | 38
Clauses:            | 80682
Unique Coverages:   | 348

=== Checkpoint Status ===
Checkpoint exists:
  "completed": [38 items]
  "failed": []
  "last_updated": "2025-12-11T01:10:44.057854"

=== Work Directory ===
/Users/cheollee/insurance-ontology-v2
```

---

## 긴급 연락처 (자가 진단)

### 문제별 해결 우선순위

| 문제 | 심각도 | 복구 시간 | 해결 방법 |
|------|--------|----------|-----------|
| 터미널 종료 | 낮음 | 1분 | `--resume` 실행 |
| Docker 다운 | 중간 | 3분 | `start_hybrid_services.sh` |
| DB 손상 | 중간 | 10분 | TRUNCATE + 재실행 |
| 패키지 오류 | 낮음 | 2분 | `pip install -r requirements.txt` |
| 디스크 부족 | 높음 | 5분 | `docker prune` |
| 세션 종료 | 낮음 | 5분 | `CURRENT_STATUS.md` 읽기 |

---

## 최악의 시나리오: 전체 재구성

**모든 것이 망가진 경우**:
```bash
# 1. Backup에서 복원
cd /Users/cheollee
cp -r insurance-ontology-claude-backup-2025-12-10 insurance-ontology-v2-recovery
cd insurance-ontology-v2-recovery

# 2. Clean v2 파일만 복사
mkdir -p temp-clean
cd temp-clean

# 핵심 파일 복사 (insurance-ontology-v2에서)
cp -r /Users/cheollee/insurance-ontology-v2/ingestion/parsers/hybrid_parser_v2.py ./
cp -r /Users/cheollee/insurance-ontology-v2/ingestion/parsers/carrier_parsers ./
cp /Users/cheollee/insurance-ontology-v2/ingestion/ingest_v3.py ./
cp /Users/cheollee/insurance-ontology-v2/scripts/batch_ingest.py ./

# 3. Docker 재시작
./scripts/start_hybrid_services.sh

# 4. DB 초기화
docker exec -i $(docker ps -q -f name=postgres) \
  psql -U postgres -d insurance_ontology_test \
  -c "TRUNCATE TABLE document_clause, document CASCADE;"

# 5. 재실행
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"
python3 scripts/batch_ingest.py --all --batch-size 5
```

**소요 시간**: 약 15-20분 (ingestion 10분 포함)

---

## 자주 묻는 질문 (FAQ)

### Q1: Checkpoint가 있는데 재실행하면 중복될까?
**A**: 아니요. `--resume` 플래그 사용 시 이미 완료된 문서는 skip합니다.

### Q2: STRICT 모드로 바꾸면 기존 데이터는?
**A**: DB TRUNCATE 후 재실행 필요. 기존 데이터는 자동으로 대체되지 않습니다.

### Q3: Phase 2 중에 시스템 다운되면?
**A**: Phase 2는 carrier별로 실행 가능. 예: `--carrier lotte`로 부분 실행 후 재개.

### Q4: 여러 디렉토리가 있는데 어느 것을 사용?
**A**:
- 작업용: `insurance-ontology-v2/` ← 이것만 사용
- Backup: `insurance-ontology-claude-backup-2025-12-10/` ← 참고/복원용

### Q5: 작업 중 어디까지 완료되었는지 모를 때?
**A**: `CURRENT_STATUS.md` 읽고 → DB 상태 확인 → 다음 단계 실행

---

## 체크리스트 (프린트 가능)

**시스템 다운 시 순서대로 실행**:

```
□ 1. Docker 서비스 확인
    docker ps | grep postgres

□ 2. DB 연결 테스트
    psql $POSTGRES_URL -c "SELECT 1;"

□ 3. 데이터 확인
    psql $POSTGRES_URL -c "SELECT COUNT(*) FROM document;"

□ 4. Checkpoint 확인
    cat data/checkpoints/phase1_progress.json

□ 5. 작업 재개
    python3 scripts/batch_ingest.py --resume

□ 6. 결과 확인
    psql $POSTGRES_URL -c "SELECT COUNT(DISTINCT structured_data->>'coverage_name') FROM document_clause WHERE clause_type='table_row';"
```

---

**마지막 업데이트**: 2025-12-11 01:20 KST
**작성자**: Claude (for future Claude sessions)
**목적**: 빠른 복구 및 작업 재개
