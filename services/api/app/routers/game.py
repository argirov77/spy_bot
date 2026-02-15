from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import BotAuth
from ..schemas import ChatRequest, GameStartRequest
from ..services import games as game_service

router = APIRouter(prefix='/game', tags=['game'], dependencies=[BotAuth])


@router.post('/start')
def start(payload: GameStartRequest, db: Session = Depends(get_db)):
    try:
        return game_service.start_game(
            db,
            chat_id=payload.chat_id,
            list_id=payload.list_id,
            players_count=payload.players_count,
            spies_count=payload.spies_count,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post('/reveal')
def reveal(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        return game_service.reveal(db, payload.chat_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post('/hide')
def hide(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        return game_service.hide(db, payload.chat_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post('/next')
def next_player(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        return game_service.next_player(db, payload.chat_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get('/status')
def status(chat_id: int, db: Session = Depends(get_db)):
    data = game_service.get_status(db, chat_id)
    return {'game': data}


@router.post('/end')
def end(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        return game_service.end_game(db, payload.chat_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
