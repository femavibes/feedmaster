"""Add feed permissions table

Revision ID: add_feed_permissions
Revises: 
Create Date: 2025-08-08 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_feed_permissions'
down_revision = '36c5c6997e4c'
head = None

def upgrade():
    # Create permission level enum (if it doesn't exist)
    permission_level_enum = postgresql.ENUM('viewer', 'moderator', 'admin', name='permissionlevel')
    permission_level_enum.create(op.get_bind(), checkfirst=True)
    
    # Create feed_permissions table
    op.create_table('feed_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('feed_id', sa.String(length=50), nullable=False),
        sa.Column('permission_level', permission_level_enum, nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['feed_id'], ['feeds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key_id', 'feed_id', name='unique_api_key_feed')
    )
    op.create_index('ix_feed_permissions_api_key_id', 'feed_permissions', ['api_key_id'])
    op.create_index('ix_feed_permissions_feed_id', 'feed_permissions', ['feed_id'])

def downgrade():
    op.drop_index('ix_feed_permissions_feed_id', table_name='feed_permissions')
    op.drop_index('ix_feed_permissions_api_key_id', table_name='feed_permissions')
    op.drop_table('feed_permissions')
    
    # Drop permission level enum
    permission_level_enum = postgresql.ENUM('viewer', 'moderator', 'admin', name='permissionlevel')
    permission_level_enum.drop(op.get_bind())