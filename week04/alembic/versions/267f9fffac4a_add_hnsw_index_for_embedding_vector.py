"""add hnsw index for embedding vector

Revision ID: 267f9fffac4a
Revises: 696c7703b58b
Create Date: 2026-06-18 14:26:32.060043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '267f9fffac4a'
down_revision: Union[str, Sequence[str], None] = '696c7703b58b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:  # 定义数据库升级逻辑，执行 alembic upgrade 时会运行这里
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_vector_hnsw
        ON document_chunks
        USING hnsw (embedding_vector vector_cosine_ops)
        """
    )  # 给 document_chunks.embedding_vector 创建 HNSW 向量索引，加速余弦距离 top_k 检索


def downgrade() -> None:  # 定义数据库回滚逻辑，执行 alembic downgrade 时会运行这里
    op.execute("""
        DROP INDEX IF EXISTS idx_document_chunks_embedding_vector_hnsw
        """)  # 回滚时删除 document_chunks.embedding_vector 上的 HNSW 向量索引
