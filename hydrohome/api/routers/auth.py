from fastapi import APIRouter, Depends

from hydrohome.api.deps import current_token, current_user, get_services
from hydrohome.api.schemas import LoginIn, PasswordIn, ProfileIn, RegisterIn
from hydrohome.services.auth_service import public_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", status_code=201, summary="Create an account")
def register(body: RegisterIn, svc=Depends(get_services)):
    user, token = svc.auth.register(body.name, body.email, body.password)
    return {"user": user, "token": token, "token_type": "bearer"}


@router.post("/login", summary="Sign in and get a bearer token")
def login(body: LoginIn, svc=Depends(get_services)):
    user, token = svc.auth.login(body.email, body.password)
    return {"user": user, "token": token, "token_type": "bearer"}


@router.post("/logout", status_code=204, summary="Invalidate the current token")
def logout(token: str = Depends(current_token), _=Depends(current_user), svc=Depends(get_services)):
    svc.auth.logout(token)


@router.get("/me", summary="The signed-in user")
def me(user=Depends(current_user)):
    return public_user(user)


@router.put("/me", summary="Update your display name")
def update_me(body: ProfileIn, user=Depends(current_user), svc=Depends(get_services)):
    return svc.auth.update_profile(user["id"], body.name)


@router.put("/password", status_code=204, summary="Change your password")
def change_password(body: PasswordIn, user=Depends(current_user), svc=Depends(get_services)):
    svc.auth.change_password(user["id"], body.current_password, body.new_password)
