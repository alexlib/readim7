from __future__ import division, print_function, absolute_import

"""
Pure-Python reader for DaVis high-speed streaming (.ims) files.

The LaVision ReadIMX C++ library bundled here (Aug-2014) only understands
single-buffer files (IMG/IMX/VEC via ReadIMX, IM7/VC7 via ReadIM7) and
rejects camera stream files with "Error in format". This module reads those
streams directly with numpy, so it works on every platform readim7 installs
on — including macOS ARM, where lvpyio has no wheels.

Stream layout (reverse-engineered from DaVis 8 sets, validated byte-for-byte
on a 14.9 GB / 1000-pair pump-shutdown acquisition):

- ``<run>/Camera1-<k>.ims`` (large): raw 12-bit packed frames, pair after
  pair, pulse-A frame then pulse-B frame, row-major, with no headers at all.
  Pair size in bytes = frames_per_pair * ny * nx * 3 // 2.
- ``<run>/Camera1-0.ims`` (small, 1024 + 40 * n_pairs bytes): stream index.
  A 1 KiB header carries the geometry as little-endian u32
  ``[?, ?, frames_per_pair, nx, ny, bits, ...]``, followed by one 40-byte
  record per pair:
  ``[1, pair_offset_u64, frame_bytes, 0, 1, frameB_offset_u64, ?, frame_bytes, 0]``.

12-bit packing is little-endian: bytes ``b0, b1, b2`` hold
``p0 = b0 | ((b1 & 0x0F) << 8)`` and ``p1 = (b1 >> 4) | (b2 << 4)``.
"""

import struct
from functools import lru_cache
from pathlib import Path

import numpy as np

__all__ = ['ims_info', 'read_ims_pair', 'read_ims_frame']


_INDEX_HEADER_BYTES = 1024
_INDEX_RECORD_BYTES = 40

_MMAPS = {}


def _looks_like_index(size):
    return (
        size > _INDEX_HEADER_BYTES
        and (size - _INDEX_HEADER_BYTES) % _INDEX_RECORD_BYTES == 0
        and (size - _INDEX_HEADER_BYTES) // _INDEX_RECORD_BYTES > 0
    )


def _parse_index_header(index_path):
    """Return (frames_per_pair, nx, ny, bits, n_records) from an index .ims."""
    with open(index_path, 'rb') as f:
        header = f.read(_INDEX_HEADER_BYTES)
    if len(header) < 24:
        raise IOError('index file too short: %s' % index_path)
    _, _, frames_per_pair, nx, ny, bits = struct.unpack('<6I', header[:24])
    size = Path(index_path).stat().st_size
    n_records = (size - _INDEX_HEADER_BYTES) // _INDEX_RECORD_BYTES
    return frames_per_pair, nx, ny, bits, n_records


