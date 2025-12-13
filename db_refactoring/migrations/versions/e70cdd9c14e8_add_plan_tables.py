"""add_plan_tables

Revision ID: e70cdd9c14e8
Revises: b3192d16d07b
Create Date: 2025-12-13

온톨로지 확장 - Plan 엔티티:
- plan: 가입설계 (보험 상품 설계 결과)
- plan_coverage: Plan-Coverage 다대다 관계 (선택된 담보와 가입금액)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e70cdd9c14e8'
down_revision: Union[str, Sequence[str], None] = 'b3192d16d07b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Plan 관련 테이블 생성:
    1. plan - 가입설계서 기반 보험 설계 정보
    2. plan_coverage - Plan과 Coverage의 다대다 관계 (가입금액 포함)
    """
    # 1. plan 테이블
    op.create_table(
        'plan',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('document.id', ondelete='CASCADE'), nullable=True,
                  comment='연결된 가입설계서 문서'),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('product.id', ondelete='CASCADE'), nullable=False,
                  comment='상품'),
        sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variant.id', ondelete='SET NULL'), nullable=True,
                  comment='상품 변형 (성별/연령 변형)'),
        sa.Column('plan_name', sa.String(200), nullable=True,
                  comment='설계 이름 (예: 삼성화재 마이헬스파트너 남성 40세)'),
        sa.Column('target_gender', sa.String(10), nullable=True,
                  comment='대상 성별 (male, female)'),
        sa.Column('target_age', sa.Integer(), nullable=True,
                  comment='대상 나이'),
        sa.Column('insurance_period', sa.String(50), nullable=True,
                  comment='보험기간 (예: 80세만기, 100세만기, 20년)'),
        sa.Column('payment_period', sa.String(50), nullable=True,
                  comment='납입기간 (예: 20년납, 전기납)'),
        sa.Column('payment_cycle', sa.String(20), nullable=True,
                  comment='납입주기 (월납, 연납)'),
        sa.Column('total_premium', sa.Numeric(15, 2), nullable=True,
                  comment='총 보험료'),
        sa.Column('attributes', postgresql.JSONB(), nullable=True,
                  comment='추가 속성 (JSON)'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_plan_product_id', 'plan', ['product_id'])
    op.create_index('ix_plan_document_id', 'plan', ['document_id'])
    op.create_index('ix_plan_target_gender', 'plan', ['target_gender'])
    op.create_index('ix_plan_target_age', 'plan', ['target_age'])

    # 2. plan_coverage 연결 테이블 (다대다 + 가입금액)
    op.create_table(
        'plan_coverage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('plan.id', ondelete='CASCADE'), nullable=False),
        sa.Column('coverage_id', sa.Integer(), sa.ForeignKey('coverage.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sum_insured', sa.Numeric(15, 2), nullable=True,
                  comment='가입금액 (예: 30000000 = 3천만원)'),
        sa.Column('sum_insured_text', sa.String(100), nullable=True,
                  comment='가입금액 텍스트 (예: 3,000만원)'),
        sa.Column('premium', sa.Numeric(12, 2), nullable=True,
                  comment='해당 담보 보험료'),
        sa.Column('is_basic', sa.Boolean(), default=False,
                  comment='기본 담보 여부'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('plan_id', 'coverage_id', name='uq_plan_coverage'),
    )
    op.create_index('ix_plan_coverage_plan_id', 'plan_coverage', ['plan_id'])
    op.create_index('ix_plan_coverage_coverage_id', 'plan_coverage', ['coverage_id'])


def downgrade() -> None:
    """Plan 관련 테이블 삭제 (역순)"""
    op.drop_table('plan_coverage')
    op.drop_table('plan')
