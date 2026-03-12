"""Add viewer access fields to user table

Revision ID: add_user_access
Revises: add_bus_post
Create Date: 2026-02-04

Adds:
- access_code (viewer login)
- access_enabled (enable/disable viewer)
- created_at (audit)

Also makes password_hash nullable to support viewer accounts (they use access codes).
"""

from alembic import op
import sqlalchemy as sa


revision = 'add_user_access'
down_revision = 'add_bus_post'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns (nullable with defaults to keep migration safe on existing data)
    op.add_column('user', sa.Column('access_code', sa.String(length=128), nullable=True))
    op.add_column('user', sa.Column('access_enabled', sa.Boolean(), nullable=True, server_default=sa.text('true')))
    op.add_column('user', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))

    # Index for fast lookup by access code
    op.create_index('ix_user_access_code', 'user', ['access_code'], unique=False)

    # Allow NULL password hashes (viewer accounts)
    op.alter_column('user', 'password_hash', existing_type=sa.String(length=256), nullable=True)


def downgrade():
    op.alter_column('user', 'password_hash', existing_type=sa.String(length=256), nullable=False)
    op.drop_index('ix_user_access_code', table_name='user')
    op.drop_column('user', 'created_at')
    op.drop_column('user', 'access_enabled')
    op.drop_column('user', 'access_code')

