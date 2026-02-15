from pydantic import BaseModel, Field


class ListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ImportEntriesRequest(BaseModel):
    raw_text: str


class GameStartRequest(BaseModel):
    chat_id: int
    list_id: int
    players_count: int
    spies_count: int


class ChatRequest(BaseModel):
    chat_id: int
