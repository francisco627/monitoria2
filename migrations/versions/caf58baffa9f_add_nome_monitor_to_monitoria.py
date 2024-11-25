"""Add nome_monitor to Monitoria

Revision ID: caf58baffa9f
Revises: 5310b18f5a44
Create Date: 2024-11-25 09:07:52.922307

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'caf58baffa9f'
down_revision = '5310b18f5a44'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('monitoria', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nome_monitor', sa.String(length=100), nullable=True))

    # Atualizar registros existentes para evitar problemas com NOT NULL
    op.execute("UPDATE monitoria SET nome_monitor = 'Desconhecido' WHERE nome_monitor IS NULL")

    with op.batch_alter_table('monitoria', schema=None) as batch_op:
        batch_op.alter_column('nome_monitor', nullable=False)  # Tornar a coluna obrigatória
