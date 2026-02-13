"""Add distribution_line_segment table for electrical line data

Revision ID: add_distribution_line
Revises: add_user_access
Create Date: 2026-02-11

Distribution line segment data: stores electrical distribution line technical specifications
including conductor types, spacings, heights, and grounding information.
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_distribution_line'
down_revision = 'add_user_access'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'distribution_line_segment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('segment_id', sa.String(length=128), nullable=False),
        sa.Column('from_bus_id', sa.String(length=64), nullable=False),
        sa.Column('to_bus_id', sa.String(length=64), nullable=False),
        sa.Column('phasing', sa.String(length=32), nullable=True),
        sa.Column('configuration', sa.String(length=64), nullable=True),
        sa.Column('system_grounding_type', sa.String(length=64), nullable=True),
        sa.Column('length_meters', sa.Float(), nullable=True),
        sa.Column('conductor_type', sa.String(length=32), nullable=True),
        sa.Column('conductor_size', sa.String(length=32), nullable=True),
        sa.Column('conductor_unit', sa.String(length=32), nullable=True),
        sa.Column('conductor_strands', sa.String(length=32), nullable=True),
        sa.Column('neutral_wire_type', sa.String(length=32), nullable=True),
        sa.Column('neutral_wire_size', sa.String(length=32), nullable=True),
        sa.Column('neutral_wire_unit', sa.String(length=32), nullable=True),
        sa.Column('neutral_wire_strands', sa.String(length=32), nullable=True),
        sa.Column('spacing_d12', sa.Float(), nullable=True),
        sa.Column('spacing_d23', sa.Float(), nullable=True),
        sa.Column('spacing_d13', sa.Float(), nullable=True),
        sa.Column('spacing_d1n', sa.Float(), nullable=True),
        sa.Column('spacing_d2n', sa.Float(), nullable=True),
        sa.Column('spacing_d3n', sa.Float(), nullable=True),
        sa.Column('spacing_dc1_c2', sa.Float(), nullable=True),
        sa.Column('height_h1', sa.Float(), nullable=True),
        sa.Column('height_h2', sa.Float(), nullable=True),
        sa.Column('height_h3', sa.Float(), nullable=True),
        sa.Column('height_hn', sa.Float(), nullable=True),
        sa.Column('earth_resistivity', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_distribution_line_segment_segment_id', 'distribution_line_segment', ['segment_id'], unique=False)


def downgrade():
    op.drop_index('ix_distribution_line_segment_segment_id', table_name='distribution_line_segment')
    op.drop_table('distribution_line_segment')
