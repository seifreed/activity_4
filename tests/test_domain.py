"""Pruebas del dominio con dobles en memoria, sin base de datos, Redis ni S3."""

import pytest

from app.authentication.domain.entities import User
from app.authentication.domain.security import Pbkdf2PasswordHasher
from app.files.domain.entities import StoredFile
from app.files.domain.errors import FileNotFound, FileWithoutContent, NotEnoughFilesToMerge
from app.files.domain.ports import FileRepository, ObjectStorage, PdfMerger, UserResolver
from app.files.domain.services import FileService

# Iteraciones bajas: aqui solo se comprueba el comportamiento, no el coste del hash.
FAST_HASHER = Pbkdf2PasswordHasher(iterations=1_000)


class FakeFileRepository(FileRepository):
    def __init__(self):
        self.rows: dict[int, StoredFile] = {}
        self._next_id = 1

    async def create(self, owner_id: int, name: str, description: str | None) -> int:
        file_id = self._next_id
        self._next_id += 1
        self.rows[file_id] = StoredFile(file_id, owner_id, name, description)
        return file_id

    async def list_for_owner(self, owner_id: int) -> list[StoredFile]:
        return [row for row in self.rows.values() if row.owner_id == owner_id]

    async def get_for_owner(self, file_id: int, owner_id: int) -> StoredFile | None:
        row = self.rows.get(file_id)
        return row if row is not None and row.owner_id == owner_id else None

    async def attach_object(self, file_id: int, object_key: str, size: int) -> None:
        row = self.rows[file_id]
        self.rows[file_id] = StoredFile(
            row.id, row.owner_id, row.name, row.description, object_key, size
        )

    async def delete(self, file_id: int) -> bool:
        return self.rows.pop(file_id, None) is not None


class FakeObjectStorage(ObjectStorage):
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, content: bytes) -> None:
        self.objects[key] = content

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def shareable_url(self, key: str, filename: str) -> str:
        return f"https://ejemplo.invalid/{key}?nombre={filename}"


class FakeMerger(PdfMerger):
    def merge(self, documents: list[bytes]) -> bytes:
        return b"".join(documents)


class FakeUserResolver(UserResolver):
    def __init__(self, external_id: int = 1):
        self.external_id = external_id

    async def external_id_for(self, token: str) -> int:
        return self.external_id


def build_service(resolver: FakeUserResolver):
    repository = FakeFileRepository()
    storage = FakeObjectStorage()
    return FileService(repository, storage, FakeMerger(), resolver), repository, storage


def test_el_hash_no_deja_rastro_de_la_contrasena():
    stored = FAST_HASHER.hash("contrasena1")

    assert "contrasena1" not in stored
    assert FAST_HASHER.verify("contrasena1", stored)
    assert not FAST_HASHER.verify("otra", stored)


def test_dos_hashes_de_la_misma_contrasena_son_distintos():
    assert FAST_HASHER.hash("contrasena1") != FAST_HASHER.hash("contrasena1")


async def test_un_usuario_no_alcanza_los_ficheros_de_otro():
    resolver = FakeUserResolver(external_id=1)
    service, _, _ = build_service(resolver)
    file_id = await service.create("token", "privado.pdf", None)

    resolver.external_id = 2

    assert await service.list_files("token") == []
    with pytest.raises(FileNotFound):
        await service.get("token", file_id)
    with pytest.raises(FileNotFound):
        await service.delete("token", file_id)


async def test_el_contenido_va_al_almacen_de_objetos_y_no_a_los_metadatos():
    service, repository, storage = build_service(FakeUserResolver())
    file_id = await service.create("token", "informe.pdf", None)

    await service.set_content("token", file_id, b"contenido")

    row = repository.rows[file_id]
    assert row.object_key in storage.objects
    assert row.size == len(b"contenido")
    assert await service.read_content("token", file_id) == b"contenido"


async def test_al_reemplazar_el_contenido_no_queda_el_objeto_anterior():
    service, repository, storage = build_service(FakeUserResolver())
    file_id = await service.create("token", "informe.pdf", None)

    await service.set_content("token", file_id, b"primera")
    primera_clave = repository.rows[file_id].object_key
    await service.set_content("token", file_id, b"segunda")

    assert primera_clave not in storage.objects
    assert await service.read_content("token", file_id) == b"segunda"


async def test_al_borrar_el_fichero_se_borra_tambien_el_objeto():
    service, _, storage = build_service(FakeUserResolver())
    file_id = await service.create("token", "informe.pdf", None)
    await service.set_content("token", file_id, b"contenido")

    await service.delete("token", file_id)

    assert storage.objects == {}


async def test_la_fusion_exige_al_menos_dos_ficheros():
    service, _, _ = build_service(FakeUserResolver())
    file_id = await service.create("token", "solo.pdf", None)

    with pytest.raises(NotEnoughFilesToMerge):
        await service.merge("token", [file_id], None)


async def test_la_fusion_exige_que_todos_tengan_contenido():
    service, _, _ = build_service(FakeUserResolver())
    first = await service.create("token", "a.pdf", None)
    second = await service.create("token", "b.pdf", None)
    await service.set_content("token", first, b"contenido")

    with pytest.raises(FileWithoutContent):
        await service.merge("token", [first, second], None)


async def test_la_fusion_guarda_el_resultado_como_objeto_nuevo():
    service, repository, storage = build_service(FakeUserResolver())
    ids = []
    for name, content in (("a.pdf", b"aaa"), ("b.pdf", b"bbb")):
        file_id = await service.create("token", name, None)
        await service.set_content("token", file_id, content)
        ids.append(file_id)

    merged_id = await service.merge("token", ids, None)

    assert merged_id not in ids
    assert repository.rows[merged_id].name == "a-b.pdf"
    assert storage.objects[repository.rows[merged_id].object_key] == b"aaabbb"


async def test_el_enlace_compartible_solo_existe_si_hay_contenido():
    service, _, _ = build_service(FakeUserResolver())
    file_id = await service.create("token", "informe.pdf", None)

    assert await service.shareable_url("token", file_id) is None

    await service.set_content("token", file_id, b"contenido")
    assert "ejemplo.invalid" in await service.shareable_url("token", file_id)


async def test_la_sesion_guarda_la_instantanea_del_usuario():
    from app.authentication.persistence.redis_repositories import RedisSessionRepository

    class FakeRedis:
        def __init__(self):
            self.values: dict[str, str] = {}
            self.ttl: int | None = None

        async def set(self, key, value, ex=None):
            self.values[key] = value
            self.ttl = ex

        async def get(self, key):
            return self.values.get(key)

        async def delete(self, key):
            return 1 if self.values.pop(key, None) is not None else 0

    client = FakeRedis()
    repository = RedisSessionRepository(client, ttl_seconds=60)
    user = User(external_id=7, email="alba@example.com", name="Alba")

    await repository.create("token", user)

    assert client.ttl == 60
    assert await repository.get_user("token") == user
    assert await repository.delete("token") is True
    assert await repository.get_user("token") is None
