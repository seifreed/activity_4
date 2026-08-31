from dataclasses import dataclass


@dataclass(frozen=True)
class StoredFile:
    id: int
    owner_id: int
    name: str
    description: str | None = None
    object_key: str | None = None
    size: int = 0

    @property
    def has_content(self) -> bool:
        return self.object_key is not None
