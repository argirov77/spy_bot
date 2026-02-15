from fastapi import FastAPI

from .routers import game, lists

app = FastAPI(title='Spy Bot API')
app.include_router(lists.router)
app.include_router(game.router)


@app.get('/')
def root():
    return {'status': 'ok'}


@app.get('/health')
def health():
    return {'ok': True}
