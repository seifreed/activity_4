from functools import lru_cache

from app.authentication.domain.security import Pbkdf2PasswordHasher, UrlSafeTokenGenerator
from app.authentication.domain.services import AuthenticationService
from app.authentication.persistence.repositories import (
    TortoiseSessionRepository,
    TortoiseUserRepository,
)


@lru_cache(maxsize=1)
def get_authentication_service() -> AuthenticationService:
    """Singleton que enlaza la API con el dominio de autenticacion."""
    return AuthenticationService(
        users=TortoiseUserRepository(),
        sessions=TortoiseSessionRepository(),
        hasher=Pbkdf2PasswordHasher(),
        tokens=UrlSafeTokenGenerator(),
    )
