"""
Unit tests for readim7.viewer (loader, colormaps, standalone, and reactive marimo viewer).
"""
import numpy as np
import pytest
from pathlib import Path

import readim7
from readim7.viewer.colormaps import (
    AVAILABLE_COLORMAPS,
    get_lut_rgba,
    get_lut_rgb8,
    normalize_to_uint8,
    apply_colormap_rgba,
    apply_colormap_rgb8,
)
from readim7.viewer.loader import (
    open_dataset,
    ImsDataSource,
    Im7DataSource,
    Vc7DataSource,
)
from readim7.tests.test_ims import _make_set, NX, NY, FRAMES, N_PAIRS


def test_colormaps_luts():
    for cmap in AVAILABLE_COLORMAPS:
        rgba = get_lut_rgba(cmap)
        assert rgba.shape == (256, 4)
        assert rgba.dtype == np.float32
        assert 0.0 <= rgba.min() and rgba.max() <= 1.0

        rgb8 = get_lut_rgb8(cmap)
        assert rgb8.shape == (256, 3)
        assert rgb8.dtype == np.uint8


def test_colormap_application():
    arr = np.linspace(0, 4095, 100, dtype=np.uint16).reshape((10, 10))
    u8 = normalize_to_uint8(arr, 0, 4095)
    assert u8.shape == (10, 10)
    assert u8.dtype == np.uint8
    assert u8[0, 0] == 0
    assert u8[-1, -1] == 255

    rgba = apply_colormap_rgba(arr, 0, 4095, "viridis")
    assert rgba.shape == (10, 10, 4)
    assert rgba.dtype == np.float32

    rgb8 = apply_colormap_rgb8(arr, 0, 4095, "turbo")
    assert rgb8.shape == (10, 10, 3)
    assert rgb8.dtype == np.uint8


def test_loader_sample_im7():
    samples = readim7.get_sample_image_filenames()
    assert len(samples) > 0
    ds = open_dataset(samples[0])
    assert isinstance(ds, Im7DataSource)
    assert ds.num_frames > 0
    assert ds.nx > 0 and ds.ny > 0
    frame = ds.get_frame(0, 0)
    assert frame.shape == (ds.ny, ds.nx)
    vmin, vmax, p1, p99 = ds.get_stats(0, 0)
    assert vmin <= p1 <= p99 <= vmax


def test_loader_sample_vc7():
    samples = readim7.get_sample_vector_filenames()
    assert len(samples) > 0
    ds = open_dataset(samples[0])
    assert isinstance(ds, Vc7DataSource)
    assert ds.num_frames > 0
    assert "Velocity Magnitude |V|" in ds.channels
    frame = ds.get_frame(0, 0)
    assert frame.shape == (ds.ny, ds.nx)


def test_loader_synthetic_ims(tmp_path):
    stream, index, truth = _make_set(tmp_path)
    ds = open_dataset(tmp_path)
    assert isinstance(ds, ImsDataSource)
    assert ds.num_frames == N_PAIRS
    assert ds.nx == NX and ds.ny == NY
    assert len(ds.channels) == 2

    # Frame 0 pulse A
    fa = ds.get_frame(0, 0)
    np.testing.assert_array_equal(fa, truth[0, 0])

    # Frame 0 pulse B
    fb = ds.get_frame(0, 1)
    np.testing.assert_array_equal(fb, truth[0, 1])


def test_standalone_viewer_init():
    try:
        import dearpygui.dearpygui as dpg
    except ImportError:
        pytest.skip("dearpygui not installed")

    from readim7.viewer.standalone import StandaloneViewer
    samples = readim7.get_sample_image_filenames()
    ds = open_dataset(samples[0])
    viewer = StandaloneViewer(ds)
    assert viewer.dataset is ds
    assert viewer.current_frame == 0
    assert viewer.colormap == "gray"


def test_marimo_app_importable():
    from readim7.viewer.marimo_app import app
    assert app is not None
