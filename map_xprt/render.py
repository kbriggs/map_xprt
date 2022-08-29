from __future__ import annotations
from math import ceil

import tempfile
from typing import BinaryIO, Optional
from xml.etree import ElementTree

import cairosvg  # type: ignore # has no stubs
from PIL import Image


# A full-frame Widescreen 16:10 google drawing is 960x600 (96 dpi)
class Box:
    def __init__(self, l: float = 0.0, t: float = 0.0, w: float = 0.0, h: float = 0.0):
        self._left = float(l)
        self._top = float(t)
        self._width = float(w)
        self._height = float(h)

    @property
    def left(self) -> float:
        return self._left

    @property
    def top(self) -> float:
        return self._top

    @property
    def width(self) -> float:
        return self._width

    @property
    def height(self) -> float:
        return self._height

    @property
    def right(self) -> float:
        return self._left + self._width

    @property
    def bottom(self) -> float:
        return self._top + self._height

    @property
    def aspect(self) -> float:
        return self._width / self._height

    @property
    def dims(self) -> tuple[float, float]:
        return (self.width, self.height)

    @property
    def idims(self) -> tuple[int, int]:
        return (ceil(self.width), ceil(self.height))

    @classmethod
    def from_viewbox(cls, viewbox: str) -> Box:
        return cls(*[float(s) for s in viewbox.split()])

    def __str__(self):
        return f"{self.left} {self.top} {self.width} {self.height}"

    def intersect(self, other: Box) -> Box:
        l = max(self.left, other.left)
        t = max(self.top, other.top)
        r = min(self.right, other.right)
        b = min(self.bottom, other.bottom)
        return self.__class__(l, t, r - l, b - t)

    __and__ = intersect

    def multiply(self, factor) -> Box:
        return self.__class__(
            *[n * factor for n in (self.left, self.top, self.width, self.height)]
        )

    __mul__ = multiply

    def __invert__(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)


class SVGRenderer:
    def __init__(
        self,
        target_maxdim: Optional[int] = 1000,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        crop: Box = None,
    ):
        self.target_width = target_width
        self.target_height = target_height
        if self.target_width is not None or self.target_height is not None:
            self.target_maxdim = None
        else:
            self.target_maxdim = target_maxdim
        self.crop = crop

    def render(self, svg: BinaryIO, dest: Optional[BinaryIO] = None) -> BinaryIO:
        # TODO use a custom cairosvg.Surface subclass to, e.g.:
        # - override .finish() to do the crop and rescale directly on the cairo surface,
        #   instead of having to round-trip the converted raster and then do that
        # - override .convert() to avoid having to parse the XML twice in order to
        #   calculate the scale and crop factors

        if dest is None:
            # must be Named for pillow to detect type
            dest = tempfile.NamedTemporaryFile(suffix=".png")

        with tempfile.TemporaryFile() as f:
            # read first element to find original viewport
            for _, e in ElementTree.iterparse(svg, ["start"]):
                # .rpartition is to ignore the xmlns
                if ElementTree.iselement(e) and e.tag.rpartition("}")[2] == "svg":
                    viewbox = Box.from_viewbox(e.get("viewBox", ""))
                    break
            assert viewbox is not None

            # rewind input
            svg.seek(0)

            # crop the viewbox
            if self.crop is not None:
                viewbox = viewbox & self.crop

            # calc target box
            if self.target_maxdim is not None:
                if viewbox.aspect > 1.0:
                    tgtbox = Box(
                        w=self.target_maxdim, h=self.target_maxdim / viewbox.aspect
                    )
                else:
                    tgtbox = Box(
                        w=self.target_maxdim * viewbox.aspect, h=self.target_maxdim
                    )
            elif self.target_width is not None:
                if self.target_height is not None:
                    tgtbox = Box(w=self.target_width, h=self.target_height)
                else:
                    tgtbox = Box(
                        w=self.target_width, h=self.target_width / viewbox.aspect
                    )
            elif self.target_height is not None:
                tgtbox = Box(
                    w=self.target_height * viewbox.aspect, h=self.target_height
                )
            else:
                tgtbox = viewbox

            # calculate minimum scaling factor based on crop
            scale = ceil(
                max(4, tgtbox.width / viewbox.width, tgtbox.height / viewbox.height)
            )

            # covert svg into tempfile f
            cairosvg.svg2png(file_obj=svg, scale=scale, write_to=f)
            with Image.open(f) as img:
                with img.resize(
                    tgtbox.idims, Image.Resampling.LANCZOS, ~(viewbox * scale)
                ) as resized:
                    resized.save(dest, optimize=True)

        return dest
