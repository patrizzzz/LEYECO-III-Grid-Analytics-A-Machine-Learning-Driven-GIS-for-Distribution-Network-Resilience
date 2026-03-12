"""Add post technical columns (phasing, configuration, spacing, height, etc.)

Revision ID: add_post_technical
Revises: add_user_access
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_post_technical'
down_revision = 'add_user_access'
branch_labels = None
depends_on = None


def upgrade():
    # Line segment / pole technical data columns on post
    # system_grounding_type and length_meters are added in add_infrastructure_data.py
    op.add_column('post', sa.Column('conductor_unit', sa.String(32)))
    op.add_column('post', sa.Column('conductor_strands', sa.String(32)))
    op.add_column('post', sa.Column('neutral_wire_type', sa.String(32)))
    op.add_column('post', sa.Column('neutral_wire_size', sa.String(32)))
    op.add_column('post', sa.Column('neutral_wire_unit', sa.String(32)))
    op.add_column('post', sa.Column('neutral_wire_strands', sa.String(32)))
    op.add_column('post', sa.Column('spacing_d12', sa.Float()))
    op.add_column('post', sa.Column('spacing_d23', sa.Float()))
    op.add_column('post', sa.Column('spacing_d13', sa.Float()))
    op.add_column('post', sa.Column('spacing_d1n', sa.Float()))
    op.add_column('post', sa.Column('spacing_d2n', sa.Float()))
    op.add_column('post', sa.Column('spacing_d3n', sa.Float()))
    op.add_column('post', sa.Column('spacing_dc1_c2', sa.Float()))
    # Height columns - note sa.Float() without parens if sa.Float works, but better to be consistent
    op.add_column('post', sa.Column('height_h1', sa.Float()))
    op.add_column('post', sa.Column('height_h2', sa.Float()))
    op.add_column('post', sa.Column('height_h3', sa.Float()))
    op.add_column('post', sa.Column('height_hn', sa.Float()))
    op.add_column('post', sa.Column('earth_resistivity', sa.Float()))


def downgrade():
    op.drop_column('post', 'earth_resistivity')
    op.drop_column('post', 'height_hn')
    op.drop_column('post', 'height_h3')
    op.drop_column('post', 'height_h2')
    op.drop_column('post', 'height_h1')
    op.drop_column('post', 'spacing_dc1_c2')
    op.drop_column('post', 'spacing_d3n')
    op.drop_column('post', 'spacing_d2n')
    op.drop_column('post', 'spacing_d1n')
    op.drop_column('post', 'spacing_d13')
    op.drop_column('post', 'spacing_d23')
    op.drop_column('post', 'spacing_d12')
    op.drop_column('post', 'neutral_wire_strands')
    op.drop_column('post', 'neutral_wire_unit')
    op.drop_column('post', 'neutral_wire_size')
    op.drop_column('post', 'neutral_wire_type')
    # Use consistent naming from the list
    op.drop_column('post', 'conductor_strands')
    op.drop_column('post', 'conductor_unit')
    op.drop_column('post', 'length_meters')
    op.drop_column('post', 'system_grounding_type')
