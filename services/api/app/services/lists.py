import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Entry, WordList


def parse_entries(raw_text: str) -> list[str]:
    chunks = re.split(r'[,\n]+', raw_text)
    result: list[str] = []
    for chunk in chunks:
        text = chunk.strip()
        if text:
            result.append(text)
    return result


def get_lists(db: Session) -> list[dict]:
    stmt = (
        select(WordList.id, WordList.name, WordList.is_active, func.count(Entry.id).label('entries_count'))
        .outerjoin(Entry, (Entry.list_id == WordList.id) & (Entry.is_active.is_(True)))
        .group_by(WordList.id)
        .order_by(WordList.name.asc())
    )
    rows = db.execute(stmt).all()
    return [
        {
            'id': row.id,
            'name': row.name,
            'is_active': row.is_active,
            'entries_count': row.entries_count,
        }
        for row in rows
    ]


def create_list(db: Session, name: str) -> WordList:
    obj = WordList(name=name.strip())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def import_entries(db: Session, list_id: int, raw_text: str) -> dict:
    list_obj = db.get(WordList, list_id)
    if not list_obj:
        raise ValueError('List not found')

    parsed = parse_entries(raw_text)
    found = len(parsed)
    existing = {
        row[0].lower()
        for row in db.execute(select(Entry.text).where(Entry.list_id == list_id, Entry.is_active.is_(True))).all()
    }

    unique_batch = []
    seen_lower = set()
    duplicates = 0
    for text in parsed:
        lower = text.lower()
        if lower in seen_lower:
            duplicates += 1
            continue
        seen_lower.add(lower)
        if lower in existing:
            duplicates += 1
            continue
        unique_batch.append(text)

    db.add_all([Entry(list_id=list_id, text=item) for item in unique_batch])
    db.commit()

    return {'found': found, 'added': len(unique_batch), 'duplicates': duplicates}
