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
    import logging
    logger = logging.getLogger(__name__)

    try:
        op.drop_column('novels', 'world_setting')
    except Exception as e:
        logger.warning(f"删除字段world_setting失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'protagonist_info')
    except Exception as e:
        logger.warning(f"删除字段protagonist_info失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'total_chapters')
    except Exception as e:
        logger.warning(f"删除字段total_chapters失败（可能不存在）: {e}")


def downgrade() -> None:
    """Downgrade schema."""
    import logging
    logger = logging.getLogger(__name__)

    # 回滚操作：删除新添加的字段
    try:
        op.drop_column('novels', 'outline')
    except Exception as e:
        logger.warning(f"删除字段outline失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'character_setting')
    except Exception as e:
        logger.warning(f"删除字段character_setting失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'background_setting')
    except Exception as e:
        logger.warning(f"删除字段background_setting失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'status')
    except Exception as e:
        logger.warning(f"删除字段status失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'theme')
    except Exception as e:
        logger.warning(f"删除字段theme失败（可能不存在）: {e}")
    try:
        op.drop_column('novels', 'description')
    except Exception as e:
        logger.warning(f"删除字段description失败（可能不存在）: {e}")

    # 恢复旧字段（如果需要）
    try:
        op.add_column('novels', sa.Column('world_setting', sa.Text(), nullable=True))
    except Exception as e:
        logger.warning(f"添加字段world_setting失败（可能已存在）: {e}")
    try:
        op.add_column('novels', sa.Column('protagonist_info', sa.Text(), nullable=True))
    except Exception as e:
        logger.warning(f"添加字段protagonist_info失败（可能已存在）: {e}")
    try:
        op.add_column('novels', sa.Column('total_chapters', sa.Integer(), nullable=True))
    except Exception as e:
        logger.warning(f"添加字段total_chapters失败（可能已存在）: {e}")
