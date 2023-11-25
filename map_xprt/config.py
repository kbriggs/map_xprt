from __future__ import annotations

# Standard python libs
import os
from typing import Any, Iterator, List, Mapping, Optional

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
    def __init__(
        self,
        name: str,
        docid: str,
        s3_bucket: str,
        s3_folder: str,
        crop: Optional[List[float]] = None,
    ):
        # TODO specify per-map s3 region?
        self.name = name
        self.docid = docid
        self.bucket = s3_bucket
        self.folder = s3_folder
        assert crop is None or len(crop) == 4
        self.crop = crop

    def __str__(self):
        return f"{self.name}: {self.docid} -> {self.bucket}/{self.folder}"


class CampaignConfig:
    def __init__(
        self,
        title: Optional[str] = None,
        short: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_folder: Optional[str] = None,
    ):
        # TODO specify per-campaign s3 region?
        self.title = title
        self.shortname = short
        self.bucket = s3_bucket
        self.folder = s3_folder

    def __str__(self):
        return f"{self.name}: {self.bucket}/{self.folder}"


class Config:
    def __init__(self, s3_bucket: str, s3_folder: str = None, s3_region: str = None):
        self.bucket = s3_bucket
        self.folder = s3_folder
        self.region = s3_region
        self.campaigns: Dict[str, CampaignConfig] = {}
        self.maps: List[MapConfig] = []  # TODO map name->config?

    @classmethod
    def from_config(cls, c: ConfigDict) -> Config:
        args = {"s3_bucket": c["s3"]["bucket"]}
        if "folder" in c["s3"]:
            args["s3_folder"] = c["s3"]["folder"]
        if "region" in c["s3"]:
            args["s3_region"] = c["s3"]["region"]
        cfg = cls(**args)
        if "campaign" in c:
            for p in cls._find_campaigns(c["campaign"]):
                cfg._add_campaign(p)
        for m in cls._find_maps(c["map"]):
            cfg._add_map(m)
        return cfg

    @classmethod
    def _find_campaigns(cls, c: ConfigDict, parent: str = None) -> Iterator[ConfigDict]:
        # TODO: add the key path as an attribute?
        for n in c:
            name = n if parent is None else ".".join((parent, n))
            if "title" in c[n] or "shortname" in c[n]:
                yield dict(c[n], name=name)
            else:
                for m in cls._find_campaigns(c[n], name):
                    yield m

    @classmethod
    def _find_maps(cls, c: ConfigDict, parent: str = None) -> Iterator[ConfigDict]:
        # TODO: add the key path as an attribute?
        for n in c:
            name = n if parent is None else ".".join((parent, n))
            if "docid" in c[n]:
                yield dict(c[n], name=name)
            else:
                for m in cls._find_maps(c[n], name):
                    yield m

    def _join_folder(self, folder: str) -> str:
        return os.path.normpath(
            os.path.join(
                self.folder if self.folder is not None else "/",
                folder if folder is not None else ".",
            )
        ).lstrip("/")

    def _add_campaign(self, m: ConfigDict) -> None:
        args: Dict[str, Optional[str]] = {
            "s3_bucket": self.bucket,
            "s3_folder": self.folder,
        }
        if "title" in m:
            args["title"] = m["title"]
        if "shortname" in m:
            args["short"] = m["shortname"]
        if "s3" in m:
            if "bucket" in m["s3"]:
                args["s3_bucket"] = m["s3"]["bucket"]
            if "folder" in m["s3"]:
                args["s3_folder"] = self._join_folder(m["s3"]["folder"])
        obj = CampaignConfig(**args)
        self.campaigns[m["name"]] = obj
        if obj.shortname is not None:
            self.campaigns[obj.shortname] = obj

    def _add_map(self, m: ConfigDict) -> None:
        args = {
            "name": m["name"],
            "docid": m["docid"],
            "s3_bucket": self.bucket,
            "s3_folder": self.folder,
        }
        if "s3" in m:
            if "bucket" in m["s3"]:
                args["s3_bucket"] = m["s3"]["bucket"]
            if "folder" in m["s3"]:
                args["s3_folder"] = self._join_folder(m["s3"]["folder"])
        if "crop" in m:
            args["crop"] = m["crop"]
        self.maps.append(MapConfig(**args))

    def __str__(self):
        r = f"{self.bucket}/{self.folder if self.folder is not None else ''}"
        for m in self.maps:
            r += f"\n\t{m}"
        return r

    def map(self, name: str) -> MapConfig:
        for m in self.maps:
            if m.name == name:
                return m
        raise (ValueError(name))


def load_config(path=default_file()):
    with open(path, "rb") as f:
        return Config.from_config(tomli.load(f))
