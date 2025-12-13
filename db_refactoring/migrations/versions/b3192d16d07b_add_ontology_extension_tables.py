"""add_ontology_extension_tables

Revision ID: b3192d16d07b
Revises: f356fc1e6a57
Create Date: 2025-12-13 14:59:36.923638

온톨로지 확장 테이블 추가:
- risk_event: 보험금 지급 사유 (위험 이벤트)
- benefit_risk_event: Benefit-RiskEvent 다대다 관계

참고: condition, exclusion 테이블은 이미 존재함 (001_initial_schema.sql에서 생성)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3192d16d07b'
down_revision: Union[str, Sequence[str], None] = 'f356fc1e6a57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    온톨로지 확장 테이블 생성:
    1. risk_event - 보험금 지급 사유 (진단, 수술, 입원, 사망 등)
    2. benefit_risk_event - Benefit↔RiskEvent 다대다 관계

    참고: condition, exclusion 테이블은 이미 001_initial_schema.sql에서 생성됨
    """
    # 1. risk_event 테이블
    op.create_table(
        'risk_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(50), nullable=False,
                  comment='diagnosis, surgery, hospitalization, death, disability, treatment'),
        sa.Column('event_name', sa.String(200), nullable=False,
                  comment='암진단, 뇌졸중진단, 급성심근경색진단, 수술, 입원, 사망 등'),
        sa.Column('severity_level', sa.String(20), nullable=True,
                  comment='critical, major, minor, mild'),
        sa.Column('icd_code_pattern', sa.String(100), nullable=True,
                  comment='ICD 코드 패턴 (C00-C97, K35.*, I60-I69 등)'),
        sa.Column('description', sa.Text(), nullable=True,
                  comment='상세 설명'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_risk_event_event_type', 'risk_event', ['event_type'])
    op.create_index('ix_risk_event_event_name', 'risk_event', ['event_name'])

    # 2. benefit_risk_event 연결 테이블 (다대다)
    op.create_table(
        'benefit_risk_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('benefit_id', sa.Integer(), sa.ForeignKey('benefit.id', ondelete='CASCADE'), nullable=False),
        sa.Column('risk_event_id', sa.Integer(), sa.ForeignKey('risk_event.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('benefit_id', 'risk_event_id', name='uq_benefit_risk_event'),
    )
    op.create_index('ix_benefit_risk_event_benefit_id', 'benefit_risk_event', ['benefit_id'])
    op.create_index('ix_benefit_risk_event_risk_event_id', 'benefit_risk_event', ['risk_event_id'])


def downgrade() -> None:
    """온톨로지 확장 테이블 삭제 (역순)"""
    # 연결 테이블 먼저 삭제
    op.drop_table('benefit_risk_event')

    # risk_event 테이블 삭제
    op.drop_table('risk_event')
