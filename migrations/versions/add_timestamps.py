"""Add missing timestamp columns to post table

Revision ID: add_timestamps
Revises: add_infrastructure_data
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_timestamps'
down_revision = 'add_infrastructure_data'
branch_labels = None
depends_on = None


def upgrade():
    # Columns were added in add_infrastructure_data, here we just ensure defaults
    op.alter_column('post', 'created_at', server_default=sa.func.now())
    op.alter_column('post', 'updated_at', server_default=sa.func.now())


def downgrade():
    op.alter_column('post', 'updated_at', server_default=None)
    op.alter_column('post', 'created_at', server_default=None)
