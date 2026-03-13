"""Add PostGIS geometry columns

Revision ID: 0cdef3a879ad
Revises: b442bb955f7c
Create Date: 2026-03-13 10:43:49.499269

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0cdef3a879ad'
down_revision = 'b442bb955f7c'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns using raw SQL to ensure PostGIS types are recognized correctly
    op.execute("ALTER TABLE bus_node ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bus_node_geom ON bus_node USING GIST (geom)")

    op.execute("ALTER TABLE distribution_line_segment ADD COLUMN IF NOT EXISTS geom geometry(LineString, 4326)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_distribution_line_segment_geom ON distribution_line_segment USING GIST (geom)")

    op.execute("ALTER TABLE post ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_post_geom ON post USING GIST (geom)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_post_geom")
    op.execute("ALTER TABLE post DROP COLUMN IF EXISTS geom")

    op.execute("DROP INDEX IF EXISTS idx_distribution_line_segment_geom")
    op.execute("ALTER TABLE distribution_line_segment DROP COLUMN IF EXISTS geom")

    op.execute("DROP INDEX IF EXISTS idx_bus_node_geom")
    op.execute("ALTER TABLE bus_node DROP COLUMN IF EXISTS geom")
