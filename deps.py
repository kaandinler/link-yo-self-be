from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.auth.auth_service import AuthService
from di.container import Container
from models import User

# Swagger'daki "Authorize" butonunun dogru endpoint'e istek atmasi icin
# tam yol verilmeli (router'lar /api/v1 prefix'i altinda).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/token')
credentials_exception = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail='Could not validate credentials',
    headers={'WWW-Authenticate': 'Bearer'}
)


@inject
async def get_current_user(
        token: str = Depends(oauth2_scheme),
        auth_service: AuthService = Depends(Provide[Container.auth_service])
) -> User:
    """
    Get the current authenticated user based on the JWT token.
    Raises HTTPException if token is invalid or user doesn't exist.
    """
    # Verify and decode the token
    try:
        payload = await auth_service.verify_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the user from the database
    user = await auth_service.user_service.get_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return the authenticated user
    return user


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Check if the current user is an admin.
    First authenticates the user, then checks if they have admin privileges.
    If not, raises a 403 Forbidden error.
    """
    # Admin yetkisi User.is_admin alanindan okunuyor.
    # (Onceden username == "admin" kontrolu vardi; "admin" kayit sirasinda
    # rezerve kelime oldugu icin bu endpoint'e hicbir zaman erisilemiyordu.)
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user

