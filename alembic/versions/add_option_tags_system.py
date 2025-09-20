"""添加选项标签体系和用户偏好分析

Revision ID: add_option_tags_system
Revises: [最新的revision_id]
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

    # 创建用户偏好表
    op.create_table('user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('risk_preference', sa.Float(), nullable=True, default=0.5),
        sa.Column('exploration_desire', sa.Float(), nullable=True, default=0.5),
        sa.Column('pacing_preference', sa.Float(), nullable=True, default=0.5),
        sa.Column('relationship_focus', sa.Float(), nullable=True, default=0.5),
        sa.Column('action_orientation', sa.Float(), nullable=True, default=0.5),
        sa.Column('preferred_action_types', sa.JSON(), nullable=True),
        sa.Column('preferred_narrative_impacts', sa.JSON(), nullable=True),
        sa.Column('preferred_emotional_tones', sa.JSON(), nullable=True),
        sa.Column('total_choices', sa.Integer(), nullable=True, default=0),
        sa.Column('confidence_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_user_preferences_id'), 'user_preferences', ['id'], unique=False)

    # 创建用户选择分析表
    op.create_table('user_choice_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('option_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('choice_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('risk_weight', sa.Float(), nullable=True),
        sa.Column('exploration_weight', sa.Float(), nullable=True),
        sa.Column('pacing_weight', sa.Float(), nullable=True),
        sa.Column('action_weight', sa.Float(), nullable=True),
        sa.Column('selected_action_type', sa.String(20), nullable=True),
        sa.Column('selected_narrative_impact', sa.String(20), nullable=True),
        sa.Column('selected_emotional_tone', sa.String(20), nullable=True),
        sa.Column('choice_response_time', sa.Float(), nullable=True),
        sa.Column('alternative_options_viewed', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ),
        sa.ForeignKeyConstraint(['option_id'], ['options.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_choice_analytics_id'), 'user_choice_analytics', ['id'], unique=False)


def downgrade() -> None:
    # 删除新建的表
    op.drop_index(op.f('ix_user_choice_analytics_id'), table_name='user_choice_analytics')
    op.drop_table('user_choice_analytics')
    op.drop_index(op.f('ix_user_preferences_id'), table_name='user_preferences')
    op.drop_table('user_preferences')

    # 删除options表的新字段
    op.drop_column('options', 'weight_factors')
    op.drop_column('options', 'emotional_tone')
    op.drop_column('options', 'pacing')
    op.drop_column('options', 'character_focus')
    op.drop_column('options', 'narrative_impact')
    op.drop_column('options', 'action_type')