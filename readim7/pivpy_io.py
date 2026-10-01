"""
readim7.pivpy_io: First-class PIVPy & xarray.Dataset Integration
================================================================

Converts DaVis vector fields (.vc7), images (.im7), and camera streams (.ims)
directly into standard xarray.Dataset structures fully compliant with PIVPy and OpenPIV.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    xr = None
    HAS_XARRAY = False

from .vectors import unpack_vector_field, VectorField
from .attributes import parse_davis_attributes, parse_time_value
from . import extra
from . import ims


def _natural_sort_key(s: str) -> List[Union[int, str]]:
    """Helper for natural alphanumeric sorting (e.g. B1, B2, ..., B10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


def read_image_pair(
    source: Union[str, Path, Any],
    pair_idx: int = 0,
    camera: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Read a PIV double-frame image pair (frame_a, frame_b) for OpenPIV / PIV processing.

    Works with multi-frame .im7 files and high-speed .ims stream files.

    Parameters
    ----------
    source : str | Path | dict
        Path to .im7 file, .ims file, or .ims run folder, or an ims_info dict.
    pair_idx : int
        Index of the pair to read (for .ims streams). Default: 0.
    camera : int
        Camera index (for multi-camera stereoscopic .im7 files with 4 frames). Default: 0.

    Returns
    -------
    frame_a : np.ndarray (ny, nx)
        First pulse/exposure image.
    frame_b : np.ndarray (ny, nx)
        Second pulse/exposure image.
    """
    if isinstance(source, (str, Path)):
        source_str = str(source)
        lower = source_str.lower()
        if lower.endswith('.im7'):
            buff, _ = extra.get_Buffer_andAttributeList(source_str)
            arr, _ = extra.buffer_as_array(buff)
            nf = arr.shape[0]

            if nf == 1:
                raise ValueError(f"File '{source_str}' has only 1 frame; expected a double-frame pair.")
            elif nf == 2:
                return arr[0], arr[1]
            elif nf >= 4:
                idx_a = camera * 2
                idx_b = camera * 2 + 1
                if idx_b >= nf:
                    raise IndexError(f"Camera index {camera} out of range for {nf}-frame buffer.")
                return arr[idx_a], arr[idx_b]
            else:
                return arr[0], arr[1]

        elif lower.endswith('.ims') or os.path.isdir(source_str):
            info = ims.ims_info(source_str)
            return ims.read_ims_pair(info, pair_idx)

    elif isinstance(source, dict) and 'ims_path' in source:
        return ims.read_ims_pair(source, pair_idx)

    # If already a buffer object
    if hasattr(source, 'array') and hasattr(source, 'nf'):
        arr, _ = extra.buffer_as_array(source)
        if arr.shape[0] >= 2:
            idx_a = camera * 2
            idx_b = camera * 2 + 1
            return arr[idx_a], arr[idx_b]

    raise TypeError(f"Unsupported source type for read_image_pair: {type(source)}")


def to_dataset(
    source: Union[str, Path, VectorField, Any],
    t: Optional[Union[float, int]] = None,
    choice_preference: str = "optimal",
    invert_y: bool = True,
    fill_invalid_with_nan: bool = True,
) -> xr.Dataset:
    """
    Convert a VC7/IM7/IMS file or VectorField into a PIVPy-compliant xarray.Dataset.

    Parameters
    ----------
    source : str | Path | VectorField | BunchMappable
        Path to .vc7, .im7 file or folder with .ims stream, or an unpacked VectorField.
    t : float | int, optional
        Time stamp or frame index for the time coordinate. If None, derived from DaVis attributes.
    choice_preference : str
        'optimal' (default) or 'first' for vector choice selection.
    invert_y : bool
        If True, adjust y coordinate and v sign so y increases upwards.
    fill_invalid_with_nan : bool
        Whether to fill masked vector positions with NaN.

    Returns
    -------
    xr.Dataset
        xarray Dataset with standard PIVPy variables (u, v, optional w, ch, p)
        and coordinates (x, y, t).
    """
    if not HAS_XARRAY:
        raise ImportError(
            "xarray is required for to_dataset() / to_pivpy(). "
            "Install it via: pip install xarray"
        )

    if isinstance(source, VectorField):
        return _vectorfield_to_dataset(source, t=t)

    if isinstance(source, (str, Path)):
        source_str = str(source)
        lower = source_str.lower()
        if lower.endswith(('.vc7', '.vec')):
            vf = unpack_vector_field(
                source_str,
                choice_preference=choice_preference,
                invert_y=invert_y,
                fill_invalid_with_nan=fill_invalid_with_nan,
            )
            ds = _vectorfield_to_dataset(vf, t=t)
            ds.attrs['source'] = os.path.abspath(source_str)
            return ds

        elif lower.endswith('.im7'):
            return _im7_to_dataset(source_str, t=t)

        elif lower.endswith('.ims') or os.path.isdir(source_str):
            return _ims_to_dataset(source_str)

        else:
            try:
                buff, atts = extra.get_Buffer_andAttributeList(source_str)
                if buff.image_sub_type > 0:
                    vf = unpack_vector_field(
                        buff,
                        attributes=atts,
                        choice_preference=choice_preference,
                        invert_y=invert_y,
                        fill_invalid_with_nan=fill_invalid_with_nan,
                    )
                    ds = _vectorfield_to_dataset(vf, t=t)
                    ds.attrs['source'] = os.path.abspath(source_str)
                    return ds
                else:
                    return _im7_to_dataset(source_str, t=t)
            except Exception as e:
                raise ValueError(f"Unable to parse '{source_str}' as PIV dataset: {e}")

    # If already a buffer
    if hasattr(source, 'image_sub_type'):
        if source.image_sub_type > 0:
            vf = unpack_vector_field(
                source,
                choice_preference=choice_preference,
                invert_y=invert_y,
                fill_invalid_with_nan=fill_invalid_with_nan,
            )
            return _vectorfield_to_dataset(vf, t=t)
        else:
            raise NotImplementedError("Converting raw image buffer to Dataset is not yet supported directly.")

    raise TypeError(f"Unsupported source type: {type(source)}")


def _vectorfield_to_dataset(vf: VectorField, t: Optional[Union[float, int]] = None) -> xr.Dataset:
    """Build an xarray.Dataset from a VectorField matching PIVPy standards."""
    parsed_meta = parse_davis_attributes(vf.attributes)

    dt = parsed_meta.get('delta_t')
    if dt is None:
        dt = 0.0

    t_val = 0.0 if t is None else float(t)

    coords = {
        'y': ('y', vf.y),
        'x': ('x', vf.x),
    }

    dims = ('y', 'x')
    data_vars = {
        'u': (dims, vf.u),
        'v': (dims, vf.v),
    }

    if vf.w is not None:
        data_vars['w'] = (dims, vf.w)

    if vf.choice is not None:
        data_vars['ch'] = (dims, vf.choice)

    if vf.peak_ratio is not None:
        data_vars['p'] = (dims, vf.peak_ratio)

    data_vars['mask'] = (dims, vf.mask.astype(np.int8))

    attrs = {
        'variables': ['x', 'y', 'u', 'v'] + (['w'] if vf.w is not None else []),
        'units': [vf.units['x'], vf.units['y'], vf.units['u'], vf.units['v']],
        'delta_t': dt,
        'dt': dt,
        'vector_grid': vf.vector_grid,
        'is_3d': vf.is_3d,
        'extent': vf.extent,
    }

    if parsed_meta.get('date'):
        attrs['date'] = parsed_meta['date']
    if parsed_meta.get('time'):
        attrs['time'] = parsed_meta['time']
    if parsed_meta.get('davis_version'):
        attrs['davis_version'] = parsed_meta['davis_version']

    # Include raw attributes prefixed with 'davis_'
    for k, v in vf.attributes.items():
        if isinstance(v, (str, int, float, bool)):
            attrs[f'davis_{k}'] = v

    ds = xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)

    # Set variable and coordinate units
    ds['x'].attrs['units'] = vf.units['x']
    ds['y'].attrs['units'] = vf.units['y']
    ds['u'].attrs['units'] = vf.units['u']
    ds['v'].attrs['units'] = vf.units['v']
    if vf.w is not None:
        ds['w'].attrs['units'] = vf.units.get('w', vf.units['u'])

    # Expand dims along time dimension t
    ds = ds.expand_dims(dim={'t': [t_val]})

    return ds


def _im7_to_dataset(filename: str, t: Optional[Union[float, int]] = None) -> xr.Dataset:
    """Convert an IM7 image file to an xarray.Dataset."""
    buff, atts = extra.get_Buffer_andAttributeList(filename)
    arr, _ = extra.buffer_as_array(buff)  # (components, ny, nx)

    parsed_meta = parse_davis_attributes(atts)
    dt = parsed_meta.get('delta_t', 0.0)

    ny, nx = buff.ny, buff.nx
    fx = getattr(buff.scaleX, 'factor', 1.0)
    ox = getattr(buff.scaleX, 'offset', 0.0)
    fy = getattr(buff.scaleY, 'factor', 1.0)
    oy = getattr(buff.scaleY, 'offset', 0.0)

    x = (np.arange(nx) + 0.5) * fx + ox
    y = (np.arange(ny) + 0.5) * fy + oy

    nf = arr.shape[0]
    frame_coords = np.arange(nf)

    data_vars = {
        'intensity': (('frame', 'y', 'x'), arr),
    }

    if nf == 2:
        data_vars['pulse_a'] = (('y', 'x'), arr[0])
        data_vars['pulse_b'] = (('y', 'x'), arr[1])

    if buff.mask is not None:
        data_vars['mask'] = (('frame', 'y', 'x'), buff.mask.astype(np.int8))

    coords = {
        'frame': ('frame', frame_coords),
        'y': ('y', y),
        'x': ('x', x),
    }

    attrs = {
        'source': os.path.abspath(filename),
        'units': [getattr(buff.scaleX, 'unit', 'pixel'), getattr(buff.scaleY, 'unit', 'pixel'), getattr(buff.scaleI, 'unit', 'counts')],
        'delta_t': dt,
        'dt': dt,
        'nf': nf,
        'is_float': buff.is_float,
    }

    for k, v in atts.items():
        if isinstance(v, (str, int, float, bool)):
            attrs[f'davis_{k}'] = v

    ds = xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)
    t_val = 0.0 if t is None else float(t)
    ds = ds.expand_dims(dim={'t': [t_val]})
    return ds


def _ims_to_dataset(source: str, max_pairs: Optional[int] = None) -> xr.Dataset:
    """Convert an IMS high-speed stream to an xarray.Dataset."""
    info = ims.ims_info(source)
    n_pairs = info['n_pairs'] if max_pairs is None else min(info['n_pairs'], max_pairs)

    nx, ny = info['nx'], info['ny']
    x = np.arange(nx, dtype=np.float32)
    y = np.arange(ny, dtype=np.float32)

    data_a = np.empty((n_pairs, ny, nx), dtype=np.uint16)
    data_b = np.empty((n_pairs, ny, nx), dtype=np.uint16)

    for i in range(n_pairs):
        pa, pb = ims.read_ims_pair(info, i)
        data_a[i] = pa
        data_b[i] = pb

    coords = {
        't': ('t', np.arange(n_pairs, dtype=np.float64)),
        'y': ('y', y),
        'x': ('x', x),
    }

    data_vars = {
        'pulse_a': (('t', 'y', 'x'), data_a),
        'pulse_b': (('t', 'y', 'x'), data_b),
    }

    attrs = {
        'source': info['ims_path'],
        'n_pairs': n_pairs,
        'nx': nx,
        'ny': ny,
        'bits_per_pixel': info.get('bits_per_pixel', 12),
        'delta_t': 0.0,
        'dt': 0.0,
    }

    return xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)


def load_sequence(
    source: Union[str, Path, Sequence[Union[str, Path]]],
    t_coords: Optional[Sequence[Union[float, int]]] = None,
    choice_preference: str = "optimal",
    invert_y: bool = True,
    chunks: Optional[Union[str, Dict[str, int]]] = None,
) -> xr.Dataset:
    """
    Load an ordered sequence of VC7/IM7 files into a single time-resolved xarray.Dataset.

    Parameters
    ----------
    source : list of str/Path | str glob pattern | str directory path
        File list, glob pattern (e.g. 'data/B*.VC7'), or directory containing files.
    t_coords : list of float/int, optional
        Custom time coordinates. If None, automatically derived from acquisition timestamps,
        delta_t * index, or integer frame indices.
    choice_preference : str
        'optimal' or 'first'.
    invert_y : bool
        Whether to orient y upwards.
    chunks : dict | str, optional
        Chunking specification for lazy Dask loading (e.g. {'t': 1} or 'auto').

    Returns
    -------
    xr.Dataset
        Concatenated dataset with coordinate 't'.
    """
    if not HAS_XARRAY:
        raise ImportError("xarray is required for load_sequence().")

    # Resolve input filenames
    if isinstance(source, (str, Path)):
        source_str = str(source)
        if os.path.isdir(source_str):
            # Find all .vc7 or .im7 in directory
            files = [
                os.path.join(source_str, f) for f in os.listdir(source_str)
                if f.lower().endswith(('.vc7', '.vec', '.im7'))
            ]
        elif any(c in source_str for c in ('*', '?', '[')):
            files = glob.glob(source_str)
        else:
            files = [source_str]
    else:
        files = [str(f) for f in source]

    if not files:
        raise ValueError(f"No matching files found for source: {source}")

    # Natural alphanumeric sort
    files.sort(key=_natural_sort_key)

    datasets = []
    current_time = 0.0

    for i, fn in enumerate(files):
        if t_coords is not None:
            t_val = t_coords[i]
        else:
            t_val = float(i)

        ds = to_dataset(
            fn,
            t=t_val,
            choice_preference=choice_preference,
            invert_y=invert_y,
        )
        datasets.append(ds)

    combined = xr.concat(datasets, dim='t', join='outer')

    # Apply Dask chunking if requested
    if chunks is not None:
        try:
            import dask
            combined = combined.chunk(chunks)
        except ImportError:
            pass

    return combined


# Alias for PIVPy users
to_pivpy = to_dataset
