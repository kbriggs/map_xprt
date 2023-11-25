from __future__ import annotations

# Standard python libs
import os
from abc import abstractmethod
from typing import Any, Dict, Iterator, List, Mapping, Optional, Type, TypeVar

# Common PyPI libs
import tomli

# Local libs
from .state import state_path
from .types import Uploader
from . import s3
from . import discord


DEFAULT_CWD = "map_xprt.toml"
DEFAULT_DOT = "config.toml"


def default_file() -> str:
    return DEFAULT_CWD if os.path.exists(DEFAULT_CWD) else state_path(DEFAULT_DOT)


# TODO: tighten up to Mapping[str, str | ConfigDict]
ConfigDict = Mapping[str, Any]

TTarget = TypeVar("TTarget", bound="MapTarget")  # type nonsense, see PEP673


class MapTarget:
    @staticmethod
    @abstractmethod
    def config_key() -> str:
        pass

    @staticmethod
    @abstractmethod
    def uploader() -> Type[Uploader]:
        pass

    @abstractmethod
    def derive(self: TTarget, *args, **kwargs) -> TTarget:
        pass


class S3Target(MapTarget):
    @staticmethod
    def config_key() -> str:
        return "s3"

    @staticmethod
    def uploader() -> Type[Uploader]:
        return s3.Bucket

    def __init__(
        self, bucket: str, folder: Optional[str] = None, region: Optional[str] = None
    ):
        self.bucket = bucket
        self.folder = folder
        self.region = region

    def _join_folder(self, folder: Optional[str]) -> str:
        return os.path.normpath(
            os.path.join(
                self.folder if self.folder is not None else "/",
                folder if folder is not None else ".",
            )
        ).lstrip("/")

    def derive(
        self: S3Target,
        bucket: Optional[str] = None,
        folder: Optional[str] = None,
        region: Optional[str] = None,
        *args,
        **kwargs,
    ) -> S3Target:
        return type(self)(
            bucket if bucket is not None else self.bucket,
            self._join_folder(folder),
            region if region is not None else self.region,
        )


class DiscordTarget(MapTarget):
    @staticmethod
    def config_key() -> str:
        return "discord"

    @staticmethod
    def uploader() -> Type[Uploader]:
        return discord.Channel

    pass


class MapConfig:
    def __init__(
        self,
        name: str,
        docid: str,
        target: MapTarget,
        crop: Optional[List[float]] = None,
    ):
        self.name = name
        self.docid = docid
        self.target = target
        assert crop is None or len(crop) == 4
        self.crop = crop

    def __str__(self):
        return f"{self.name}: {self.docid} -> {self.bucket}/{self.folder}"


class CampaignConfig:
    def __init__(
        self,
        title: Optional[str] = None,
        short: Optional[str] = None,
        target: Optional[MapTarget] = None,
    ):
        self.title = title
        self.shortname = short
        self.target = target

    def __str__(self):
        return f"{self.name}: {self.bucket}/{self.folder}"


class Config:
    def __init__(self, s3_bucket: str, s3_folder: str = None, s3_region: str = None):
        self.target = S3Target(s3_bucket, s3_folder, s3_region)
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

    def _add_campaign(self, m: ConfigDict) -> None:
        args = {}
        if "title" in m:
            args["title"] = m["title"]
        if "shortname" in m:
            args["short"] = m["shortname"]
        if "s3" in m:
            args["target"] = self.target.derive(
                bucket=m["s3"]["bucket"] if "bucket" in m["s3"] else None,
                folder=m["s3"]["folder"] if "folder" in m["s3"] else None,
                region=m["s3"]["region"] if "region" in m["s3"] else None,
            )
        else:
            args["target"] = self.target.derive()
        obj = CampaignConfig(**args)
        self.campaigns[m["name"]] = obj
        if obj.shortname is not None:
            self.campaigns[obj.shortname] = obj

    def _add_map(self, m: ConfigDict) -> None:
        args = {
            "name": m["name"],
            "docid": m["docid"],
        }
        if "s3" in m:
            # FIXME: derive from campaign target
            args["target"] = self.target.derive(
                bucket=m["s3"]["bucket"] if "bucket" in m["s3"] else None,
                folder=m["s3"]["folder"] if "folder" in m["s3"] else None,
                region=m["s3"]["region"] if "region" in m["s3"] else None,
            )
        else:
            # FIXME: use campaign target
            args["target"] = self.target.derive()
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
