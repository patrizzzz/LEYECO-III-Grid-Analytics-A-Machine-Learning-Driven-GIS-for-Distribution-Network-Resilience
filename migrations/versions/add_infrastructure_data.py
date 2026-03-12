"""Add complete infrastructure data to posts

Revision ID: add_infrastructure_data
Revises: add_distribution_line
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_infrastructure_data'
down_revision = 'add_distribution_line'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL transactional DDL breaks if a command fails inside a try-except.
    # Since we are starting fresh, we remove the try-except blocks and the redundant drops.
    
    # Add missing columns to post table
    op.add_column('post', sa.Column('pole_number', sa.String(32)))
    op.add_column('post', sa.Column('feeder', sa.String(64)))
    op.add_column('post', sa.Column('pri_structure', sa.String(64)))
    op.add_column('post', sa.Column('pri_conductor_size', sa.String(32)))
    op.add_column('post', sa.Column('neutral_wire', sa.String(32)))
    op.add_column('post', sa.Column('configuration', sa.String(64)))
    op.add_column('post', sa.Column('phasing', sa.String(32)))
    op.add_column('post', sa.Column('primary_bus_id', sa.String(64)))
    op.add_column('post', sa.Column('sec_structure', sa.String(64)))
    op.add_column('post', sa.Column('sec_conductor_size', sa.String(32)))
    op.add_column('post', sa.Column('sec_type', sa.String(64)))
    op.add_column('post', sa.Column('conductor_type', sa.String(64)))
    op.add_column('post', sa.Column('sec_bus_id', sa.String(64)))
    op.add_column('post', sa.Column('kva_rating', sa.Float()))
    op.add_column('post', sa.Column('common_sole', sa.String(32)))
    op.add_column('post', sa.Column('transformer_bus_id', sa.String(64)))
    op.add_column('post', sa.Column('transformer_phasing', sa.String(32)))
    op.add_column('post', sa.Column('grounding_rod', sa.String(32)))
    op.add_column('post', sa.Column('meter_id', sa.String(128)))
    op.add_column('post', sa.Column('meter_brand', sa.String(64)))
    op.add_column('post', sa.Column('meter_rating', sa.Float()))
    op.add_column('post', sa.Column('circuit', sa.String(64)))
    op.add_column('post', sa.Column('l2_conductor_size', sa.String(32)))
    op.add_column('post', sa.Column('l2_wire_type', sa.String(32)))
    op.add_column('post', sa.Column('l1_conductor_size', sa.String(32)))
    op.add_column('post', sa.Column('l1_wire_type', sa.String(32)))
    op.add_column('post', sa.Column('created_at', sa.DateTime()))
    op.add_column('post', sa.Column('updated_at', sa.DateTime()))
    
    # Create unique index on pole_number
    op.create_unique_constraint('uq_post_pole_number', 'post', ['pole_number'])
    
    # Create new Meter table for historical readings
    op.create_table(
        'meter',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('meter_id', sa.String(128)),
        sa.Column('meter_brand', sa.String(64)),
        sa.Column('meter_rating', sa.Float()),
        sa.Column('kwhr_reading', sa.Float()),
        sa.Column('reading_date', sa.DateTime()),
        sa.ForeignKeyConstraint(['post_id'], ['post.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meter_meter_id', 'meter', ['meter_id'], unique=False)


def downgrade():
    op.drop_index('ix_meter_meter_id', table_name='meter')
    op.drop_table('meter')
    
    # Drop columns from post table
    columns_to_drop = [
        'updated_at', 'created_at', 'l1_wire_type', 'l1_conductor_size',
        'l2_wire_type', 'l2_conductor_size', 'circuit', 'meter_rating',
        'meter_brand', 'meter_id', 'grounding_rod', 'transformer_phasing',
        'transformer_bus_id', 'common_sole', 'kva_rating', 'sec_bus_id',
        'conductor_type', 'sec_type', 'sec_conductor_size', 'sec_structure',
        'primary_bus_id', 'phasing', 'configuration', 'neutral_wire',
        'pri_conductor_size', 'pri_structure', 'feeder', 'pole_number'
    ]
    
    for col in columns_to_drop:
        op.drop_column('post', col)
