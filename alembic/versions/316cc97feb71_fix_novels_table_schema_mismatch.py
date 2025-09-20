"""fix novels table schema mismatch

Revision ID: 316cc97feb71
Revises: add_option_tags_system
Create Date: 2025-09-20 22:13:40.835892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '316cc97feb71'
down_revision: Union[str, Sequence[str], None] = 'add_option_tags_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加novels表缺失的字段
    op.add_column('novels', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('novels', sa.Column('theme', sa.String(50), nullable=False, server_default='modern'))
    op.add_column('novels', sa.Column('status', sa.String(20), nullable=False, server_default='draft'))
    op.add_column('novels', sa.Column('background_setting', sa.Text(), nullable=True))
    op.add_column('novels', sa.Column('character_setting', sa.Text(), nullable=True))
    op.add_column('novels', sa.Column('outline', sa.Text(), nullable=True))

    # 删除旧的字段名（如果存在）
    try:
        op.drop_column('novels', 'world_setting')
    except:
        pass
    try:
        op.drop_column('novels', 'protagonist_info')
    except:
        pass
    try:
        op.drop_column('novels', 'total_chapters')
    except:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # 回滚操作：删除新添加的字段
    op.drop_column('novels', 'outline')
    op.drop_column('novels', 'character_setting')
    op.drop_column('novels', 'background_setting')
    op.drop_column('novels', 'status')
    op.drop_column('novels', 'theme')
    op.drop_column('novels', 'description')

    # 恢复旧字段（如果需要）
    op.add_column('novels', sa.Column('world_setting', sa.Text(), nullable=True))
    op.add_column('novels', sa.Column('protagonist_info', sa.Text(), nullable=True))
    op.add_column('novels', sa.Column('total_chapters', sa.Integer(), nullable=True))
