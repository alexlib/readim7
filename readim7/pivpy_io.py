"""
readim7.pivpy_io: First-class PIVPy & xarray.Dataset Integration
================================================================

Converts DaVis vector fields (.vc7), images (.im7), and camera streams (.ims)
directly into standard xarray.Dataset structures fully compliant with PIVPy and OpenPIV.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    xr = None
    HAS_XARRAY = False

from .vectors import unpack_vector_field, VectorField
from . import extra
from . import ims


def to_dataset(
    source: Union[str, VectorField, Any],
    t: Optional[Union[float, int]] = 0,
    choice_preference: str = "optimal",
    invert_y: bool = True,
    fill_invalid_with_nan: bool = True,
) -> xr.Dataset:
    """
    Convert a VC7/IM7/IMS file or VectorField into a PIVPy-compliant xarray.Dataset.

    Parameters
    ----------
    source : str | VectorField | BunchMappable
        Path to .vc7, .im7 file or folder with .ims stream, or an unpacked VectorField.
    t : float | int, optional
        Time stamp or frame index for the time coordinate (default: 0).
    choice_preference : str
        'optimal' or 'first' for vector choice selection.
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

    if isinstance(source, str):
        lower = source.lower()
        if lower.endswith(('.vc7', '.vec')):
            vf = unpack_vector_field(
                source,
                choice_preference=choice_preference,
                invert_y=invert_y,
                fill_invalid_with_nan=fill_invalid_with_nan,
            )
            ds = _vectorfield_to_dataset(vf, t=t)
            ds.attrs['source'] = os.path.abspath(source)
            return ds

        elif lower.endswith('.im7'):
            return _im7_to_dataset(source, t=t)

        elif lower.endswith('.ims') or os.path.isdir(source):
            return _ims_to_dataset(source)

        else:
            # Try loading as vector first, fall back to buffer
            try:
                buff, atts = extra.get_Buffer_andAttributeList(source)
                if buff.image_sub_type > 0:
                    vf = unpack_vector_field(
                        buff,
                        attributes=atts,
                        choice_preference=choice_preference,
                        invert_y=invert_y,
                        fill_invalid_with_nan=fill_invalid_with_nan,
                    )
                    ds = _vectorfield_to_dataset(vf, t=t)
                    ds.attrs['source'] = os.path.abspath(source)
                    return ds
                else:
                    return _im7_to_dataset(source, t=t)
            except Exception as e:
                raise ValueError(f"Unable to parse '{source}' as PIV dataset: {e}")

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


def _extract_dt(attributes: Dict[str, Any]) -> Optional[float]:
    """Extract pulse separation dt in seconds from DaVis attributes."""
    for key in ('FrameDt0', 'DevDataScaleI2', '_PULSE_SEPARATION_US', 'dt'):
        val = attributes.get(key)
        if val is not None:
            val_str = str(val).strip()
            # E.g. "10000 us" or "10 ms" or "0.01"
            parts = val_str.split()
            try:
                num = float(parts[0])
                if len(parts) > 1:
                    unit = parts[1].lower()
                    if 'us' in unit or 'µs' in unit:
                        return num * 1e-6
                    elif 'ms' in unit:
                        return num * 1e-3
                    elif 'ns' in unit:
                        return num * 1e-9
                return num
            except (ValueError, IndexError):
                pass
    return None


def _vectorfield_to_dataset(vf: VectorField, t: Optional[Union[float, int]] = 0) -> xr.Dataset:
    """Build an xarray.Dataset from a VectorField."""
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

    dt = _extract_dt(vf.attributes)

    attrs = {
        'units': [vf.units['x'], vf.units['y'], vf.units['u'], vf.units['v']],
        'variables': ['x', 'y', 'u', 'v'] + (['w'] if vf.w is not None else []),
        'vector_grid': vf.vector_grid,
        'is_3d': vf.is_3d,
        'extent': vf.extent,
    }

    if dt is not None:
        attrs['dt'] = dt

    # Include raw attributes
    for k, v in vf.attributes.items():
        if isinstance(v, (str, int, float, bool)):
            attrs[f'davis_{k}'] = v

    ds = xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)

    if t is not None:
        ds = ds.expand_dims(dim={'t': [t]})

    return ds


