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

sources = ['ReadIM/src/pybind_core.cpp', 'ReadIM/src/ReadIMX.cpp', 'ReadIM/src/ReadIM7.cpp']
sources += ['ReadIM/src/zlib/' + s for s in zlib_sources]
for s in sources:
    assert os.path.isfile(s), s

ext_modules = [
    Pybind11Extension(
        'ReadIM._core',
        sources=sources,
        include_dirs=['ReadIM/src'],
        # No explicit cxx_std: it would apply -std=c++11 to every source in
        # this extension, including the vendored zlib .c files, and Apple
        # clang rejects a C++ std flag on a C compile unit. Compilers'
        # C++14+ defaults are already enough for this binding.
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
