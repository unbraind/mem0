"""secure_api_key_storage

Revision ID: bbfd61f5a85c
Revises: 130be2a95390
Create Date: 2025-06-18 00:48:07.638898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import secrets
import hashlib


# revision identifiers, used by Alembic.
revision: str = 'bbfd61f5a85c'
down_revision: Union[str, None] = '130be2a95390'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add new columns as nullable
    op.add_column('api_keys', sa.Column('salt', sa.String(255), nullable=True))
    op.add_column('api_keys', sa.Column('key_prefix', sa.String(8), nullable=True))

    # Step 2: Perform renames and nullability changes in batch
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('key',
                              new_column_name='hashed_key',
                              existing_type=sa.String,
                              type_=sa.String(255),
                              existing_nullable=False,
                              nullable=False)

        batch_op.alter_column('salt',
                              existing_type=sa.String(255),
                              existing_nullable=True,
                              nullable=False)
        batch_op.alter_column('key_prefix',
                              existing_type=sa.String(8),
                              existing_nullable=True,
                              nullable=False)

    # Step 3: Data migration
    placeholder_salt_val = secrets.token_urlsafe(16)
    placeholder_hashed_key_val = hashlib.sha256(("migrated_key_" + secrets.token_urlsafe(10) + placeholder_salt_val).encode()).hexdigest()
    placeholder_key_prefix_val = secrets.token_hex(4)

    op.execute(
        sa.text(
            "UPDATE api_keys SET "
            "salt = :salt, "
            "hashed_key = :hashed_key, "
            "key_prefix = :key_prefix "
            "WHERE salt IS NULL"
        ).bindparams(
            salt=placeholder_salt_val,
            hashed_key=placeholder_hashed_key_val,
            key_prefix=placeholder_key_prefix_val
        )
    )

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('hashed_key',
                              new_column_name='key',
                              existing_type=sa.String(255),
                              type_=sa.String,
                              existing_nullable=False,
                              nullable=False)

        batch_op.drop_column('key_prefix')
        batch_op.drop_column('salt')
