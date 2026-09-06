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

from .extra import *
