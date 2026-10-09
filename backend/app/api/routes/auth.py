from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, SettingsDep
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    login_limiter,
    verify_password,
)
from app.models import User
from app.schemas import AccountDelete, LoginIn, PasswordChange, RegisterIn, TokenOut, UserOut, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session(response: Response, token: str, settings) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _issue(response: Response, user: User, settings) -> TokenOut:
    token = create_access_token(user.id, user.token_version)
    _set_session(response, token, settings)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, response: Response, db: DB, settings: SettingsDep):
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue(response, user, settings)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: DB, settings: SettingsDep):
    email = body.email.lower()
    client = request.client.host if request.client else "unknown"
    if not login_limiter.allow(f"{client}:{email}"):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in a minute.")
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        burn_password_check(body.password)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return _issue(response, user, settings)


@router.post("/logout", status_code=204)
def logout(response: Response, settings: SettingsDep):
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: CurrentUser, db: DB):
    if body.email and body.email.lower() != user.email:
        clash = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
        if clash:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        user.email = body.email.lower()
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", response_model=TokenOut)
def change_password(body: PasswordChange, response: Response, user: CurrentUser, db: DB, settings: SettingsDep):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    RegisterIn(email=user.email, password=body.new_password)  # same strength rules
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # signs out every other session
    db.commit()
    return _issue(response, user, settings)


@router.post("/me/sign-out-everywhere", status_code=204)
def sign_out_everywhere(response: Response, user: CurrentUser, db: DB, settings: SettingsDep):
    user.token_version += 1
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(body: AccountDelete, response: Response, user: CurrentUser, db: DB, settings: SettingsDep):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    db.delete(user)
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")
