"""Add latitude/longitude to distribution_line_segment for map visualization

Revision ID: add_coordinates_to_lines
Revises: add_infrastructure_data
Create Date: 2026-02-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_coordinates_to_lines'
down_revision = 'add_infrastructure_data'
branch_labels = None
depends_on = None


def upgrade():
    # Add coordinate columns to distribution_line_segment
    op.add_column('distribution_line_segment', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('distribution_line_segment', sa.Column('longitude', sa.Float(), nullable=True))


def downgrade():
    # Remove coordinate columns
    op.drop_column('distribution_line_segment', 'latitude')
    op.drop_column('distribution_line_segment', 'longitude')
