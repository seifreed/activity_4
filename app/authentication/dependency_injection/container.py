from functools import lru_cache

from redis.asyncio import Redis

from app.authentication.domain.ports import SessionRepository
from app.authentication.domain.security import Pbkdf2PasswordHasher, UrlSafeTokenGenerator
from app.authentication.domain.services import AuthenticationService
from app.authentication.persistence.redis_repositories import RedisSessionRepository
from app.authentication.persistence.repositories import (
    TortoiseSessionRepository,
    TortoiseUserRepository,
)
from app.config import settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


@lru_cache(maxsize=1)
def get_session_repository() -> SessionRepository:
    """Elige la implementacion del puerto de sesiones segun la configuracion.

    Las dos cumplen el mismo contrato, asi que el servicio de autenticacion no nota el cambio.
    """
    if settings.session_backend == "redis":
        return RedisSessionRepository(get_redis_client(), settings.session_ttl_seconds)
    return TortoiseSessionRepository()


@lru_cache(maxsize=1)
def get_authentication_service() -> AuthenticationService:
    """Singleton que enlaza la API con el dominio de autenticacion."""
    return AuthenticationService(
        users=TortoiseUserRepository(),
        sessions=get_session_repository(),
        hasher=Pbkdf2PasswordHasher(),
        tokens=UrlSafeTokenGenerator(),
    )
