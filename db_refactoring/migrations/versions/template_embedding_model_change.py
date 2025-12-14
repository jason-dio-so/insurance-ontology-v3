"""
임베딩 모델 변경 마이그레이션 템플릿

이 파일은 임베딩 모델 변경 시 사용하는 Alembic 마이그레이션 템플릿입니다.
실제 사용 시 파일명을 변경하고 revision ID를 생성하세요.

사용 방법:
1. 이 파일을 복사하여 새 마이그레이션 파일 생성
2. revision, down_revision 수정
3. OLD_DIMENSION, NEW_DIMENSION, NEW_MODEL_NAME 수정
4. alembic upgrade head 실행

주의사항:
- 이 마이그레이션은 기존 임베딩 데이터를 삭제합니다
- 마이그레이션 후 임베딩 재생성 필요 (python -m vector_index.build_index)
- 대량 데이터의 경우 다운타임 발생 가능

Revision ID: XXXXXX (수정 필요)
Revises: (이전 revision 입력)
Create Date: 2025-12-14
"""

from alembic import op
import sqlalchemy as sa

# ============================================================================
# 설정 (수정 필요)
# ============================================================================

# revision identifiers
revision = 'XXXXXX'  # TODO: 'alembic revision' 명령어로 생성된 ID 사용
down_revision = None  # TODO: 이전 마이그레이션 revision 입력
branch_labels = None
depends_on = None

# 임베딩 설정
OLD_DIMENSION = 1536  # 현재 차원 (OpenAI ada-002 / text-embedding-3-small)
NEW_DIMENSION = 384   # 새 차원 (예: BGE-Small)
NEW_MODEL_NAME = 'bge-small-en-v1.5'  # 새 모델명

# ============================================================================
# 마이그레이션
# ============================================================================


def upgrade():
    """
    임베딩 모델 변경 (차원 변경 포함)

    단계:
    1. 기존 인덱스 삭제
    2. 기존 임베딩 데이터 백업 (선택)
    3. embedding 컬럼 차원 변경
    4. 새 인덱스 생성
    5. model_name 업데이트
    """

    # 1. 기존 HNSW 인덱스 삭제
    op.execute("DROP INDEX IF EXISTS idx_clause_embedding_hnsw")

    # 2. 기존 임베딩 데이터 삭제 (차원 변경 시 필수)
    # 주의: 이 작업은 되돌릴 수 없습니다!
    op.execute("DELETE FROM clause_embedding")

    # 3. embedding 컬럼 차원 변경
    op.execute(f"""
        ALTER TABLE clause_embedding
        ALTER COLUMN embedding TYPE vector({NEW_DIMENSION})
    """)

    # 4. 새 HNSW 인덱스 생성
    # 차원이 작으면 m 값도 조정 가능 (선택)
    op.execute(f"""
        CREATE INDEX idx_clause_embedding_hnsw
        ON clause_embedding
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # 5. 컬럼 코멘트 업데이트
    op.execute(f"""
        COMMENT ON COLUMN clause_embedding.embedding IS
        '벡터 임베딩 ({NEW_DIMENSION}차원, 모델: {NEW_MODEL_NAME})'
    """)

    print(f"""
    ============================================================
    임베딩 모델 변경 완료
    ============================================================
    - 이전 차원: {OLD_DIMENSION}
    - 새 차원: {NEW_DIMENSION}
    - 새 모델: {NEW_MODEL_NAME}

    다음 단계:
    1. 임베딩 재생성: python -m vector_index.build_index
    2. 검증: python db_refactoring/scripts/monitor_vector_search.py --stats
    ============================================================
    """)


def downgrade():
    """
    롤백: 원래 차원으로 복원

    주의: 이 작업도 임베딩 데이터를 삭제합니다!
    """

    # 1. 인덱스 삭제
    op.execute("DROP INDEX IF EXISTS idx_clause_embedding_hnsw")

    # 2. 임베딩 데이터 삭제
    op.execute("DELETE FROM clause_embedding")

    # 3. 원래 차원으로 복원
    op.execute(f"""
        ALTER TABLE clause_embedding
        ALTER COLUMN embedding TYPE vector({OLD_DIMENSION})
    """)

    # 4. 원래 인덱스 재생성
    op.execute(f"""
        CREATE INDEX idx_clause_embedding_hnsw
        ON clause_embedding
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # 5. 코멘트 복원
    op.execute(f"""
        COMMENT ON COLUMN clause_embedding.embedding IS
        '벡터 임베딩 ({OLD_DIMENSION}차원)'
    """)

    print(f"""
    ============================================================
    롤백 완료
    ============================================================
    - 차원 복원: {OLD_DIMENSION}

    다음 단계:
    1. 임베딩 재생성 필요: python -m vector_index.build_index
    ============================================================
    """)


# ============================================================================
# 임베딩 모델 변경 체크리스트
# ============================================================================
"""
## 마이그레이션 전

- [ ] 현재 임베딩 수 확인
      SELECT COUNT(*) FROM clause_embedding;

- [ ] 현재 모델 확인
      SELECT DISTINCT model_name FROM clause_embedding;

- [ ] 백업 필요 여부 결정
      - 임베딩 재생성이 비용이 큰 경우 (유료 API 등)
      - 롤백 가능성이 있는 경우

- [ ] 새 모델 테스트
      - 소규모 데이터로 품질 테스트
      - 검색 정확도 비교


## 마이그레이션 실행

- [ ] 점검 시간 공지 (다운타임 예상)

- [ ] 마이그레이션 실행
      alembic upgrade head

- [ ] 임베딩 재생성
      python -m vector_index.build_index

- [ ] 모니터링
      python db_refactoring/scripts/monitor_vector_search.py --benchmark


## 마이그레이션 후

- [ ] 임베딩 수 확인
      SELECT COUNT(*) FROM clause_embedding;

- [ ] 검색 품질 테스트
      - 주요 쿼리 테스트
      - 검색 정확도 확인

- [ ] 성능 벤치마크
      python db_refactoring/scripts/monitor_vector_search.py --benchmark --save

- [ ] 문서 업데이트
      - PGVECTOR_GUIDE.md 현재 설정 섹션 업데이트
"""
