"""Add installation_type, conductor fields to secondary_line_segment

Revision ID: add_secondary_extra
Revises: add_secondary_line
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_secondary_extra'
down_revision = 'add_secondary_line'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('secondary_line_segment', sa.Column('installation_type', sa.String(64), nullable=True))
    op.add_column('secondary_line_segment', sa.Column('conductor_type', sa.String(32), nullable=True))
    op.add_column('secondary_line_segment', sa.Column('conductor_size', sa.String(32), nullable=True))
    op.add_column('secondary_line_segment', sa.Column('conductor_unit', sa.String(32), nullable=True))


def downgrade():
    op.drop_column('secondary_line_segment', 'conductor_unit')
    op.drop_column('secondary_line_segment', 'conductor_size')
    op.drop_column('secondary_line_segment', 'conductor_type')
    op.drop_column('secondary_line_segment', 'installation_type')
