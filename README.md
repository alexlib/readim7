Overview
========

readim7 is a C++ wrapper to load DaVis Images and Vectors and is a 'low level' wrapper of C++ libraries provided by LaVision GMBH.
ReadIMX source was latest updated by LaVision in Aug-2014.

Source: https://github.com/alexlib/readim7

Forked from the original `ReadIM` project by fleming79 (https://bitbucket.org/fleming79/readim),
repackaged as `readim7` with pybind11-based bindings and prebuilt binary wheels.

A higher level module: "[IM](https://bitbucket.org/fleming79/im)" exists to work with images and vectors. It isn't hosted on PyPi however it can still be installed with pip. It provides more convenient file read / write capability and is the recommended starting point to read and write IM7/VC7 files.

Installation
------------

This module must be compiled to work correctly. If there isn't a binary on pip you'll need to have the appropriate build tools installed for it to compile and install properly.

```python
pip install readim7
```

Usage
-----

To load a .vc7 file run

```python
import readim7
filename = readim7.extra.get_sample_vector_filenames()[0]
buffer, atts = readim7.get_Buffer_andAttributeList(filename)
v_array, _ = readim7.buffer_as_array(buffer)
v_array.shape
```

similarly for a .im7 file run

```python
import readim7
filename = readim7.extra.get_sample_image_filenames()[0]
buffer, atts = readim7.get_Buffer_andAttributeList(filename)
im_array, _ = readim7.buffer_as_array(buffer)
im_array.shape
```

`buffer` and `atts` are plain Python objects (a `BunchMappable` wrapping numpy
arrays, and a `dict`) — nothing needs to be destroyed manually.

Writing files
-------------

```python
buff = readim7.newBuffer(window=[(0, 0), (100, 100)], image_sub_type=readim7.core.BUFFER_FORMAT_VECTOR_2D)
buff.array[...] = v_array   # fill in your data
readim7.WriteIM7('saved_file.im7', buff, {'attribute': 'value'})
```

VC7 files
---------

Depending on the filetype, there could be several frames that make up the optimal vector field as decided by DaVis. For a full description of the buffer you should contact LaVision support. Below is a link for some code snippets. The higher level "[IM](https://bitbucket.org/fleming79/im)" automatically reads the optimal result.

see the function "_get_vectors" at https://bitbucket.org/fleming79/im/src/master/IM/core.py

