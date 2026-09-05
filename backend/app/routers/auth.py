from fastapi import APIRouter, Depends

from app.auth import authenticate, create_access_token, get_current_admin
from app.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    from fastapi import HTTPException

    if not authenticate(body.username, body.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return TokenResponse(access_token=create_access_token(body.username), username=body.username)


@router.get("/me")
def me(username: str = Depends(get_current_admin)) -> dict:
    return {"username": username}
