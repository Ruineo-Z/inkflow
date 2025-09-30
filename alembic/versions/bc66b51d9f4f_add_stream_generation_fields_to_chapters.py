"""add_stream_generation_fields_to_chapters

Revision ID: bc66b51d9f4f
Revises: 316cc97feb71
Create Date: 2025-09-30 12:22:14.189264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc66b51d9f4f'
down_revision: Union[str, Sequence[str], None] = '316cc97feb71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - 添加流式生成相关字段（保证数据不丢失）"""
    # 添加新字段，所有字段都允许NULL或有默认值，确保现有数据不受影响

    # 1. status字段：默认值为'completed'，表示已有章节都是完成状态
    op.add_column('chapters', sa.Column('status', sa.String(length=20), nullable=False, server_default='completed'))

    # 2. session_id字段：允许NULL，已有章节不需要此字段
    op.add_column('chapters', sa.Column('session_id', sa.String(length=100), nullable=True))

    # 3. generation_started_at字段：允许NULL，已有章节不需要此字段
    op.add_column('chapters', sa.Column('generation_started_at', sa.DateTime(timezone=True), nullable=True))

    # 4. generation_completed_at字段：允许NULL，已有章节不需要此字段
    op.add_column('chapters', sa.Column('generation_completed_at', sa.DateTime(timezone=True), nullable=True))

    # 为status字段添加索引，提升查询性能
    op.create_index(op.f('ix_chapters_status'), 'chapters', ['status'], unique=False)

    # 为session_id字段添加索引，用于快速查找生成中的章节
    op.create_index(op.f('ix_chapters_session_id'), 'chapters', ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - 安全回滚，删除新增字段"""
    # 删除索引
    op.drop_index(op.f('ix_chapters_session_id'), table_name='chapters')
    op.drop_index(op.f('ix_chapters_status'), table_name='chapters')

    # 删除列（数据会丢失，但原有的content、title等核心数据保留）
    op.drop_column('chapters', 'generation_completed_at')
    op.drop_column('chapters', 'generation_started_at')
    op.drop_column('chapters', 'session_id')
    op.drop_column('chapters', 'status')
