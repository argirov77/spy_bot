import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Entry, Game, GamePlayer, GameStatus, WordList


def _active_game(db: Session, chat_id: int) -> Game | None:
    stmt = (
        select(Game)
        .where(Game.chat_id == chat_id, Game.status.in_([GameStatus.ACTIVE, GameStatus.ALL_SEEN]))
        .options(joinedload(Game.players), joinedload(Game.entry))
    )
    return db.execute(stmt).scalars().unique().first()


def serialize_game(game: Game) -> dict:
    seen_count = sum(1 for p in game.players if p.seen_at is not None)
    current = next((p for p in game.players if p.player_index == game.current_player), None)
    spy_indices = [p.player_index for p in game.players if p.is_spy]
    return {
        'game_id': game.id,
        'chat_id': game.chat_id,
        'status': game.status.value,
        'players_count': game.players_count,
        'spies_count': game.spies_count,
        'current_player': game.current_player,
        'is_revealed': game.is_revealed,
        'current_seen': bool(current and current.seen_at is not None),
        'seen_count': seen_count,
        'seen': [
            {'player_index': p.player_index, 'seen': p.seen_at is not None}
            for p in sorted(game.players, key=lambda x: x.player_index)
        ],
        'entry_text': game.entry.text,
        'spy_indices': spy_indices,
    }


def start_game(db: Session, chat_id: int, list_id: int, players_count: int, spies_count: int) -> dict:
    if spies_count >= players_count:
        raise ValueError('Spies must be less than players')
    if players_count < 3:
        raise ValueError('Players must be at least 3')

    active = _active_game(db, chat_id)
    if active:
        raise ValueError('Active game already exists')

    list_obj = db.get(WordList, list_id)
    if not list_obj or not list_obj.is_active:
        raise ValueError('List not found')

    entries = db.execute(select(Entry).where(Entry.list_id == list_id, Entry.is_active.is_(True))).scalars().all()
    if not entries:
        raise ValueError('List has no entries')

    entry = random.choice(entries)
    spy_indices = sorted(random.sample(range(1, players_count + 1), spies_count))

    game = Game(
        chat_id=chat_id,
        list_id=list_id,
        entry_id=entry.id,
        players_count=players_count,
        spies_count=spies_count,
        status=GameStatus.ACTIVE,
        current_player=1,
        is_revealed=False,
    )
    db.add(game)
    db.flush()

    players = [
        GamePlayer(game_id=game.id, player_index=i, is_spy=(i in spy_indices))
        for i in range(1, players_count + 1)
    ]
    db.add_all(players)
    db.commit()

    game = _active_game(db, chat_id)
    return serialize_game(game)


def get_status(db: Session, chat_id: int) -> dict | None:
    game = _active_game(db, chat_id)
    return serialize_game(game) if game else None


def reveal(db: Session, chat_id: int) -> dict:
    game = _active_game(db, chat_id)
    if not game:
        raise ValueError('No active game')
    if game.status == GameStatus.ALL_SEEN:
        raise ValueError('All players already seen')
    if game.is_revealed:
        raise ValueError("Първо натисни 'Скрий'.")

    current = next(p for p in game.players if p.player_index == game.current_player)
    game.is_revealed = True
    db.commit()
    payload = serialize_game(game)
    payload['reveal_text'] = 'ШПИОН' if current.is_spy else f"ДУМА/ФРАЗА: {game.entry.text}"
    return payload


def hide(db: Session, chat_id: int) -> dict:
    game = _active_game(db, chat_id)
    if not game:
        raise ValueError('No active game')
    if not game.is_revealed:
        raise ValueError("Натисни 'Покажи' първо.")

    current = next(p for p in game.players if p.player_index == game.current_player)
    current.seen_at = datetime.now(timezone.utc)
    game.is_revealed = False

    if game.current_player == game.players_count:
        game.status = GameStatus.ALL_SEEN

    db.commit()
    return serialize_game(game)


def next_player(db: Session, chat_id: int) -> dict:
    game = _active_game(db, chat_id)
    if not game:
        raise ValueError('No active game')
    if game.status == GameStatus.ALL_SEEN:
        raise ValueError('All players already seen')
    if game.is_revealed:
        raise ValueError("Първо натисни 'Скрий'.")

    current = next(p for p in game.players if p.player_index == game.current_player)
    if current.seen_at is None:
        raise ValueError("Първо натисни 'Скрий'.")

    game.current_player += 1
    if game.current_player > game.players_count:
        game.status = GameStatus.ALL_SEEN
        game.current_player = game.players_count
    db.commit()
    return serialize_game(game)


def end_game(db: Session, chat_id: int) -> dict:
    game = _active_game(db, chat_id)
    if not game:
        raise ValueError('No active game')

    game.status = GameStatus.FINISHED
    game.ended_at = datetime.now(timezone.utc)
    db.commit()
    payload = serialize_game(game)
    return payload
