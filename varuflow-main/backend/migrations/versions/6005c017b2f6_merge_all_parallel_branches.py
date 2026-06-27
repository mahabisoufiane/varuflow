"""merge_all_parallel_branches

Revision ID: 6005c017b2f6
Revises: a0b1c2d3e4f5, aa0bb1cc2dd3, aa8b9c0d1e2f, d0e1f2a3b4c5, dd4ee5ff6gg7, f9z0a1b2c3d4, gg7hh8ii9jj0, h8i9j0k1l2m3, ii8jj9kk0ll1, mm3nn4oo5pp6, pp7qq8rr9ss0, uu2xx5yy6zz7, xx4yy5zz6aa7
Create Date: 2026-06-08 14:59:17.048236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6005c017b2f6'
down_revision: Union[str, None] = ('a0b1c2d3e4f5', 'aa0bb1cc2dd3', 'aa8b9c0d1e2f', 'd0e1f2a3b4c5', 'dd4ee5ff6gg7', 'f9z0a1b2c3d4', 'gg7hh8ii9jj0', 'h8i9j0k1l2m3', 'ii8jj9kk0ll1', 'mm3nn4oo5pp6', 'pp7qq8rr9ss0', 'uu2xx5yy6zz7', 'xx4yy5zz6aa7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
