"""initial_schema_baseline

Revision ID: dafe7c48833f
Revises:
Create Date: 2025-12-13 13:32:34.087992

이 마이그레이션은 "baseline"입니다.
- 기존 운영 DB에서 pg_dump로 추출한 스키마를 기준점으로 설정
- 실제 스키마 생성은 001_initial_schema.sql에서 수행
- 이 마이그레이션은 Alembic 버전 추적의 시작점 역할만 함
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dafe7c48833f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline 마이그레이션 - 아무 작업도 수행하지 않음.

    스키마는 다음 방법으로 적용됨:
    1. Docker: /docker-entrypoint-initdb.d/001_initial_schema.sql (자동)
    2. 수동: psql -f postgres/001_initial_schema.sql

    이 마이그레이션은 Alembic 버전 추적 시작점만 표시.
    """
    pass


def downgrade() -> None:
    """
    Baseline 마이그레이션 - 롤백 시 아무 작업도 수행하지 않음.

    주의: 전체 스키마를 삭제하려면 수동으로 DROP 해야 함.
    """
    pass
