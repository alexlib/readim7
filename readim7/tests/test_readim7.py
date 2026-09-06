"""Smoke test for the pybind11 _core binding. Run with: python -m pytest readim7/tests
or just: python readim7/tests/test_readim7.py
"""
from __future__ import division, print_function, absolute_import

import numpy as np
import readim7


def test_read_sample_image():
    filename = readim7.get_sample_image_filenames()[0]
    buff, atts = readim7.get_Buffer_andAttributeList(filename)
    array, _ = readim7.buffer_as_array(buff)
    assert array.ndim == 3
    assert array.shape == (buff.nf, buff.ny, buff.nx)
    assert isinstance(atts, dict)


def test_read_sample_vector():
    filename = readim7.get_sample_vector_filenames()[0]
    buff, atts = readim7.get_Buffer_andAttributeList(filename)
    array, _ = readim7.buffer_as_array(buff)
    components = readim7.get_vector_components(buff.image_sub_type) * buff.nf
    assert array.shape == (components, buff.ny, buff.nx)


def test_write_roundtrip(tmp_path):
    buff = readim7.newBuffer(window=[(0, 0), (10, 10)], nx=5, ny=5,
                             vectorGrid=1, image_sub_type=readim7.core.BUFFER_FORMAT_VECTOR_2D,
                             frames=1)
    buff.array[...] = np.arange(buff.array.size, dtype=buff.array.dtype).reshape(buff.array.shape)

    out_file = str(tmp_path / 'roundtrip.im7')
    readim7.WriteIM7(out_file, buff, {'note': 'hello'})

    buff2, atts2 = readim7.get_Buffer_andAttributeList(out_file)
    array2, _ = readim7.buffer_as_array(buff2)

    assert array2.shape == buff.array.shape
    assert np.allclose(array2, buff.array)
    assert atts2.get('note') == 'hello'


if __name__ == '__main__':
    import tempfile, pathlib
    test_read_sample_image()
    test_read_sample_vector()
    with tempfile.TemporaryDirectory() as d:
        test_write_roundtrip(pathlib.Path(d))
    print('OK')
