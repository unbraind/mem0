"""Update User, APIKey models and add A2ATask table

Revision ID: ff60d7d776b6
Revises: 0b471a015fe8
Create Date: 2025-06-18 03:38:19.191582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff60d7d776b6'
down_revision: Union[str, None] = '0b471a015fe8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
