"""add content_length to chapters for stream reconnect

Revision ID: ce0b5e4d2b89
Revises: bc66b51d9f4f
Create Date: 2025-09-30 14:16:44.874163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce0b5e4d2b89'
down_revision: Union[str, Sequence[str], None] = 'bc66b51d9f4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 添加content_length字段(先允许NULL)
    op.add_column('chapters', sa.Column('content_length', sa.Integer(), nullable=True))

    # 2. 初始化已存在章节的content_length值
    from sqlalchemy import text
    op.execute(text("""
        UPDATE chapters
        SET content_length = COALESCE(LENGTH(content), 0)
        WHERE content_length IS NULL
    """))

    # 3. 设置为NOT NULL并添加默认值
    op.alter_column('chapters', 'content_length',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='0')


def downgrade() -> None:
    """Downgrade schema."""
    # 删除content_length字段
    op.drop_column('chapters', 'content_length')
