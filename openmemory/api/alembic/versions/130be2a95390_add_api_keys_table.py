"""add_api_keys_table

Revision ID: 130be2a95390
Revises: afd00efbd06b
Create Date: 2025-06-18 00:19:04.177774

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '130be2a95390'
down_revision: Union[str, None] = 'afd00efbd06b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'api_keys',
        sa.Column('id', sa.UUID, primary_key=True, server_default=sa.text('(uuid_generate_v4())')),
        sa.Column('key', sa.String, unique=True, index=True, nullable=False),
        sa.Column('user_id', sa.UUID, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime, index=True, server_default=sa.func.now(), nullable=False),
        sa.Column('is_active', sa.Boolean, index=True, server_default=sa.true(), nullable=False)
    )
    # Additional explicit index creation if `index=True` in Column is not sufficient or for specific naming
    # op.create_index(op.f('ix_api_keys_key'), 'api_keys', ['key'], unique=True) # Already handled by unique=True, index=True
    # op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False) # Handled by index=True
    # op.create_index(op.f('ix_api_keys_created_at'), 'api_keys', ['created_at'], unique=False) # Handled by index=True
    # op.create_index(op.f('ix_api_keys_is_active'), 'api_keys', ['is_active'], unique=False) # Handled by index=True


def downgrade() -> None:
    """Downgrade schema."""
    # op.drop_index(op.f('ix_api_keys_is_active'), table_name='api_keys') # Not needed if index=True was used
    # op.drop_index(op.f('ix_api_keys_created_at'), table_name='api_keys') # Not needed
    # op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys') # Not needed
    # op.drop_index(op.f('ix_api_keys_key'), table_name='api_keys') # Not needed
    op.drop_table('api_keys')