@lru_cache(maxsize=8)
def ims_info(path, nx=None, ny=None, frames_per_pair=2):
    """Describe a DaVis camera stream set.

    Parameters
    ----------
    path: str | Path
        Either the run folder holding the ``*.ims`` files or a direct path
        to one ``.ims`` file (the large stream file *or* its small index
        sibling — both resolve to the same set).
    nx, ny: int, optional
        Sensor width/height. Only needed when no index file is found next
        to the stream; otherwise geometry comes from the index header.
    frames_per_pair: int
        Frames per buffer (2 for dual-frame PIV).

    Returns
    -------
    dict with ims_path, index_path (or None), n_pairs, nx, ny,
    frames_per_pair, pair_bytes, frame_bytes.
    """
    given = Path(str(path).strip())
    if not str(given):
        raise IOError('empty .ims path')
    if given.is_file():
        if given.suffix.lower() != '.ims':
            raise IOError('not a .ims file: %s' % given)
        folder = given.parent
        if _looks_like_index(given.stat().st_size):
            index_path, stream_path = given, None
        else:
            index_path, stream_path = None, given
    elif given.is_dir():
        folder = given
        index_path, stream_path = None, None
    else:
        raise IOError('no such file or folder: %s' % given)

    ims_files = sorted(folder.glob('*.ims'), key=lambda p: p.stat().st_size)
    if not ims_files:
        raise IOError('no *.ims files in %s' % folder)
    if stream_path is None:
        stream_path = ims_files[-1]  # the stream dwarfs the index
    if index_path is None:
        for candidate in ims_files:
            if candidate != stream_path and _looks_like_index(candidate.stat().st_size):
                index_path = candidate
                break

    if index_path is not None:
        idx_frames, idx_nx, idx_ny, _, n_records = _parse_index_header(index_path)
        frames_per_pair, nx, ny = idx_frames, idx_nx, idx_ny
    if nx is None or ny is None:
        raise IOError(
            'no index .ims next to %s — pass nx=/ny= explicitly '
            '(e.g. nx=2432, ny=2048)' % stream_path
        )
    nx, ny, frames_per_pair = int(nx), int(ny), int(frames_per_pair)
    if (frames_per_pair * ny * nx) % 2:
        raise IOError(
            '12-bit packing needs an even pixel count per pair, got '
            'frames=%d ny=%d nx=%d' % (frames_per_pair, ny, nx)
        )
    pair_bytes = frames_per_pair * ny * nx * 3 // 2
    stream_size = stream_path.stat().st_size
    if stream_size % pair_bytes:
        raise IOError(
            '%s size %d is not a whole number of pairs (%d bytes each '
            'for %d frames of %dx%d 12-bit packed)' % (
                stream_path, stream_size, pair_bytes,
                frames_per_pair, nx, ny,
            )
        )
    n_pairs = stream_size // pair_bytes
    if index_path is not None and n_records != n_pairs:
        raise IOError(
            'index %s lists %d pairs but stream %s holds %d' % (
                index_path, n_records, stream_path, n_pairs,
            )
        )
    return {
        'ims_path': str(stream_path),
        'index_path': str(index_path) if index_path is not None else None,
        'n_pairs': n_pairs,
        'nx': nx,
        'ny': ny,
        'frames_per_pair': frames_per_pair,
        'pair_bytes': pair_bytes,
        'frame_bytes': pair_bytes // frames_per_pair,
        'backend': 'readim7-raw12',
    }


def _memmap(stream_path):
    handle = _MMAPS.get(stream_path)
    if handle is None:
        handle = np.memmap(stream_path, dtype=np.uint8, mode='r')
        _MMAPS[stream_path] = handle
    return handle


def _unpack12_pair(raw, nx, ny, frames_per_pair):
    """Unpack one pair's raw bytes to uint16 frames, shape (frames, ny, nx)."""
    n_pixels = nx * ny
    frames = np.empty((frames_per_pair, n_pixels), dtype=np.uint16)
    frame_bytes = len(raw) // frames_per_pair
    for f in range(frames_per_pair):
        seg = raw[f * frame_bytes:(f + 1) * frame_bytes]
        b0 = seg[0::3].astype(np.uint16)
        b1 = seg[1::3].astype(np.uint16)
        b2 = seg[2::3].astype(np.uint16)
        frames[f, 0::2] = b0 | ((b1 & 0x0F) << 8)
        frames[f, 1::2] = (b1 >> 4) | (b2 << 4)
    return frames.reshape(frames_per_pair, ny, nx)


def read_ims_pair(path, idx):
    """Read one dual-frame pair from a camera stream.

    Parameters
    ----------
    path: str | Path | dict
        Run folder, direct ``.ims`` path, or an :func:`ims_info` dict.
    idx: int
        Zero-based pair index.

    Returns
    -------
    (pulseA, pulseB): uint16 arrays of shape (ny, nx).
    """
    info = path if isinstance(path, dict) else ims_info(path)
    idx = int(idx)
    if not 0 <= idx < info['n_pairs']:
        raise IndexError(
            'pair %d out of range for %d pairs in %s' % (
                idx, info['n_pairs'], info['ims_path'],
            )
        )
    stream = _memmap(info['ims_path'])
    offset = idx * info['pair_bytes']
    raw = np.array(stream[offset:offset + info['pair_bytes']])
    frames = _unpack12_pair(raw, info['nx'], info['ny'], info['frames_per_pair'])
    return frames[0], frames[1]


def read_ims_frame(path, idx, pulse=0):
    """Read a single pulse frame (0 = A, 1 = B) from a camera stream pair."""
    pulse_a, pulse_b = read_ims_pair(path, idx)
    return pulse_a if int(pulse) == 0 else pulse_b
