"""Tests for readim7.ims (DaVis camera stream reader). Run with:
python -m pytest readim7/tests/test_ims.py
or just: python readim7/tests/test_ims.py

All data here is synthetic and self-contained (no 14 GB drive file needed).
"""
from __future__ import division, print_function, absolute_import

import struct

import numpy as np
import pytest

import readim7
from readim7 import ims as ims_mod


NX, NY, FRAMES, N_PAIRS = 32, 16, 2, 5


def _pack12(pixels):
    """Inverse of the stream packing: even-count uint16 array -> packed bytes."""
    flat = np.asarray(pixels, dtype=np.uint16).reshape(-1)
    assert flat.size % 2 == 0
    assert flat.max() < 4096
    pairs = flat.reshape(-1, 2)
    b0 = (pairs[:, 0] & 0xFF).astype(np.uint8)
    b1 = (((pairs[:, 0] >> 8) & 0x0F) | ((pairs[:, 1] & 0x0F) << 4)).astype(np.uint8)
    b2 = ((pairs[:, 1] >> 4) & 0xFF).astype(np.uint8)
    out = np.empty(pairs.shape[0] * 3, dtype=np.uint8)
    out[0::3], out[1::3], out[2::3] = b0, b1, b2
    return out


def _make_set(folder, nx=NX, ny=NY, frames=FRAMES, n_pairs=N_PAIRS, seed=7):
    """Write a synthetic stream + index pair. Returns (stream, index, truth)."""
    rng = np.random.default_rng(seed)
    truth = rng.integers(0, 4096, size=(n_pairs, frames, ny, nx), dtype=np.uint16)
    stream = folder / 'Camera1-1.ims'
    with open(stream, 'wb') as f:
        for i in range(n_pairs):
            f.write(_pack12(truth[i]).tobytes())
    frame_bytes = ny * nx * 3 // 2
    index = folder / 'Camera1-0.ims'
    with open(index, 'wb') as f:
        f.write(struct.pack('<6I', 1, 0, frames, nx, ny, 16))
        f.write(b'\x00' * (1024 - 24))
        for i in range(n_pairs):
            off = i * frames * frame_bytes
            f.write(struct.pack('<10I', 1,
                                off & 0xFFFFFFFF, (off >> 32) & 0xFFFFFFFF,
                                frame_bytes, 0, 1,
                                (off + frame_bytes) & 0xFFFFFFFF,
                                ((off + frame_bytes) >> 32) & 0xFFFFFFFF,
                                frame_bytes, 0))
    return stream, index, truth


def test_info_from_folder(tmp_path):
    stream, index, _ = _make_set(tmp_path)
    info = readim7.ims_info(str(tmp_path))
    assert info['ims_path'] == str(stream)
    assert info['index_path'] == str(index)
    assert (info['n_pairs'], info['nx'], info['ny']) == (N_PAIRS, NX, NY)
    assert info['pair_bytes'] == FRAMES * NY * NX * 3 // 2


def test_info_from_direct_stream_file(tmp_path):
    stream, _, _ = _make_set(tmp_path)
    info = readim7.ims_info(str(stream))
    assert info['n_pairs'] == N_PAIRS


def test_info_from_index_file(tmp_path):
    _, index, _ = _make_set(tmp_path)
    info = readim7.ims_info(str(index))
    assert info['n_pairs'] == N_PAIRS


def test_info_missing_index_needs_geometry(tmp_path):
    stream, index, _ = _make_set(tmp_path)
    index.unlink()
    with pytest.raises(IOError):
        readim7.ims_info(str(stream))
    info = readim7.ims_info(str(stream), nx=NX, ny=NY)
    assert info['n_pairs'] == N_PAIRS
    assert info['index_path'] is None


def test_read_roundtrip(tmp_path):
    _, _, truth = _make_set(tmp_path)
    info = readim7.ims_info(str(tmp_path))
    for i in range(N_PAIRS):
        pulse_a, pulse_b = readim7.read_ims_pair(info, i)
        assert pulse_a.shape == (NY, NX)
        assert pulse_a.dtype == np.uint16
        np.testing.assert_array_equal(pulse_a, truth[i, 0])
        np.testing.assert_array_equal(pulse_b, truth[i, 1])
    np.testing.assert_array_equal(
        readim7.read_ims_frame(str(tmp_path), 3, pulse=1), truth[3, 1])


def test_read_out_of_range(tmp_path):
    _make_set(tmp_path)
    with pytest.raises(IndexError):
        readim7.read_ims_pair(str(tmp_path), N_PAIRS)


def test_module_exported():
    assert ims_mod is readim7.ims


if __name__ == '__main__':
    import tempfile
    import pathlib
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and name != 'test_module_exported':
            with tempfile.TemporaryDirectory() as d:
                fn(pathlib.Path(d))
    test_module_exported()
    print('OK')
