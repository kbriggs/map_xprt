from contextlib import contextmanager
import os
from typing import Any, Mapping, Optional, Sequence

import pytest  # type: ignore
import tomli

from map_xprt import config
from map_xprt.state import DOTPATH


DATADIR = os.path.join("tests", "data")


@contextmanager
def workdir(dir: Optional[str]):
    if dir is not None:
        prev_dir = os.getcwd()
        os.chdir(dir)
    try:
        yield
    finally:
        if dir is not None:
            os.chdir(prev_dir)


@pytest.mark.parametrize(
    "dir,expected",
    [
        (None, os.path.expanduser(os.path.join(DOTPATH, config.DEFAULT_DOT))),
        (DATADIR, config.DEFAULT_CWD),
    ],
)
def test_default_file(dir: Optional[str], expected: str):
    with workdir(dir):
        assert os.path.realpath(config.default_file()) == os.path.realpath(expected)


@pytest.fixture(scope="module")
def config_data():
    with open(os.path.join(DATADIR, config.DEFAULT_CWD), "rb") as f:
        return tomli.load(f)


@pytest.fixture
def check_cfg(config_data):
    def _check_cfg(cfg: config.Config):
        assert "s3" in config_data
        if "region" in config_data["s3"]:
            assert cfg.region == config_data["s3"]["region"]
        else:
            assert cfg.region is None
        assert cfg.bucket == config_data["s3"]["bucket"]
        assert cfg.folder == config_data["s3"]["folder"]

    return _check_cfg


@pytest.mark.skip(
    "Default arguments are evaluated as function definition time, so this test can never work"
)
def test_load_config_default(config_data, check_cfg):
    with workdir(DATADIR):
        cfg = config.load_config()
        check_cfg(cfg)


def test_load_config_data(config_data, check_cfg):
    cfg = config.load_config(os.path.join(DATADIR, config.DEFAULT_CWD))
    check_cfg(cfg)


def test_load_config_construct(config_data, check_cfg):
    cfg = config.Config.from_config(config_data)
    check_cfg(cfg)


def test_map_lookup_self(config_data):
    cfg = config.Config.from_config(config_data)
    assert len(cfg.maps) > 0
    for m in cfg.maps:
        assert m == cfg.map(m.name)


def by_path(d: Mapping[str, Any], key: Sequence[str]):
    if not key:
        return d
    return by_path(d[key[0]], key[1:])


@pytest.mark.parametrize(
    "path",
    [
        ("port", "moonraider"),
        ("sbrd", "moonraider"),
        ("port", "intruder"),
        ("sbrd", "wildspace"),
    ],
)
def test_map_lookup_data(config_data, path: Sequence[str]):
    cfg = config.Config.from_config(config_data)
    name = ".".join(path)
    map = cfg.map(name)
    assert map.name == name
    data = by_path(config_data["map"], path)
    assert map.docid is not None
    assert map.docid == data["docid"]
    if "crop" in data:
        assert map.crop is not None
        assert len(map.crop)
        assert map.crop == data["crop"]
    else:
        assert map.crop is None
    assert map.bucket is not None
    assert map.folder is not None
    s3 = config_data["s3"] if "s3" in config_data else {}
    if "s3" in data:
        if "bucket" in data["s3"]:
            s3["bucket"] = data["s3"]["bucket"]
        if "folder" in data["s3"]:
            # TODO: more complex paths e.g. ".." components
            s3["folder"] = (
                f"{s3['folder']}/{data['s3']['folder']}"
                if "folder" in s3
                else data["s3"]["folder"]
            )
    assert map.bucket == s3["bucket"]
    assert map.folder == s3["folder"]
