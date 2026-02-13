"""Add missing timestamp columns to post table

Revision ID: add_timestamps
Revises: add_infrastructure_data
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_timestamps'
down_revision = 'add_infrastructure_data'
branch_labels = None
depends_on = None


def upgrade():
    # Add the missing created_at column to post table
    try:
        op.add_column('post', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    except Exception as e:
        print(f"Note: created_at might already exist: {e}")
    
    try:
        op.add_column('post', sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    except Exception as e:
        print(f"Note: updated_at might already exist: {e}")


def downgrade():
    try:
        op.drop_column('post', 'updated_at')
    except:
        pass
    
    try:
        op.drop_column('post', 'created_at')
    except:
        pass