def _im7_to_dataset(filename: str, t: Optional[Union[float, int]] = 0) -> xr.Dataset:
    """Convert an IM7 image file to an xarray.Dataset."""
    buff, atts = extra.get_Buffer_andAttributeList(filename)
    arr, _ = extra.buffer_as_array(buff)  # (components, ny, nx)

    ny, nx = buff.ny, buff.nx
    fx = getattr(buff.scaleX, 'factor', 1.0)
    ox = getattr(buff.scaleX, 'offset', 0.0)
    fy = getattr(buff.scaleY, 'factor', 1.0)
    oy = getattr(buff.scaleY, 'offset', 0.0)

    x = (np.arange(nx) + 0.5) * fx + ox
    y = (np.arange(ny) + 0.5) * fy + oy

    # If multiple frames (e.g. pulse A and pulse B)
    nf = arr.shape[0]
    frame_coords = np.arange(nf)

    data_vars = {
        'intensity': (('frame', 'y', 'x'), arr),
    }

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
        'nf': nf,
        'is_float': buff.is_float,
    }
    for k, v in atts.items():
        if isinstance(v, (str, int, float, bool)):
            attrs[f'davis_{k}'] = v

    ds = xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)
    if t is not None:
        ds = ds.expand_dims(dim={'t': [t]})
    return ds


def _ims_to_dataset(source: str, max_pairs: Optional[int] = None) -> xr.Dataset:
    """Convert an IMS high-speed stream to an xarray.Dataset."""
    info = ims.ims_info(source)
    n_pairs = info['n_pairs'] if max_pairs is None else min(info['n_pairs'], max_pairs)

    nx, ny = info['nx'], info['ny']
    x = np.arange(nx, dtype=np.float32)
    y = np.arange(ny, dtype=np.float32)

    # Read pairs into memory (or chunks)
    data_a = np.empty((n_pairs, ny, nx), dtype=np.uint16)
    data_b = np.empty((n_pairs, ny, nx), dtype=np.uint16)

    for i in range(n_pairs):
        pa, pb = ims.read_ims_pair(info, i)
        data_a[i] = pa
        data_b[i] = pb

    coords = {
        'pair': ('pair', np.arange(n_pairs)),
        'y': ('y', y),
        'x': ('x', x),
    }

    data_vars = {
        'pulse_a': (('pair', 'y', 'x'), data_a),
        'pulse_b': (('pair', 'y', 'x'), data_b),
    }

    attrs = {
        'source': info['ims_path'],
        'n_pairs': n_pairs,
        'nx': nx,
        'ny': ny,
        'bits_per_pixel': info.get('bits_per_pixel', 12),
    }

    return xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)


def load_sequence(
    filenames: Sequence[str],
    t_coords: Optional[Sequence[Union[float, int]]] = None,
    choice_preference: str = "optimal",
    invert_y: bool = True,
) -> xr.Dataset:
    """
    Load an ordered list of VC7/IM7 files into a single time-resolved xarray.Dataset.

    Parameters
    ----------
    filenames : list of str
        List of paths to VC7 or IM7 files.
    t_coords : list of float/int, optional
        Custom time coordinates. If None, indices 0, 1, ... are used.
    choice_preference : str
        'optimal' or 'first'.
    invert_y : bool
        Whether to orient y upwards.

    Returns
    -------
    xr.Dataset
        Concatenated dataset with coordinate 't'.
    """
    if not HAS_XARRAY:
        raise ImportError("xarray is required for load_sequence().")

    if not filenames:
        raise ValueError("filenames sequence must not be empty.")

    datasets = []
    for i, fn in enumerate(filenames):
        t_val = t_coords[i] if t_coords is not None else i
        ds = to_dataset(
            fn,
            t=t_val,
            choice_preference=choice_preference,
            invert_y=invert_y,
        )
        datasets.append(ds)

    combined = xr.concat(datasets, dim='t')
    return combined


# Alias for PIVPy users
to_pivpy = to_dataset
