#!/usr/bin/env python

"""
setup.py for ReadIM

Builds ReadIM._core, a pybind11 extension wrapping LaVision's ReadIMX/ReadIM7
C++ file readers.

    python -m build            # sdist + wheel
    pip install .              # local install
    pip wheel . -w dist        # single wheel for this platform

For binary wheels across Linux/macOS/Windows use cibuildwheel (see
.github/workflows/wheels.yml).

note to deploy:
update version info below, then

    python -m build
    twine upload dist/*
"""

version = '0.9.0'

import io
import os

from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

here = os.path.abspath(os.path.dirname(__file__))

zlib_sources = ['adler32.c', 'compress.c', 'deflate.c', 'infblock.c',
                 'infcodes.c', 'inffast.c', 'inflate.c', 'infutil.c',
                 'inftrees.c', 'trees.c', 'uncompr.c', 'zutil.c']
zlib_sources = ['ReadIM/src/zlib/' + s for s in zlib_sources]

sources = ['ReadIM/src/pybind_core.cpp', 'ReadIM/src/ReadIMX.cpp', 'ReadIM/src/ReadIM7.cpp']
for s in sources + zlib_sources:
    assert os.path.isfile(s), s

# The vendored zlib sources are plain C and must be compiled without a C++
# std flag (Apple clang errors out if one is passed to a .c file, and
# Pybind11Extension always adds one for its own sources). Build them as a
# separate static library with the plain C compiler, then link the pybind11
# extension against it -- the standard pattern for bundling a C library
# alongside a C++ extension (e.g. Pillow, psycopg2).
libraries = [('readim_zlib', dict(sources=zlib_sources))]

ext_modules = [
    Pybind11Extension(
        'ReadIM._core',
        sources=sources,
        include_dirs=['ReadIM/src'],
        libraries=['readim_zlib'],
    ),
]

description = 'Read and write native DaVis images and vectors filetypes VC7 and IM7'
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except IOError:
    long_description = description

setup(
    name='ReadIM',
    description=description,
    version=version,
    url='https://bitbucket.org/fleming79/readim',
    libraries=libraries,
    ext_modules=ext_modules,
    cmdclass={'build_ext': build_ext},
    packages=['ReadIM'],
    package_data={'ReadIM': ['sample_files/*.*']},
    include_package_data=True,
    install_requires=['numpy'],
    setup_requires=['pybind11>=2.10'],
    long_description_content_type='text/markdown',
    long_description=long_description,
    license='MIT',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
    ],
    keywords='IM7 VC7 DaVis LaVision FileIO PIV',
)
