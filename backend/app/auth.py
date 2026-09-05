from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": username, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def authenticate(username: str, password: str) -> bool:
    return username == settings.admin_username and password == settings.admin_password


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    token: str | None = Query(default=None),
) -> str:
    raw = creds.credentials if creds else token
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(raw, settings.secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效") from exc
    if username != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效用户")
    return username
