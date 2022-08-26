from __future__ import annotations

from configparser import ConfigParser
from typing import Mapping, Optional

from boto3 import resource as aws_resource

from .state import read_json, state_path


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


class Bucket:
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
            args = {"service_name": "s3"}
            if self.region is not None:
                args["region_name"] = self.region
            if self.creds is not None:
                args["aws_access_key_id"] = self.creds.access_key
                args["aws_secret_access_key"] = self.creds.secret_key
            self._resource = aws_resource(**args)

        assert self._resource is not None
        return self._resource

    def _get_bucket(self):
        if self._bucket is None:
            self._bucket = self._get_resource().Bucket(self.bucket_name)

        assert self._bucket is not None
        assert self._bucket.creation_date is not None
        return self._bucket

    # FIXME testing only
    def list_files(self, folder=""):
        bucket = self._get_bucket()
        for o in bucket.objects.filter(Prefix=folder):
            if not o.key.endswith("/"):
                print(o.key)
