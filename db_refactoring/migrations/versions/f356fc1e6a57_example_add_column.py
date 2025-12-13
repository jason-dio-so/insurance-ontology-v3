"""example_add_column

Revision ID: f356fc1e6a57
Revises: dafe7c48833f
Create Date: 2025-12-13

예시 마이그레이션 - 향후 스키마 변경 시 템플릿으로 사용
이 마이그레이션은 테스트 목적이며, 실제 스키마 변경 예시를 보여줍니다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f356fc1e6a57'
down_revision: Union[str, Sequence[str], None] = 'dafe7c48833f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    예시: coverage 테이블에 notes 컬럼 추가

    사용법:
        alembic upgrade head
    """
    op.add_column('coverage', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """
    예시: coverage 테이블에서 notes 컬럼 제거

    사용법:
        alembic downgrade -1
    """
    op.drop_column('coverage', 'notes')
