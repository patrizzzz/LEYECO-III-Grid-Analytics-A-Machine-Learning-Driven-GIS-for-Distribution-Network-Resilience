"""Add bus_post_mapping table for Bus–Post mapping (feeder visualization)

Revision ID: add_bus_post
Revises: 58285a24ebf6
Create Date: 2026-02-04

Bus–Post mapping layer: map engineering Bus IDs to Post IDs only for drawing feeder lines.
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_bus_post'
down_revision = '58285a24ebf6'
branch_labels = None
depends_on = None


def upgrade():
    # Bus–Post mapping: visualization only, no electrical logic
    op.create_table(
        'bus_post_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bus_id', sa.String(length=64), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['post.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bus_post_mapping_bus_id', 'bus_post_mapping', ['bus_id'], unique=False)


def downgrade():
    op.drop_index('ix_bus_post_mapping_bus_id', table_name='bus_post_mapping')
    op.drop_table('bus_post_mapping')
