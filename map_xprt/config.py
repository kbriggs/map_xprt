from __future__ import annotations

# Standard python libs
import os
from typing import Any, Iterator, List, Mapping

# Common PyPI libs
import tomli

# Local libs
from .state import state_path


DEFAULT_CWD = "map_xprt.toml"
DEFAULT_DOT = "config.toml"


def default_file() -> str:
    return DEFAULT_CWD if os.path.exists(DEFAULT_CWD) else state_path(DEFAULT_DOT)


# TODO: tighten up to Mapping[str, str | ConfigDict]
ConfigDict = Mapping[str, Any]


class MapConfig:
    def __init__(self, docid: str, s3_bucket: str, s3_folder: str):
        self.docid = docid
        self.bucket = s3_bucket
        self.folder = s3_folder

    def __str__(self):
        return f"{self.docid} -> {self.bucket}/{self.folder}"


class Config:
    def __init__(self, s3_bucket: str, s3_folder: str = None):
        self.bucket = s3_bucket
        self.folder = s3_folder
        self.maps: List[MapConfig] = []

    @classmethod
    def from_config(cls, c: ConfigDict) -> Config:
        args = {
            "s3_bucket": c["s3"]["bucket"],
        }
        if "folder" in c["s3"]:
            args["s3_folder"] = c["s3"]["folder"]
        cfg = cls(**args)
        for m in cls._find_maps(c["map"]):
            cfg._add_map(m)
        return cfg

    @classmethod
    def _find_maps(cls, c: ConfigDict) -> Iterator[ConfigDict]:
        # TODO: add the key path as an attribute?
        for n in c:
            if "docid" in c[n]:
                yield c[n]
            else:
                for m in cls._find_maps(c[n]):
                    yield m

    def _join_folder(self, folder: str) -> str:
        return os.path.normpath(
            os.path.join(
                self.folder if self.folder is not None else "/",
                folder if folder is not None else ".",
            )
        ).lstrip("/")

    def _add_map(self, m: ConfigDict) -> None:
        args = {
            "docid": m["docid"],
            "s3_bucket": self.bucket,
            "s3_folder": self.folder,
        }
        if "s3" in m:
            if "bucket" in m["s3"]:
                args["s3_bucket"] = m["s3"]["bucket"]
            if "folder" in m["s3"]:
                args["s3_folder"] = self._join_folder(m["s3"]["folder"])
        self.maps.append(MapConfig(**args))

    def __str__(self):
        r = f"{self.bucket}/{self.folder if self.folder is not None else ''}"
        for m in self.maps:
            r += f"\n\t{m}"
        return r


def load_config(path=default_file()):
    with open(path, "rb") as f:
        return Config.from_config(tomli.load(f))
