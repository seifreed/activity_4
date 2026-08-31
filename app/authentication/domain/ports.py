from abc import ABC, abstractmethod

from app.authentication.domain.entities import User


class UserRepository(ABC):
    """Puerto de salida hacia el almacen de usuarios."""

    @abstractmethod
    async def exists(self, email: str) -> bool: ...

    @abstractmethod
    async def create(self, email: str, password_hash: str, name: str | None) -> User: ...

    @abstractmethod
    async def find_with_password(self, email: str) -> tuple[User, str] | None:
        """Devuelve el usuario y el hash de su contrasena, o None si no existe."""


class SessionRepository(ABC):
    """Puerto de salida hacia el almacen de sesiones."""

    @abstractmethod
    async def create(self, token: str, user: User) -> None: ...

    @abstractmethod
    async def get_user(self, token: str) -> User | None: ...

    @abstractmethod
    async def delete(self, token: str) -> bool: ...


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, stored: str) -> bool: ...


class TokenGenerator(ABC):
    @abstractmethod
    def generate(self) -> str: ...
