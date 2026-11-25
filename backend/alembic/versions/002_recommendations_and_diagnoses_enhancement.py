"""recommendations and diagnoses enhancement

Revision ID: 002_recommendations_and_diagnoses_enhancement
Revises: 001_initial_schema
Create Date: 2026-11-23 12:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_recommendations_and_diagnoses_enhancement'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ai_diagnoses additions
    op.add_column('ai_diagnoses', sa.Column('missing_information', sa.JSON(), nullable=True))
    op.add_column('ai_diagnoses', sa.Column('recommended_investigation', sa.JSON(), nullable=True))

    # recommendations additions
    op.add_column('recommendations', sa.Column('title', sa.String(length=255), nullable=False, server_default=''))
    op.add_column('recommendations', sa.Column('target_stage', sa.String(length=50), nullable=False, server_default='product_page'))
    op.add_column('recommendations', sa.Column('expected_direction', sa.String(length=20), nullable=False, server_default='increase'))
    op.add_column('recommendations', sa.Column('potential_impact_estimate', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('recommendations', sa.Column('implementation_effort', sa.String(length=20), nullable=False, server_default='medium'))
    op.add_column('recommendations', sa.Column('confidence_level', sa.String(length=20), nullable=False, server_default='medium'))
    op.add_column('recommendations', sa.Column('priority_score', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('recommendations', sa.Column('priority_breakdown', sa.JSON(), nullable=True))
    op.add_column('recommendations', sa.Column('risks_or_prerequisites', sa.JSON(), nullable=True))
    op.add_column('recommendations', sa.Column('merchant_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    # recommendations removals
    op.drop_column('recommendations', 'merchant_notes')
    op.drop_column('recommendations', 'risks_or_prerequisites')
    op.drop_column('recommendations', 'priority_breakdown')
    op.drop_column('recommendations', 'priority_score')
    op.drop_column('recommendations', 'confidence_level')
    op.drop_column('recommendations', 'implementation_effort')
    op.drop_column('recommendations', 'potential_impact_estimate')
    op.drop_column('recommendations', 'expected_direction')
    op.drop_column('recommendations', 'target_stage')
    op.drop_column('recommendations', 'title')

    # ai_diagnoses removals
    op.drop_column('ai_diagnoses', 'recommended_investigation')
    op.drop_column('ai_diagnoses', 'missing_information')
