from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import BotAuth
from ..schemas import ImportEntriesRequest, ListCreate
from ..services import lists as list_service

router = APIRouter(prefix='/lists', tags=['lists'], dependencies=[BotAuth])


@router.get('')
def get_lists(db: Session = Depends(get_db)):
    return {'items': list_service.get_lists(db)}


@router.post('')
def create_list(payload: ListCreate, db: Session = Depends(get_db)):
    try:
        obj = list_service.create_list(db, payload.name)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='List with this name already exists')
    return {'id': obj.id, 'name': obj.name, 'is_active': obj.is_active}


@router.post('/{list_id}/entries/import')
def import_entries(list_id: int, payload: ImportEntriesRequest, db: Session = Depends(get_db)):
    try:
        stats = list_service.import_entries(db, list_id=list_id, raw_text=payload.raw_text)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    return stats


@router.delete('/{list_id}')
def delete_list(list_id: int, db: Session = Depends(get_db)):
    from ..models import WordList

    obj = db.get(WordList, list_id)
    if not obj:
        raise HTTPException(status_code=404, detail='List not found')
    db.delete(obj)
    db.commit()
    return {'ok': True}
