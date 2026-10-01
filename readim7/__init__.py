"""
readim7: A fast DaVis8 file reader and writer for Python
=======================================================

Documentation is available in the docstrings.

Contents
--------
readim7 is a wrapper for for C-code provided by LaVision as the core
functionality. Additional functions are provided to load array data into memory
with access to data as numpy arrays and attributes as dictionaires.
"""
from __future__ import division, print_function, absolute_import

from . import core
from . import extra
from . import ims

# collect buffer formats together
BUFFER_FORMATS = {}
for s in dir(core):
    if s.startswith('BUFFER_FORMAT'):
        BUFFER_FORMATS[getattr(core, s)] = s

# collect error codes
ERROR_CODES = {}
for s in dir(core):
    if s.startswith('IMREAD_ERR'):
        ERROR_CODES[getattr(core, s)] = s

del(s)

from .core import read_file, write_file, get_vector_components

from .ims import ims_info, read_ims_pair, read_ims_frame

from .extra import *

from .vectors import (
    VectorField,
    unpack_vector_field,
    compute_coordinates,
)

from .attributes import (
    parse_davis_attributes,
    parse_scale_string,
    parse_time_value,
)

from .pivpy_io import (
    to_dataset,
    to_pivpy,
    load_sequence,
    read_image_pair,
)

from .export import (
    export_pivmat,
    export_tecplot,
    export_hdf5,
    export_openpiv_txt,
)

from .transforms import (
    flip_ud,
    flip_lr,
    rotate_90_cw,
    rotate_90_ccw,
    rotate_180,
    swap_uv,
    invert_uv,
    scale_coords,
    scale_velocity,
    transform,
)

from .calc import (
    calc_vorticity,
    calc_divergence,
    calc_shear_strain,
    calc_turbulent_statistics,
    normalized_median_filter,
)
