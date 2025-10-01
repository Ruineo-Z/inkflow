"""fix_chapter_status_enum_type

Revision ID: 07f492baa56a
Revises: ce0b5e4d2b89
Create Date: 2025-10-01 09:41:46.117197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07f492baa56a'
down_revision: Union[str, Sequence[str], None] = 'ce0b5e4d2b89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: 修复章节status字段类型为枚举"""

    # 1. 创建PostgreSQL枚举类型
    op.execute("CREATE TYPE chapterstatus AS ENUM ('generating', 'completed', 'failed')")

    # 2. 删除现有默认值
    op.execute("ALTER TABLE chapters ALTER COLUMN status DROP DEFAULT")

    # 3. 修改列类型为枚举,使用USING子句进行类型转换
    op.execute("""
        ALTER TABLE chapters
        ALTER COLUMN status TYPE chapterstatus
        USING status::text::chapterstatus
    """)

    # 4. 设置新的默认值为枚举值
    op.execute("ALTER TABLE chapters ALTER COLUMN status SET DEFAULT 'completed'::chapterstatus")


def downgrade() -> None:
    """Downgrade schema: 回退status字段为VARCHAR"""

    # 1. 修改列类型回VARCHAR
    op.execute("""
        ALTER TABLE chapters
        ALTER COLUMN status TYPE VARCHAR(20)
        USING status::text
    """)

    # 2. 恢复默认值
    op.execute("ALTER TABLE chapters ALTER COLUMN status SET DEFAULT 'completed'")

    # 3. 删除枚举类型
    op.execute("DROP TYPE chapterstatus")
