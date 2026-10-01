"""
test_piv_suite.py: Comprehensive test suite for PIVPy bridge, exporters, transforms, and calculus.
"""

import os
import tempfile
import pytest
import numpy as np
import scipy.io
import h5py

import readim7


@pytest.fixture
def sample_2c():
    return readim7.get_sample_vector_filenames()[0]  # 2C.VC7


@pytest.fixture
def sample_3c():
    return readim7.get_sample_vector_filenames()[1]  # 3C.VC7


@pytest.fixture
def sample_im7():
    return readim7.get_sample_image_filenames()[0]


def test_unpack_2c_vector(sample_2c):
    from pathlib import Path
    # Test Path object input
    vf = readim7.unpack_vector_field(Path(sample_2c))
    assert vf.shape == (43, 57)
    assert len(vf.x) == 57
    assert len(vf.y) == 43
    assert not vf.is_3d
    assert vf.w is None
    assert vf.vmag.shape == (43, 57)
    assert vf.units['u'] == 'm/s'
    assert vf.extent[0] < vf.extent[1]
    assert vf.extent[2] < vf.extent[3]


def test_unpack_3c_vector(sample_3c):
    vf = readim7.unpack_vector_field(sample_3c)
    assert vf.shape == (30, 42)
    assert vf.is_3d
    assert vf.w is not None
    assert vf.peak_ratio is not None
    assert vf.vmag.shape == (30, 42)


def test_unpack_vector_options(sample_2c):
    # Test first choice vs optimal
    vf_opt = readim7.unpack_vector_field(sample_2c, choice_preference="optimal")
    vf_first = readim7.unpack_vector_field(sample_2c, choice_preference="first")
    assert vf_opt.shape == vf_first.shape

    # Test invert_y=False
    vf_no_inv = readim7.unpack_vector_field(sample_2c, invert_y=False)
    assert vf_no_inv.y[0] > vf_no_inv.y[-1]  # decreasing y

    # Test fill_invalid_with_nan=False
    vf_no_nan = readim7.unpack_vector_field(sample_2c, fill_invalid_with_nan=False)
    assert not np.isnan(vf_no_nan.u).any()


def test_to_dataset_and_pivpy(sample_2c, sample_3c):
    ds2 = readim7.to_dataset(sample_2c)
    assert 'u' in ds2.data_vars
    assert 'v' in ds2.data_vars
    assert 'ch' in ds2.data_vars
    assert 't' in ds2.coords
    assert ds2.attrs['units'] == ['mm', 'mm', 'm/s', 'm/s']
    assert ds2.attrs['dt'] == 0.01
    assert ds2.attrs['delta_t'] == 0.01
    assert ds2['u'].attrs['units'] == 'm/s'
    assert ds2['x'].attrs['units'] == 'mm'

    ds3 = readim7.to_pivpy(sample_3c)
    assert 'w' in ds3.data_vars
    assert ds3.attrs['is_3d'] is True


def test_parse_davis_attributes(sample_2c, sample_im7):
    _, atts2 = readim7.get_Buffer_andAttributeList(sample_2c)
    meta2 = readim7.parse_davis_attributes(atts2)
    assert meta2['delta_t'] == 0.01
    assert meta2['date'] == '18.05.10'
    assert 'x' in meta2['scales']
    assert 'y' in meta2['scales']
    assert meta2['scales']['x']['factor'] > 0

    _, atts_im = readim7.get_Buffer_andAttributeList(sample_im7)
    meta_im = readim7.parse_davis_attributes(atts_im)
    assert meta_im['davis_version'] == '7.2.2.249'


def test_read_image_pair():
    # 2-frame 1camera.im7
    img1 = readim7.get_sample_image_filenames()[0]
    fa, fb = readim7.read_image_pair(img1)
    assert fa.shape == (1024, 1376)
    assert fb.shape == (1024, 1376)
    assert fa.dtype == np.uint16

    # 4-frame 2cameras.im7
    img2 = readim7.get_sample_image_filenames()[1]
    c0a, c0b = readim7.read_image_pair(img2, camera=0)
    c1a, c1b = readim7.read_image_pair(img2, camera=1)
    assert c0a.shape == (1024, 1376)
    assert c1a.shape == (1024, 1376)


def test_pivpy_accessor_direct(sample_2c):
    try:
        import pivpy
        ds = readim7.to_pivpy(sample_2c)
        assert ds.piv.delta_t == 0.01
        vort = ds.piv.vorticity()
        assert 'u' in vort.data_vars
    except ImportError:
        pass


