"""Update User, APIKey models and add A2ATask table V3

Revision ID: c0f56385e8ca
Revises: ff60d7d776b6
Create Date: 2025-06-18 03:39:08.869780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0f56385e8ca'
down_revision: Union[str, None] = 'ff60d7d776b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
