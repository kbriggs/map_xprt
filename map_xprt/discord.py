from __future__ import annotations

from datetime import datetime
from typing import IO, Callable, Mapping, Optional
from urllib.parse import urljoin
from weakref import finalize

import requests
import tomli

from .state import state_path
from .types import Uploader


class Credentials:
    STEM = "discord_credentials"

    def __init__(self, token: str):
        self.token = token

    @classmethod
    def from_dict(cls, d: Mapping[str, str]) -> Credentials:
        args = {
            "token": d["token"],
        }
        return cls(**args)

    @classmethod
    def load(cls) -> Optional[Credentials]:
        c: Optional[Mapping[str, Mapping[str, str]]] = None
        for n in (f"{cls.STEM}.ini", cls.STEM):
            try:
                with open(state_path(n), "rb") as f:
                    c = tomli.load(f)
            except FileNotFoundError:
                pass
        return cls.from_dict(c["discord"]) if c is not None and "discord" in c else None


class API:
    BOT_NAME = "KarrionMaps"
    BOT_VERSION = "0.1"

    BASE_URL = "https://discord.com/api/v10/"

    class _DiscordBotAuth(requests.auth.AuthBase):
        def __init__(
            self,
            token: str,
            bot_name: Optional[str] = None,
            bot_version: Optional[str] = None,
        ):
            self.token = token
            self.agent = (
                f"{bot_name if bot_name is None else API.BOT_NAME} "
                f"{bot_version if bot_version is None else API.BOT_VERSION}"
            )

        def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
            r.headers["Authorization"] = f"Bot {self.token}"
            r.headers["User-Agent"] = f"DiscordBot ({self.agent})"
            return r

        def __eq__(self, other: object) -> bool:
            return all(
                [
                    self.token == getattr(other, "token", None),
                ]
            )

        def __ne__(self, other: object) -> bool:
            return not self == other

    def __init__(
        self,
        creds: Credentials,
        bot_name: Optional[str] = None,
        bot_version: Optional[str] = None,
    ):
        self._session = requests.Session()
        self._session.auth = self._DiscordBotAuth(creds.token, bot_name, bot_version)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._session.close()

    def _url(self, path: str) -> str:
        return urljoin(self.BASE_URL, path.lstrip("/"))

    def __getattr__(self, name: str) -> Callable:
        VERBS = ["get", "options", "head", "post", "put", "patch", "delete"]
        func = getattr(self._session, name)

        if name in VERBS:

            def verb_wrapper(url, *args, **kwargs):
                return func(self._url(url), *args, **kwargs)

            return verb_wrapper

        elif name == "request":

            def req_wrapper(method, url, *args, **kwargs):
                return func(method, self._url(url), *args, **kwargs)

            return req_wrapper

        else:
            return func


class Channel(Uploader):
    def __init__(self, channel: str, creds=Credentials.load()):
        self.channel = channel
        self.api = API(creds)
        self._final = finalize(self, self._finalize, self.api)

    def find_next(
        self, stem: str, before: Optional[datetime] = None, suffix: str = ".png"
    ) -> Optional[str]:
        raise NotImplementedError("Discord upload WIP")  # FIXME

    def upload(self, file: IO[bytes], filename: str) -> str:
        raise NotImplementedError("Discord upload WIP")  # FIXME

    @classmethod
    def _finalize(cls, api: API):
        api.close()

    def close(self):
        if self._final.detach():
            self.api.close()


def discover(creds=Credentials.load()):
    with API(creds) as api:
        for server in api.get("/users/@me/guilds").json():
            print(f"## {server['name']}")
            for channel in api.get(f"/guilds/{server['id']}/channels").json():
                if channel["type"] == 0:
                    print(f"{channel['id']}\t{channel['name']}")


if __name__ == "__main__":
    discover()