def test_load_sequence(sample_2c):
    ds_seq = readim7.load_sequence([sample_2c, sample_2c], t_coords=[0.0, 0.5])
    assert ds_seq.sizes['t'] == 2
    assert list(ds_seq.coords['t'].values) == [0.0, 0.5]


def test_load_sequence_dask(sample_2c):
    try:
        import dask
        ds_chunked = readim7.load_sequence([sample_2c, sample_2c], chunks={'t': 1})
        assert hasattr(ds_chunked.u.data, 'dask')
    except ImportError:
        pass


def test_export_pivmat(sample_2c):
    vf = readim7.unpack_vector_field(sample_2c)
    with tempfile.TemporaryDirectory() as td:
        mat_file = os.path.join(td, 'pivmat_test.mat')
        readim7.export_pivmat(mat_file, vf)
        data = scipy.io.loadmat(mat_file)
        assert 'vx' in data
        assert 'vy' in data
        unit_vx = str(data['unitvx']).strip("[]' ")
        assert unit_vx == 'm/s'


def test_export_tecplot(sample_3c):
    ds = readim7.to_pivpy(sample_3c)
    with tempfile.TemporaryDirectory() as td:
        dat_file = os.path.join(td, 'tecplot_test.dat')
        readim7.export_tecplot(dat_file, ds, title="Test Tecplot")
        with open(dat_file) as f:
            lines = [f.readline() for _ in range(4)]
        assert 'TITLE = "Test Tecplot"' in lines[0]
        assert 'VARIABLES = "X", "Y", "U", "V", "W", "Vmag", "Choice", "Mask"' in lines[1]
        assert 'ZONE I=42, J=30, F=POINT' in lines[2]


def test_export_hdf5(sample_2c):
    ds = readim7.to_pivpy(sample_2c)
    with tempfile.TemporaryDirectory() as td:
        h5_file = os.path.join(td, 'h5_test.h5')
        readim7.export_hdf5(h5_file, ds)
        with h5py.File(h5_file, 'r') as h:
            assert 'piv/u' in h
            assert 'piv/v' in h
            assert h['piv/u'].shape == (43, 57)


def test_export_openpiv_txt(sample_2c):
    vf = readim7.unpack_vector_field(sample_2c)
    with tempfile.TemporaryDirectory() as td:
        txt_file = os.path.join(td, 'openpiv_test.txt')
        readim7.export_openpiv_txt(txt_file, vf)
        arr = np.loadtxt(txt_file)
        assert arr.shape == (43 * 57, 5)


def test_transforms(sample_2c):
    vf = readim7.unpack_vector_field(sample_2c)
    orig_u = vf.u.copy()

    # Flip UD
    f_ud = readim7.flip_ud(vf)
    assert np.allclose(f_ud.u, orig_u[::-1, :], equal_nan=True)

    # Flip LR
    f_lr = readim7.flip_lr(vf)
    assert np.allclose(f_lr.u, -orig_u[:, ::-1], equal_nan=True)

    # Invert UV
    inv = readim7.invert_uv(vf)
    assert np.allclose(inv.u, -orig_u, equal_nan=True)

    # Scale coords
    sc = readim7.scale_coords(vf, factor=0.001)
    assert np.isclose(sc.x[0], vf.x[0] * 0.001)

    # Scale velocity
    sv = readim7.scale_velocity(vf, factor=1000.0)
    assert np.allclose(sv.u, vf.u * 1000.0, equal_nan=True)

    # Chained transform on Dataset
    ds = readim7.to_pivpy(sample_2c)
    ds_t = readim7.transform(ds, ['rotate_90_cw', 'scale_velocity:2.0'])
    assert ds_t.u.shape == (1, 57, 43)


def test_calculus_and_statistics(sample_2c):
    vf = readim7.unpack_vector_field(sample_2c)
    vort = readim7.calc_vorticity(vf)
    div = readim7.calc_divergence(vf)
    strain = readim7.calc_shear_strain(vf)

    assert vort.shape == vf.shape
    assert div.shape == vf.shape
    assert strain.shape == vf.shape

    # Normalized median filter
    outliers = readim7.normalized_median_filter(vf.u, vf.v, threshold=2.0)
    assert outliers.shape == vf.shape
    # All masked points (choice == 0) must be flagged
    assert np.all(outliers[vf.mask])

    # Turbulent statistics
    ds_seq = readim7.load_sequence([sample_2c, sample_2c], t_coords=[0, 1])
    stats = readim7.calc_turbulent_statistics(ds_seq)
    assert 'u_mean' in stats
    assert 'tke' in stats
    assert stats['u_mean'].shape == vf.shape
