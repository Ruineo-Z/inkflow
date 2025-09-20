"""添加选项标签体系

Revision ID: add_option_tags_system
Revises: e23315eafbc7
Create Date: 2025-09-20 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_option_tags_system'
down_revision: Union[str, None] = 'e23315eafbc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为options表添加标签字段
    op.add_column('options', sa.Column('action_type', sa.String(20), nullable=True))
    op.add_column('options', sa.Column('narrative_impact', sa.String(20), nullable=True))
    op.add_column('options', sa.Column('character_focus', sa.String(20), nullable=True))
    op.add_column('options', sa.Column('pacing', sa.String(10), nullable=True))
    op.add_column('options', sa.Column('emotional_tone', sa.String(20), nullable=True))
    op.add_column('options', sa.Column('weight_factors', sa.JSON(), nullable=True))


def downgrade() -> None:
    # 删除options表的新字段
    op.drop_column('options', 'weight_factors')
    op.drop_column('options', 'emotional_tone')
    op.drop_column('options', 'pacing')
    op.drop_column('options', 'character_focus')
    op.drop_column('options', 'narrative_impact')
    op.drop_column('options', 'action_type')