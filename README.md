Overview
========

readim7 is a C++ wrapper to load DaVis Images and Vectors and is a 'low level' wrapper of C++ libraries provided by LaVision GMBH.
ReadIMX source was latest updated by LaVision in Aug-2014.

Source: https://github.com/alexlib/readim7

Forked from the original `ReadIM` project by fleming79 (https://bitbucket.org/fleming79/readim),
repackaged as `readim7` with pybind11-based bindings and prebuilt binary wheels.

A higher level module: "[IM](https://bitbucket.org/fleming79/im)" exists to work with images and vectors. It isn't hosted on PyPi however it can still be installed with pip. It provides more convenient file read / write capability and is the recommended starting point to read and write IM7/VC7 files.

Why readim7? Feature Comparison
-------------------------------

| Capability | Official `lvpyio` | Legacy `libim7-py3` / `IM` | `pyFlowStat` / `PIVTOOLs` | **`readim7`** |
| :--- | :---: | :---: | :---: | :---: |
| **Platform Portability** | Closed binary, **no macOS ARM** | Fragile ctypes / Python 2 | Incomplete reader bindings | **Linux, Windows & macOS (native ARM64 + x86)** |
| **All Vector Formats** (2D, 3D, Multi-Peak Choice 1..5) | Partial | 2D / basic only | Basic | **All 5 DaVis formats + full choice map** |
| **All Image Formats** (Int16, Float32, Zipped, Multi-camera) | Yes | Partial | Partial | **Tested & verified on all types** |
| **High-Speed `.ims` Streams** | Windows only / C++ library | No | No | **Native pure-NumPy 12-bit reader** |
| **PIVPy Bridge** (`xarray.Dataset`, `ds.piv`) | No | No | No | **Native 1-liner (`readim7.to_pivpy`)** |
| **OpenPIV Image Pair Reader** | No | No | No | **`readim7.read_image_pair`** |
| **Sequence Loading & Dask Chunking** | No | Manual loops | Custom scripts | **Natural numerical sort + lazy Dask** |
| **Exporters** (PIVMAT, Tecplot, HDF5, OpenPIV) | No | PIVMAT only | Custom HDF5/Tecplot | **All 4 universal formats built-in** |
| **Flow Calculus & Outlier Validation** | No | No | Custom scripts | **Vorticity, divergence, TKE, Westerweel test** |
| **Interactive GUI Viewers** | No | No | No | **Hardware-accelerated OpenGL + Marimo + macOS Finder Quick Action** |


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

VC7 Vector Files & PIVPy / OpenPIV Bridge
----------------------------------------

`readim7` provides full, high-level integration with the **PIVPy** and **OpenPIV** ecosystems:

### 1. Direct one-liner into PIVPy (`xarray.Dataset`)
Convert `.vc7` or `.im7` files directly into an `xarray.Dataset` compliant with PIVPy:

```python
import readim7

# Convert VC7 to PIVPy dataset
ds = readim7.to_pivpy("B00001.VC7")   # or readim7.to_dataset(...)

# Standard PIVPy variables (u, v, w, ch, p, mask) and coordinates (x, y, t):
print(ds)
# <xarray.Dataset>
# Dimensions:  (t: 1, y: 43, x: 57)
# Coordinates:
#   * x  (x) float64 -143.6 ... 193.3 (mm)
#   * y  (y) float64 -324.8 ... -72.1 (mm)
#   * t  (t) int64 0
# Data variables:
#     u     (t, y, x) float32 ... (m/s)
#     v     (t, y, x) float32 ... (m/s)
#     ch    (t, y, x) int32   ... (choice map: 1-4 peak, 5 post-processed)
#     mask  (t, y, x) int8    ... (1=masked, 0=valid)

# Load an entire sequence into a time-resolved dataset:
seq_ds = readim7.load_sequence(["B00001.VC7", "B00002.VC7", "B00003.VC7"])
```

### 2. Standalone Vector Field Unpacking
If you prefer pure NumPy without xarray:

```python
vf = readim7.unpack_vector_field("B00001.VC7")
print(vf.u.shape, vf.x.shape, vf.y.shape)
print("Velocity magnitude:", vf.vmag)
print("Physical extent [xmin, xmax, ymin, ymax]:", vf.extent)
```

Universal Exporters & Interoperability
--------------------------------------

Export vector fields directly to standard fluid dynamics and post-processing tools:

```python
# 1. PIVMAT (.mat) for MATLAB PIV toolbox
readim7.export_pivmat("field.mat", ds)

# 2. Tecplot ASCII (.dat) for CFD, Tecplot, and ParaView
readim7.export_tecplot("field.dat", ds)

# 3. Hierarchical HDF5 (.h5) with compressed datasets & metadata
readim7.export_hdf5("field.h5", ds)

# 4. OpenPIV ASCII (.txt) 5-column format (x, y, u, v, mask)
readim7.export_openpiv_txt("field.txt", ds)
```

Vector Field Transforms & Fluid Mechanics
-----------------------------------------

Perform pure, coordinate-consistent transforms and spatial derivations:

```python
# Geometric transforms (consistently transforms x, y and u, v):
ds_rot = readim7.rotate_90_cw(ds)
ds_flip = readim7.flip_ud(ds)
ds_piped = readim7.transform(ds, ['flip_lr', 'rotate_90_cw', 'scale_velocity:1000'])

# Spatial derivatives:
vorticity = readim7.calc_vorticity(ds)       # omega_z = dv/dx - du/dy
divergence = readim7.calc_divergence(ds)     # div = du/dx + dv/dy
shear_strain = readim7.calc_shear_strain(ds) # 0.5 * (du/dy + dv/dx)

# Westerweel & Scarano Normalized Median Test (Universal Outlier Detection):
outliers = readim7.normalized_median_filter(vf.u, vf.v, threshold=2.0)

# Reynolds stresses and Turbulent Kinetic Energy across time series:
stats = readim7.calc_turbulent_statistics(seq_ds)
print(stats['uu'], stats['uv'], stats['tke'])
```


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

