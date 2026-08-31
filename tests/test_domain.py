"""Pruebas del dominio con dobles en memoria, sin base de datos ni HTTP."""

import pytest

from app.authentication.domain.security import Pbkdf2PasswordHasher
from app.files.domain.entities import StoredFile
from app.files.domain.errors import FileNotFound, FileWithoutContent, NotEnoughFilesToMerge
from app.files.domain.ports import FileRepository, PdfMerger, UserResolver
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

    async def set_content(self, file_id: int, content: bytes) -> None:
        row = self.rows[file_id]
        self.rows[file_id] = StoredFile(row.id, row.owner_id, row.name, row.description, content)

    async def delete(self, file_id: int) -> bool:
        return self.rows.pop(file_id, None) is not None


class FakeMerger(PdfMerger):
    def merge(self, documents: list[bytes]) -> bytes:
        return b"".join(documents)


class FakeUserResolver(UserResolver):
    def __init__(self, external_id: int = 1):
        self.external_id = external_id

    async def external_id_for(self, token: str) -> int:
        return self.external_id


def build_service(resolver: FakeUserResolver) -> tuple[FileService, FakeFileRepository]:
    repository = FakeFileRepository()
    return FileService(repository, FakeMerger(), resolver), repository


def test_el_hash_no_deja_rastro_de_la_contrasena():
    stored = FAST_HASHER.hash("contrasena1")

    assert "contrasena1" not in stored
    assert FAST_HASHER.verify("contrasena1", stored)
    assert not FAST_HASHER.verify("otra", stored)


def test_dos_hashes_de_la_misma_contrasena_son_distintos():
    assert FAST_HASHER.hash("contrasena1") != FAST_HASHER.hash("contrasena1")


async def test_un_usuario_no_alcanza_los_ficheros_de_otro():
    resolver = FakeUserResolver(external_id=1)
    service, _ = build_service(resolver)
    file_id = await service.create("token", "privado.pdf", None)

    resolver.external_id = 2

    assert await service.list_files("token") == []
    with pytest.raises(FileNotFound):
        await service.get("token", file_id)
    with pytest.raises(FileNotFound):
        await service.delete("token", file_id)


async def test_la_fusion_exige_al_menos_dos_ficheros():
    service, _ = build_service(FakeUserResolver())
    file_id = await service.create("token", "solo.pdf", None)

    with pytest.raises(NotEnoughFilesToMerge):
        await service.merge("token", [file_id], None)


async def test_la_fusion_exige_que_todos_tengan_contenido():
    service, _ = build_service(FakeUserResolver())
    first = await service.create("token", "a.pdf", None)
    second = await service.create("token", "b.pdf", None)
    await service.set_content("token", first, b"contenido")

    with pytest.raises(FileWithoutContent):
        await service.merge("token", [first, second], None)


async def test_la_fusion_guarda_el_resultado_como_fichero_nuevo():
    service, repository = build_service(FakeUserResolver())
    ids = []
    for name, content in (("a.pdf", b"aaa"), ("b.pdf", b"bbb")):
        file_id = await service.create("token", name, None)
        await service.set_content("token", file_id, content)
        ids.append(file_id)

    merged_id = await service.merge("token", ids, None)

    assert merged_id not in ids
    assert repository.rows[merged_id].content == b"aaabbb"
    assert repository.rows[merged_id].name == "a-b.pdf"
