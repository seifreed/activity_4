import json

from redis.asyncio import Redis

from app.authentication.domain.entities import User
from app.authentication.domain.ports import SessionRepository

SESSION_PREFIX = "session:"


class RedisSessionRepository(SessionRepository):
    """Implementacion del puerto de sesiones contra Redis.

    Guarda una instantanea del usuario junto al token, de modo que validar una peticion no
    necesita ninguna consulta a Postgres. La caducidad la lleva el propio Redis con un TTL, asi
    que no hace falta ninguna tarea que limpie sesiones viejas y varios workers comparten estado.
    """

    def __init__(self, client: Redis, ttl_seconds: int):
        self._client = client
        self._ttl_seconds = ttl_seconds

    async def create(self, token: str, user: User) -> None:
        payload = json.dumps(
            {"external_id": user.external_id, "email": user.email, "name": user.name}
        )
        await self._client.set(SESSION_PREFIX + token, payload, ex=self._ttl_seconds)

    async def get_user(self, token: str) -> User | None:
        payload = await self._client.get(SESSION_PREFIX + token)
        return None if payload is None else User(**json.loads(payload))

    async def delete(self, token: str) -> bool:
        return await self._client.delete(SESSION_PREFIX + token) > 0
