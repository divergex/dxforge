from typing import final


@final
class SecretBytes:
    __slots__ = ("_data",)

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._data = bytearray(data)

    def as_bytes(self) -> bytes:
        return bytes(self._data)

    def __bytes__(self) -> bytes:
        return bytes(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def wipe(self) -> None:
        for i in range(len(self._data)):
            self._data[i] = 0

    def __enter__(self) -> "SecretBytes":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.wipe()
