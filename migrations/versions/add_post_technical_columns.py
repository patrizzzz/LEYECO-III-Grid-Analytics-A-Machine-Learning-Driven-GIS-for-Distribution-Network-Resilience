"""Add post technical columns (phasing, configuration, spacing, height, etc.)

Revision ID: add_post_technical
Revises: add_user_access_fields
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
    new_columns = [
        ('system_grounding_type', sa.String(64)),
        ('length_meters', sa.Float()),
        ('conductor_unit', sa.String(32)),
        ('conductor_strands', sa.String(32)),
        ('neutral_wire_type', sa.String(32)),
        ('neutral_wire_size', sa.String(32)),
        ('neutral_wire_unit', sa.String(32)),
        ('neutral_wire_strands', sa.String(32)),
        ('spacing_d12', sa.Float()),
        ('spacing_d23', sa.Float()),
        ('spacing_d13', sa.Float()),
        ('spacing_d1n', sa.Float()),
        ('spacing_d2n', sa.Float()),
        ('spacing_d3n', sa.Float()),
        ('spacing_dc1_c2', sa.Float()),
        ('height_h1', sa.Float()),
        ('height_h2', sa.Float()),
        ('height_h3', sa.Float()),
        ('height_hn', sa.Float()),
        ('earth_resistivity', sa.Float()),
    ]
    for col_name, col_type in new_columns:
        try:
            op.add_column('post', sa.Column(col_name, col_type))
        except Exception:
            pass  # Column already exists


def downgrade():
    cols = [
        'earth_resistivity', 'height_hn', 'height_h3', 'height_h2', 'height_h1',
        'spacing_dc1_c2', 'spacing_d3n', 'spacing_d2n', 'spacing_d1n',
        'spacing_d13', 'spacing_d23', 'spacing_d12',
        'neutral_wire_strands', 'neutral_wire_unit', 'neutral_wire_size', 'neutral_wire_type',
        'conductor_strands', 'conductor_unit', 'length_meters', 'system_grounding_type',
    ]
    for col in cols:
        try:
            op.drop_column('post', col)
        except Exception:
            pass
