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

DaVis camera streams (.ims)
----------------------------

High-speed streaming files (`.ims`) use a different container that the
ReadIMX C++ library cannot parse. `readim7.ims` reads them directly with
numpy (12-bit packed frames, no headers), so it works on every platform —
including macOS ARM, where `lvpyio` has no wheels:

```python
import readim7
info = readim7.ims_info('/path/to/run_folder')  # or .../Camera1-1.ims directly
# {'ims_path': ..., 'n_pairs': 1000, 'nx': 2432, 'ny': 2048, ...}
pulse_a, pulse_b = readim7.read_ims_pair(info, 0)  # uint16 (ny, nx) frames
frame_b = readim7.read_ims_frame(info, 42, pulse=1)
```

The run folder normally holds the large stream file (`Camera1-1.ims`) plus a
small index sibling (`Camera1-0.ims`, 1024-byte header + 40 bytes per pair)
that provides the sensor geometry. If the index is missing, pass the
geometry explicitly: `readim7.ims_info(stream, nx=2432, ny=2048)`.

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


Interactive Viewers
-------------------

`readim7` includes two ultra-fast viewers for previewing `.ims` streams, `.im7` image sequences, and `.vc7` vector fields:

### 1. Ultra-fast Standalone OpenGL Viewer (`readim7-view`)
A lightweight, sub-second launch desktop viewer built on Dear PyGui (hardware-accelerated OpenGL):
- **Smooth playback & scrubbing** (up to 60+ FPS directly from memory-mapped files)
- **Mouse pan & scroll-wheel zoom**
- **Pulse A / Pulse B & vector component selection**
- **Auto-contrast windowing** and scientific colormaps (Viridis, Turbo, Plasma, Inferno, Grayscale)
- **Keyboard shortcuts**:
  - `Space`: Play / Pause
  - `Left` / `Right`: Previous / Next frame
  - `A` / `B`: Toggle Pulse A / Pulse B
  - `C`: Auto-contrast
  - `R`: Reset pan & zoom

```bash
# Install optional viewer dependencies
pip install "readim7[viewer]"

# Launch directly with a file or folder:
readim7-view /path/to/Camera1-1.ims
readim7-view /path/to/run_folder/
readim7-view /path/to/image.im7
```

### 2. Reactive Marimo Viewer (`readim7-marimo`)
A notebook-ready reactive web app using [Marimo](https://marimo.io):
- Interactive scrubbing slider, pulse/channel toggle, contrast range slider, colormap picker, and dataset metadata inspector.
- Runs in browser or inside notebooks:

```bash
readim7-marimo /path/to/file.ims
# or with marimo directly:
marimo run readim7/viewer/marimo_app.py
```

### 3. macOS Finder Integration (Quick Action & App Droplet)
To open files directly from macOS Finder:

```bash
readim7-finder-action
```

This installs:
1. **Finder Quick Action**: Right-click any `.ims`, `.im7`, `.vc7` file or folder in Finder -> **Quick Actions** -> **Open with readim7-view**.
2. **Droplet App (`~/Applications/readim7 Viewer.app`)**: Drag and drop files/folders onto the app icon, or use Finder's **Open With...** menu.

