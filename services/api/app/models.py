import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class GameStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    ALL_SEEN = 'ALL_SEEN'
    FINISHED = 'FINISHED'


class WordList(Base):
    __tablename__ = 'word_lists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    entries: Mapped[list['Entry']] = relationship(back_populates='word_list', cascade='all, delete-orphan')


class Entry(Base):
    __tablename__ = 'entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey('word_lists.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    word_list: Mapped['WordList'] = relationship(back_populates='entries')


class Game(Base):
    __tablename__ = 'games'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    list_id: Mapped[int] = mapped_column(ForeignKey('word_lists.id', ondelete='RESTRICT'), nullable=False)
    entry_id: Mapped[int] = mapped_column(ForeignKey('entries.id', ondelete='RESTRICT'), nullable=False)
    players_count: Mapped[int] = mapped_column(Integer, nullable=False)
    spies_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[GameStatus] = mapped_column(Enum(GameStatus, name='game_status'), default=GameStatus.ACTIVE, nullable=False)
    current_player: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    players: Mapped[list['GamePlayer']] = relationship(back_populates='game', cascade='all, delete-orphan')
    entry: Mapped['Entry'] = relationship()


Index(
    'ix_games_unique_active_chat',
    Game.chat_id,
    unique=True,
    postgresql_where=Game.status.in_([GameStatus.ACTIVE, GameStatus.ALL_SEEN]),
)


class GamePlayer(Base):
    __tablename__ = 'game_players'

    game_id: Mapped[int] = mapped_column(ForeignKey('games.id', ondelete='CASCADE'), primary_key=True)
    player_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_spy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    game: Mapped['Game'] = relationship(back_populates='players')
