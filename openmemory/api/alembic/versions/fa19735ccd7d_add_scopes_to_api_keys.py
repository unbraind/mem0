"""add_scopes_to_api_keys

Revision ID: fa19735ccd7d
Revises: bbfd61f5a85c
Create Date: 2025-06-18 00:54:41.708935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa19735ccd7d'
down_revision: Union[str, None] = 'bbfd61f5a85c' # Points to the secure_api_key_storage migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('api_keys',
                  sa.Column('scopes',
                            sa.String(),
                            nullable=False,
                            server_default="memories:read,memories:write")
                 )
    # For existing rows, the server_default will set the value.
    # For new rows created after this migration, if the application doesn't provide a value,
    # the database's default mechanism would ideally kick in. However, SQLAlchemy model's
    # `default` is usually handled at the application level. `server_default` is for the DB.
    # Since the model also has `default="memories:read,memories:write"`, new keys created
    # via SQLAlchemy without explicit scopes will get this value before INSERT.
    # Keys created with explicit scopes will use those.


def downgrade() -> None:
    """Downgrade schema."""
    # For SQLite, dropping columns often requires batch mode.
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.drop_column('scopes')
