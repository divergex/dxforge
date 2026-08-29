from pathlib import Path


class SourceAdapter:
    source_type = "source"

    def fetch(self) -> Path:
        """Materialize the source tree; caller owns cleanup of the returned dir."""
        raise NotImplementedError
