"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa


revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    game_status = sa.Enum('ACTIVE', 'ALL_SEEN', 'FINISHED', name='game_status')
    game_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'word_lists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('word_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_entries_list_id', 'entries', ['list_id'])

    op.create_table(
        'games',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.Integer(), nullable=False),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('word_lists.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('entry_id', sa.Integer(), sa.ForeignKey('entries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('players_count', sa.Integer(), nullable=False),
        sa.Column('spies_count', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'ALL_SEEN', 'FINISHED', name='game_status', create_type=False), nullable=False),
        sa.Column('current_player', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_revealed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_games_chat_id', 'games', ['chat_id'])

    op.create_table(
        'game_players',
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('player_index', sa.Integer(), primary_key=True),
        sa.Column('is_spy', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        "CREATE UNIQUE INDEX ix_games_unique_active_chat ON games (chat_id) WHERE status IN ('ACTIVE', 'ALL_SEEN')"
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_games_unique_active_chat')
    op.drop_table('game_players')
    op.drop_index('ix_games_chat_id', table_name='games')
    op.drop_table('games')
    op.drop_index('ix_entries_list_id', table_name='entries')
    op.drop_table('entries')
    op.drop_table('word_lists')
    sa.Enum(name='game_status').drop(op.get_bind(), checkfirst=True)
