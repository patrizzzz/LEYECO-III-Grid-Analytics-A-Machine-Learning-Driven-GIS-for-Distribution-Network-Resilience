"""Add secondary_line_segment table

Secondary line: from_bus_id = transformer to_secondary_bus_id,
to_bus_id = post primary_bus_id.

Revision ID: add_secondary_line
Revises: add_line_connections
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_secondary_line'
down_revision = 'add_line_connections'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'secondary_line_segment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('segment_id', sa.String(128), nullable=True),
        sa.Column('from_bus_id', sa.String(64), nullable=False),
        sa.Column('to_bus_id', sa.String(64), nullable=False),
        sa.Column('feeder', sa.String(64), nullable=True),
        sa.Column('circuit', sa.String(64), nullable=True),
        sa.Column('phasing', sa.String(32), nullable=True),
        sa.Column('length_meters', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_secondary_line_segment_from_bus_id', 'secondary_line_segment', ['from_bus_id'], unique=False)
    op.create_index('ix_secondary_line_segment_to_bus_id', 'secondary_line_segment', ['to_bus_id'], unique=False)
    op.create_index('ix_secondary_line_segment_segment_id', 'secondary_line_segment', ['segment_id'], unique=False)
    op.create_index('ix_secondary_line_segment_feeder', 'secondary_line_segment', ['feeder'], unique=False)


def downgrade():
    op.drop_index('ix_secondary_line_segment_feeder', table_name='secondary_line_segment')
    op.drop_index('ix_secondary_line_segment_segment_id', table_name='secondary_line_segment')
    op.drop_index('ix_secondary_line_segment_to_bus_id', table_name='secondary_line_segment')
    op.drop_index('ix_secondary_line_segment_from_bus_id', table_name='secondary_line_segment')
    op.drop_table('secondary_line_segment')
