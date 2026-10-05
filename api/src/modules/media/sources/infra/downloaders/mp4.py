from dataclasses import dataclass
from pathlib import Path
from struct import unpack_from
from typing import BinaryIO


@dataclass(frozen=True)
class MP4Box:
    kind: bytes
    start: int
    end: int


class FragmentedMP4Duration:
    def boxes(self, stream: BinaryIO, start: int, end: int) -> list[MP4Box]:
        result = []
        position = start
        while position < end:
            stream.seek(position)
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("Truncated MP4 box")
            size, kind = unpack_from(">I4s", header)
            prefix = 8
            if size == 1:
                extended = stream.read(8)
                if len(extended) != 8:
                    raise ValueError("Truncated extended MP4 box")
                size = unpack_from(">Q", extended)[0]
                prefix = 16
            elif size == 0:
                size = end - position
            if size < prefix or position + size > end:
                raise ValueError("Invalid MP4 box size")
            result.append(MP4Box(kind, position + prefix, position + size))
            if len(result) > 10000:
                raise ValueError("MP4 contains too many boxes")
            position += size
        return result

    def read(self, stream: BinaryIO, box: MP4Box) -> bytes:
        size = box.end - box.start
        if size > 4_000_000:
            raise ValueError("MP4 metadata exceeds its size limit")
        stream.seek(box.start)
        value = stream.read(size)
        if len(value) != size:
            raise ValueError("Truncated MP4 metadata")
        return value

    def child(self, stream: BinaryIO, parent: MP4Box, kind: bytes) -> MP4Box:
        matches = [
            box
            for box in self.boxes(stream, parent.start, parent.end)
            if box.kind == kind
        ]
        if len(matches) != 1:
            raise ValueError("Missing or duplicate MP4 timing box")
        return matches[0]

    def tracks(self, stream: BinaryIO, movie: MP4Box) -> dict[int, int]:
        tracks = {}
        for box in self.boxes(stream, movie.start, movie.end):
            if box.kind != b"trak":
                continue
            header = self.read(stream, self.child(stream, box, b"tkhd"))
            media = self.child(stream, box, b"mdia")
            timing = self.read(stream, self.child(stream, media, b"mdhd"))
            identifier = unpack_from(">I", header, 20 if header[0] else 12)[0]
            scale = unpack_from(">I", timing, 20 if timing[0] else 12)[0]
            if not scale or identifier in tracks:
                raise ValueError("Invalid MP4 track timescale or identity")
            tracks[identifier] = scale
        return tracks

    def run(
        self, data: bytes, default_duration: int, default_size: int
    ) -> tuple[int, int]:
        flags, count = unpack_from(">II", data)
        flags &= 0xFFFFFF
        offset = 8 + (4 if flags & 1 else 0) + (4 if flags & 4 else 0)
        fields = [bit for bit in (0x100, 0x200, 0x400, 0x800) if flags & bit]
        stride = len(fields) * 4
        if not count or offset + count * stride != len(data):
            raise ValueError("Invalid MP4 fragment sample table")
        duration = count * default_duration
        size = count * default_size
        if flags & 0x100:
            duration = sum(
                unpack_from(">I", data, offset + index * stride)[0]
                for index in range(count)
            )
        if flags & 0x200:
            size_offset = 4 if flags & 0x100 else 0
            size = sum(
                unpack_from(">I", data, offset + index * stride + size_offset)[
                    0
                ]
                for index in range(count)
            )
        if not duration or not size:
            raise ValueError("Missing MP4 fragment sample timing or size")
        return duration, size

    def fragment(
        self,
        stream: BinaryIO,
        track: MP4Box,
        scales: dict[int, int],
        defaults: dict[int, tuple[int, int]],
    ) -> tuple[float, int]:
        header = self.read(stream, self.child(stream, track, b"tfhd"))
        flags, identifier = unpack_from(">II", header)
        flags &= 0xFFFFFF
        if identifier not in scales:
            raise ValueError("Unknown MP4 fragment track")
        duration, size = defaults.get(identifier, (0, 0))
        offset = 8 + (8 if flags & 1 else 0) + (4 if flags & 2 else 0)
        if flags & 8:
            duration = unpack_from(">I", header, offset)[0]
            offset += 4
        if flags & 16:
            size = unpack_from(">I", header, offset)[0]
        timing = self.read(stream, self.child(stream, track, b"tfdt"))
        ticks = unpack_from(">Q" if timing[0] else ">I", timing, 4)[0]
        runs = [
            self.run(self.read(stream, box), duration, size)
            for box in self.boxes(stream, track.start, track.end)
            if box.kind == b"trun"
        ]
        if not runs:
            raise ValueError("Missing MP4 fragment samples")
        return (
            (ticks + sum(run[0] for run in runs)) / scales[identifier],
            sum(run[1] for run in runs),
        )

    def inspect(self, path: Path) -> float:
        with path.open("rb") as stream:
            root = MP4Box(b"root", 0, path.stat().st_size)
            movie = self.child(stream, root, b"moov")
            scales = self.tracks(stream, movie)
            extensions = self.child(stream, movie, b"mvex")
            defaults = {}
            for box in self.boxes(stream, extensions.start, extensions.end):
                if box.kind == b"trex":
                    values = unpack_from(">6I", self.read(stream, box))
                    defaults[values[1]] = (values[3], values[4])
            top = self.boxes(stream, root.start, root.end)
            fragments = [
                self.fragment(stream, track, scales, defaults)
                for box in top
                if box.kind == b"moof"
                for track in self.boxes(stream, box.start, box.end)
                if track.kind == b"traf"
            ]
            data_size = sum(
                box.end - box.start for box in top if box.kind == b"mdat"
            )
            if not fragments or sum(part[1] for part in fragments) > data_size:
                raise ValueError("Incomplete MP4 fragment data")
            result = max(part[0] for part in fragments)
        return result
