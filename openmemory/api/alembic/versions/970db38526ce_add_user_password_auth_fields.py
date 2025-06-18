"""add_user_password_auth_fields

Revision ID: 970db38526ce
Revises: fa19735ccd7d
Create Date: 2025-06-18 00:59:55.040438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import secrets
import hashlib


# revision identifiers, used by Alembic.
revision: str = '970db38526ce'
down_revision: Union[str, None] = 'fa19735ccd7d' # add_scopes_to_api_keys
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns as nullable initially
    op.add_column('users', sa.Column('hashed_password', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('salt', sa.String(255), nullable=True))

    # Populate placeholder/random values for existing users
    # This requires op.execute for data manipulation.
    # We need to generate a unique salt for each user and hash a placeholder password.
    # A direct UPDATE for all users with the same hash is simpler for migration,
    # but less secure if someone could guess the placeholder.
    # For this exercise, we'll use a common placeholder password.
    placeholder_password = "password_needs_reset_" + secrets.token_hex(8)

    # To update each row, we would typically iterate, but Alembic is schema-focused.
    # We can issue an UPDATE statement. Since each salt must be unique,
    # we cannot do this in a single UPDATE statement easily without database-specific functions.
    # However, for making them non-nullable, they just need *a* value.
    # Let's set a common salt and hash for simplicity of migration for existing users.
    # They will all need to reset their passwords.

    temp_salt = secrets.token_hex(16)
    temp_hashed_password = hashlib.sha256((placeholder_password + temp_salt).encode('utf-8')).hexdigest()

    op.execute(
        sa.text(
            "UPDATE users SET hashed_password = :h_password, salt = :salt_val WHERE hashed_password IS NULL OR salt IS NULL"
        ).bindparams(h_password=temp_hashed_password, salt_val=temp_salt)
    )

    # Now, alter columns to be non-nullable and handle 'email'
    # Using batch_alter_table for SQLite compatibility
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('hashed_password',
                              existing_type=sa.String(255),
                              nullable=False,
                              existing_nullable=True)
        batch_op.alter_column('salt',
                              existing_type=sa.String(255),
                              nullable=False,
                              existing_nullable=True)
        batch_op.alter_column('email',
                              existing_type=sa.String(), # Assuming original type was generic String
                              nullable=False,
                              existing_nullable=True) # Email was nullable=True before


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('hashed_password')
        batch_op.drop_column('salt')
        batch_op.alter_column('email',
                              existing_type=sa.String(),
                              nullable=True, # Revert email to nullable=True
                              existing_nullable=False)
