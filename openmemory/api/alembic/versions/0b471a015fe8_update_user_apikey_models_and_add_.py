"""Update User, APIKey models and add A2ATask table

Revision ID: 0b471a015fe8
Revises: 236a819e3b88
Create Date: 2025-06-18 03:37:07.783977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b471a015fe8'
down_revision: Union[str, None] = '236a819e3b88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
