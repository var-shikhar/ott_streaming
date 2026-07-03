"""movies mode (content_type, credits, stills) + youtube episode source

Revision ID: c47d21e9a3f0
Revises: 98abc6d56da0
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c47d21e9a3f0'
down_revision: Union[str, Sequence[str], None] = '98abc6d56da0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('series', sa.Column('content_type', sa.String(length=10),
                                      nullable=False, server_default='series'))
    op.create_index(op.f('ix_series_content_type'), 'series', ['content_type'], unique=False)
    op.add_column('series', sa.Column('release_year', sa.Integer(), nullable=True))
    op.add_column('series', sa.Column('maturity_rating', sa.String(length=20),
                                      nullable=False, server_default=''))
    op.add_column('episodes', sa.Column('youtube_id', sa.String(length=20),
                                        nullable=False, server_default=''))
    op.create_table('credits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('series_id', sa.Uuid(), nullable=False),
        sa.Column('person_name', sa.String(length=120), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('character_name', sa.String(length=120), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['series_id'], ['series.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credits_series_id'), 'credits', ['series_id'], unique=False)
    op.create_table('stills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('series_id', sa.Uuid(), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['series_id'], ['series.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stills_series_id'), 'stills', ['series_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_stills_series_id'), table_name='stills')
    op.drop_table('stills')
    op.drop_index(op.f('ix_credits_series_id'), table_name='credits')
    op.drop_table('credits')
    op.drop_column('episodes', 'youtube_id')
    op.drop_column('series', 'maturity_rating')
    op.drop_column('series', 'release_year')
    op.drop_index(op.f('ix_series_content_type'), table_name='series')
    op.drop_column('series', 'content_type')
