"""Add line connection table for inferred network topology

Revision ID: add_line_connections
Revises: add_infrastructure_data
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_line_connections'
down_revision = 'add_timestamps'
branch_labels = None
depends_on = None


def upgrade():
    # Create line_connection table
    op.create_table(
        'line_connection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_bus', sa.String(64), nullable=False),
        sa.Column('to_bus', sa.String(64), nullable=False),
        sa.Column('connection_type', sa.String(32), nullable=False),
        sa.Column('feeder', sa.String(64), nullable=True),
        sa.Column('circuit', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_bus', 'to_bus', 'connection_type', name='unique_connection')
    )
    
    # Create indexes for common queries
    op.create_index('ix_line_connection_from_bus', 'line_connection', ['from_bus'])
    op.create_index('ix_line_connection_to_bus', 'line_connection', ['to_bus'])
    op.create_index('ix_line_connection_feeder', 'line_connection', ['feeder'])


def downgrade():
    op.drop_table('line_connection')
