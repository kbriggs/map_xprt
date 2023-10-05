from __future__ import annotations

import abc
from datetime import datetime
import re
from typing import IO, Optional


class Uploader(abc.ABC):
    """A class to upload rasterized maps to some cloud storage."""

    @abc.abstractmethod
    def upload(self, file: IO[bytes], filename: str) -> str:
        pass

    @abc.abstractmethod
    def find_next(
        self, stem: str, before: Optional[datetime] = None, suffix: str = ".png"
    ) -> Optional[str]:
        pass

    fn_re = re.compile(r"_([0-9]+)\.[a-z]+$")

    @classmethod
    def num_from_filename(cls, filename: str) -> int:
        m = cls.fn_re.search(filename)
        return int(m.group(1)) if m else -1
