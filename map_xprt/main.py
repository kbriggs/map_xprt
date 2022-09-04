#! /usr/bin/env python

import argparse
from datetime import datetime
import re
from typing import Optional

from .config import Config, MapConfig, load_config
from .drive import GoogleDrive, MediaType
from .render import Box, SVGRenderer
from .s3 import Bucket


cli = argparse.ArgumentParser(description="Export a Google Drawing to an S3-hosted PNG")
cli.add_argument("map", nargs="*", help="map(s) to convert")
cli.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="Be more verbose (mostly for debugging)",
)
cli.add_argument(
    "-n",
    "--dry-run",
    action="store_true",
    help="Don't convert or upload, just show what would be done",
)
cli.add_argument(
    "-f", "--force", action="store_true", help="Ignore timestamps and always process"
)
cli.add_argument(
    "-O",
    "--only-convert",
    action="store_true",
    help="Don't upload, just convert and save to current directory",
)
cli.add_argument(
    "-o",
    "--output",
    action="store",
    type=str,
    metavar="FILENAME",
    help="Don't upload, just convert and save to the specified file (implies -f and a single map name)",
)
cli.add_argument(
    "-c",
    "--crop",
    nargs=4,
    type=float,
    metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"),
    help="Crop the map (specified in original drawing's coordinates)",
)
cli_size = cli.add_mutually_exclusive_group()
cli_size.add_argument(
    "-x",
    "--maxsize",
    type=int,
    metavar="SIZE",
    help="Maximum dimension of output image (in pixels)",
)
cli_size.add_argument(
    "-s",
    "--size",
    nargs=2,
    type=int,
    metavar=("WIDTH", "HEIGHT"),
    help="Dimensions of output image (in pixels); one may be zero to calculate from aspect",
)

opts: argparse.Namespace


def validate_args(args: argparse.Namespace):
    if hasattr(args, "output") and args.output is not None:
        if not hasattr(args, "map") or len(args.map) != 1:
            cli.error("Exactly one map must be specified for --output")
        setattr(args, "only_convert", True)
        setattr(args, "force", True)
    if hasattr(args, "size") and args.size is not None:
        if args.size[0] == 0 and args.size[1] == 0:
            cli.error("Width and height cannot both be zero")


def verbose(*args, **kwargs):
    if opts.verbose:
        print(*args, **kwargs)


def name_to_stem(name: str) -> str:
    """Filter characters from the name to construct a filename stem"""
    return re.sub(r"[^\w]", "", re.sub(r"[-\s]+", "_", name.lower()))


fn_re = re.compile(r"_([0-9]+)\.[a-z]+$")


def num_from_filename(filename: str) -> int:
    m = fn_re.search(filename)
    return int(m.group(1)) if m else -1


def find_next(
    bucket: Bucket,
    stem: str,
    folder: str = "",
    before: datetime = None,
    suffix: str = ".png",
) -> Optional[str]:
    try:
        o = max(
            bucket.find_matching(folder, stem), key=lambda o: num_from_filename(o.key)
        )
    except ValueError as e:
        if "empty sequence" in str(e):
            return f"{stem}_{1:03}{suffix}"
        raise
    verbose(f"{o} @ {o.last_modified}")
    if before is not None and o.last_modified >= before:
        return None

    return f"{stem}_{num_from_filename(o.key)+1:03}{suffix}"


# S3 buckets
s3 = {}


def process_map(cfg: Config, map: MapConfig):
    verbose(f"stating {map.docid}")

    doc = GoogleDrive(map.docid)
    stat = doc.stat()
    verbose(stat)
    stem = name_to_stem(stat["name"])
    if opts.force is True:
        modified = None
    else:
        modified = datetime.fromisoformat(re.sub(r"Z$", "+00:00", stat["modifiedTime"]))

    if opts.output is None:
        # need the s3 bucket to find file number and compare timestamps
        if map.bucket not in s3:
            s3[map.bucket] = Bucket(map.bucket, cfg.region)
        bucket = s3[map.bucket]
        filename = find_next(bucket, stem, map.folder, modified)
        if filename is None:
            verbose(f"Skipping unmodified {stem}")
            return

    else:
        filename = opts.output
    assert filename is not None

    verbose(
        f"{'Converting' if opts.only_convert else 'Converting and uploading'} {filename}"
    )
    if opts.dry_run is True:
        return

    with doc.export(MediaType.SVG) as svg:
        szopts = {}
        if opts.size is not None:
            if opts.size[0] != 0:
                szopts["target_width"] = opts.size[0]
            if opts.size[1] != 0:
                szopts["target_height"] = opts.size[1]
        elif opts.maxsize is not None:
            szopts["target_maxdim"] = opts.maxsize
        r = SVGRenderer(
            crop=Box(*opts.crop) if opts.crop is not None else None, **szopts
        )
        with r.render(svg, open(filename, "wb") if opts.only_convert else None) as png:
            if not opts.only_convert:
                png.seek(0)
                print(bucket.upload(png, filename, map.folder))


def main():
    global opts
    opts = cli.parse_args()
    verbose(opts)
    validate_args(opts)

    # Read config
    cfg = load_config()

    verbose(cfg)
    if len(opts.map) > 0:
        for n in opts.map:
            process_map(cfg, cfg.map(n))
    else:
        for m in cfg.maps:
            process_map(cfg, m)


if __name__ == "__main__":
    main()
