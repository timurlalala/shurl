"""Initial migration

Revision ID: 1da96e286682
Revises: 
Create Date: 2025-04-01 16:35:24.893342

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import fastapi_users_db_sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '1da96e286682'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('original_url', sa.String(), nullable=False),
    sa.Column('short_url', sa.String(), nullable=False),
    sa.Column('created_by_uuid', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
    sa.Column('clicks', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_links_created_by_uuid'), 'links', ['created_by_uuid'], unique=False)
    op.create_index(op.f('ix_links_expires_at'), 'links', ['expires_at'], unique=False)
    op.create_index(op.f('ix_links_original_url'), 'links', ['original_url'], unique=False)
    op.create_index(op.f('ix_links_short_url'), 'links', ['short_url'], unique=True)
    op.create_table('user',
    sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=1024), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_links_short_url'), table_name='links')
    op.drop_index(op.f('ix_links_original_url'), table_name='links')
    op.drop_index(op.f('ix_links_expires_at'), table_name='links')
    op.drop_index(op.f('ix_links_created_by_uuid'), table_name='links')
    op.drop_table('links')
    # ### end Alembic commands ###
