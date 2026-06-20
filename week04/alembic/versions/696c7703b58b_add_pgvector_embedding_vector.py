"""add pgvector embedding vector

Revision ID: 696c7703b58b
Revises: 8ab241e6321c
Create Date: 2026-06-18 14:05:31.323812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '696c7703b58b'
down_revision: Union[str, Sequence[str], None] = '8ab241e6321c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:  # 定义数据库升级逻辑，执行 alembic upgrade 时会运行这里
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )  # 启用 PostgreSQL 的 pgvector 扩展，如果已经存在就不会重复创建

    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN IF NOT EXISTS embedding_vector vector(1024)
        """
    )  # 给 document_chunks 表新增 embedding_vector 字段，用来保存真实 embedding 向量


def downgrade() -> None:  # 定义数据库回滚逻辑，执行 alembic downgrade 时会运行这里
    op.execute("""
        ALTER TABLE document_chunks
        DROP COLUMN IF EXISTS embedding_vector
        """)  # 回滚时删除 document_chunks 表里的 embedding_vector 字段
