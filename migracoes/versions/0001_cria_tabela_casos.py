"""Cria a tabela de casos descritos pelos estudantes (etapa A).

Revisão: 0001
Anterior: nenhuma
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "casos",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("codigo", sa.String(16), nullable=False, unique=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("descricao", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("anonimizacao", sa.JSON(), nullable=False),
        sa.Column("consentimento", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="recebido"),
        sa.Column("validado_em", sa.DateTime(), nullable=True),
        sa.Column("fatos", sa.JSON(), nullable=True),
        sa.Column("resultado", sa.JSON(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_casos_status_criado_em", "casos", ["status", "criado_em"])


def downgrade() -> None:
    op.drop_index("ix_casos_status_criado_em", table_name="casos")
    op.drop_table("casos")
