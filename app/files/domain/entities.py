from dataclasses import dataclass


@dataclass(frozen=True)
class StoredFile:
    id: int
    owner_id: int
    name: str
    description: str | None = None
    content: bytes | None = None

    @property
    def size(self) -> int:
        return len(self.content) if self.content else 0

    @property
    def has_content(self) -> bool:
        return self.content is not None
