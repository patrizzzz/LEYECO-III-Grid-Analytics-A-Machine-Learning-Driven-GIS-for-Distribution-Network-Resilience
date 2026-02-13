"""Add distribution_transformer table (example2.csv)

Revision ID: add_dist_transformer
Revises: add_post_technical
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_dist_transformer'
down_revision = 'add_post_technical'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'distribution_transformer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transformer_id', sa.String(128), nullable=False),
        sa.Column('from_primary_bus_id', sa.String(64), nullable=False),
        sa.Column('to_secondary_bus_id', sa.String(64)),
        sa.Column('primary_phasing', sa.String(32)),
        sa.Column('secondary_phasing', sa.String(32)),
        sa.Column('installation_type', sa.String(64)),
        sa.Column('no_dts_in_bank', sa.Integer()),
        sa.Column('connection', sa.String(32)),
        sa.Column('kva_rating', sa.Float()),
        sa.Column('primary_voltage_kv', sa.Float()),
        sa.Column('secondary_voltage_kv', sa.Float()),
        sa.Column('primary_tap_kv', sa.Float()),
        sa.Column('secondary_tap_kv', sa.Float()),
        sa.Column('pct_z', sa.Float()),
        sa.Column('xr_ratio', sa.Float()),
        sa.Column('no_load_loss_kw', sa.Float()),
        sa.Column('exciting_current_pct', sa.Float()),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_distribution_transformer_transformer_id', 'distribution_transformer', ['transformer_id'], unique=False)
    op.create_index('ix_distribution_transformer_from_primary_bus_id', 'distribution_transformer', ['from_primary_bus_id'], unique=False)


def downgrade():
    op.drop_index('ix_distribution_transformer_from_primary_bus_id', table_name='distribution_transformer')
    op.drop_index('ix_distribution_transformer_transformer_id', table_name='distribution_transformer')
    op.drop_table('distribution_transformer')
