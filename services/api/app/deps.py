from fastapi import Depends, Header, HTTPException, status

from .config import settings


def validate_bot_token(x_bot_token: str = Header(default='')):
    if x_bot_token != settings.api_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized bot token')


BotAuth = Depends(validate_bot_token)
