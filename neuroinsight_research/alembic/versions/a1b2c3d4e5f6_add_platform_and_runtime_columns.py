"""add platform and runtime columns to jobs

Revision ID: a1b2c3d4e5f6
Revises: e25556f4711f
Create Date: 2026-02-21 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e25556f4711f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('runtime_seconds', sa.Float(), nullable=True))
    op.add_column('jobs', sa.Column('runtime_formatted', sa.String(length=50), nullable=True))
    op.add_column('jobs', sa.Column('data_source_platform', sa.String(length=50), nullable=True,
                                     comment='Source platform: pennsieve, xnat, or None for filesystem'))
    op.add_column('jobs', sa.Column('data_source_dataset_id', sa.String(length=200), nullable=True,
                                     comment='Dataset/experiment ID on the source platform'))


def downgrade() -> None:
    op.drop_column('jobs', 'data_source_dataset_id')
    op.drop_column('jobs', 'data_source_platform')
    op.drop_column('jobs', 'runtime_formatted')
    op.drop_column('jobs', 'runtime_seconds')
