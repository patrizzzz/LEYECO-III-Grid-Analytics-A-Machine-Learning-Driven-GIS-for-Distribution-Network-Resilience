"""Merge migration heads

Revision ID: 421aca01d29e
Revises: add_coordinates_to_lines, add_dist_transformer, add_secondary_extra
Create Date: 2026-02-25 11:41:02.370067

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '421aca01d29e'
down_revision = ('add_coordinates_to_lines', 'add_dist_transformer', 'add_secondary_extra')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
