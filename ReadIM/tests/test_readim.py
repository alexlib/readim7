"""Smoke test for the pybind11 _core binding. Run with: python -m pytest ReadIM/tests
or just: python ReadIM/tests/test_readim.py
"""
from __future__ import division, print_function, absolute_import

import numpy as np
import ReadIM


def test_read_sample_image():
    filename = ReadIM.get_sample_image_filenames()[0]
    buff, atts = ReadIM.get_Buffer_andAttributeList(filename)
    array, _ = ReadIM.buffer_as_array(buff)
    assert array.ndim == 3
    assert array.shape == (buff.nf, buff.ny, buff.nx)
    assert isinstance(atts, dict)


def test_read_sample_vector():
    filename = ReadIM.get_sample_vector_filenames()[0]
    buff, atts = ReadIM.get_Buffer_andAttributeList(filename)
    array, _ = ReadIM.buffer_as_array(buff)
    components = ReadIM.get_vector_components(buff.image_sub_type) * buff.nf
    assert array.shape == (components, buff.ny, buff.nx)


def test_write_roundtrip(tmp_path):
    buff = ReadIM.newBuffer(window=[(0, 0), (10, 10)], nx=5, ny=5,
                             vectorGrid=1, image_sub_type=ReadIM.core.BUFFER_FORMAT_VECTOR_2D,
                             frames=1)
    buff.array[...] = np.arange(buff.array.size, dtype=buff.array.dtype).reshape(buff.array.shape)

    out_file = str(tmp_path / 'roundtrip.im7')
    ReadIM.WriteIM7(out_file, buff, {'note': 'hello'})

    buff2, atts2 = ReadIM.get_Buffer_andAttributeList(out_file)
    array2, _ = ReadIM.buffer_as_array(buff2)

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
