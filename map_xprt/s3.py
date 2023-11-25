from __future__ import annotations

from configparser import ConfigParser
from datetime import datetime
from logging import getLogger
from typing import IO, TYPE_CHECKING, Iterator, Mapping, Optional
from urllib.parse import urlparse, urlunparse

from boto3 import resource as aws_resource

if TYPE_CHECKING:
    from mypy_boto3_s3.service_resource import ObjectSummary

from .state import read_json, state_path
from .types import Uploader

logger = getLogger(__name__.split(".")[-1])


class Credentials:
    STEM = "aws_credentials"

    def __init__(self, access_key: str, secret_key: str, region: str = None):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

    @classmethod
    def from_dict(cls, d: Mapping[str, str]) -> Credentials:
        args = {
            "access_key": d["aws_access_key_id"],
            "secret_key": d["aws_secret_access_key"],
        }
        if "region" in d:
            args["region"] = d["region"]
        return cls(**args)

    @classmethod
    def load(cls) -> Optional[Credentials]:
        c: Optional[Mapping[str, str]] = None
        try:
            c = read_json(cls.STEM)
        except FileNotFoundError:
            cfg = ConfigParser()
            for n in (f"{cls.STEM}.ini", cls.STEM):
                cfg.read(state_path(n))
            if "default" in cfg:
                c = dict(cfg["default"])
        return cls.from_dict(c) if c is not None else None


class Bucket(Uploader):
    def __init__(self, bucket: str, region: str = None, creds=Credentials.load()):
        self.bucket_name = bucket
        self.region = (
            region
            if region is not None
            else creds.region
            if creds is not None
            else None
        )
        self.creds = creds
        self._resource = None
        self._bucket = None

    def _get_resource(self):
        if self._resource is None:
            args = {}
            if self.region is not None:
                args["region_name"] = self.region
            if self.creds is not None:
                args["aws_access_key_id"] = self.creds.access_key
                args["aws_secret_access_key"] = self.creds.secret_key
            self._resource = aws_resource(service_name="s3", **args)

        assert self._resource is not None
        return self._resource

    def _get_bucket(self):
        if self._bucket is None:
            self._bucket = self._get_resource().Bucket(self.bucket_name)

        assert self._bucket is not None
        assert self._bucket.creation_date is not None
        return self._bucket

    def _generate_url(self, key: str) -> str:
        bucket = self._get_bucket()
        url = self._get_resource().meta.client.generate_presigned_url(
            "get_object", ExpiresIn=0, Params={"Bucket": bucket.name, "Key": key}
        )
        return urlunparse(urlparse(url)._replace(params="", query="", fragment=""))

    def find_matching(
        self, folder: str = "", stem: str = ""
    ) -> Iterator[ObjectSummary]:
        bucket = self._get_bucket()
        prefix = f"{folder}/{stem}".lstrip("/")
        for o in bucket.objects.filter(Prefix=prefix):
            if not o.key.endswith("/"):
                yield o

    def find_next(
        self,
        stem: str,
        before: Optional[datetime] = None,
        suffix: str = ".png",
        folder: str = "",
    ) -> Optional[str]:
        try:
            o = max(
                self.find_matching(folder, stem),
                key=lambda o: self.num_from_filename(o.key),
            )
        except ValueError as e:
            if "empty sequence" in str(e):
                return f"{stem}_{1:03}{suffix}"
            raise
        logger.info(f"{o} @ {o.last_modified}")
        if before is not None and o.last_modified >= before:
            return None

        return f"{stem}_{self.num_from_filename(o.key)+1:03}{suffix}"

    def upload(self, file: IO[bytes], filename: str, folder: str = "") -> str:
        bucket = self._get_bucket()
        key = f"{folder}/{filename}".lstrip("/")
        bucket.upload_fileobj(file, key, ExtraArgs={"ContentType": "image/png"})
        return self._generate_url(key)
