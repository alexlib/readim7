"""
readim7.transforms: Geometric Transformations for Vector Fields
==============================================================

Applies geometric and parametric transformations to vector fields,
ensuring physical consistency between spatial coordinates and velocity vectors.
Inspired by python-PIVTOOLs and pyFlowStat.
"""

from __future__ import annotations

import copy
from typing import Any, List, Sequence, Union
import numpy as np

from .vectors import VectorField

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    xr = None
    HAS_XARRAY = False


def flip_ud(data: Any) -> Any:
    """Flip vertically (along y-axis), negating vertical velocity component v."""
    return _apply_transform(data, op="flip_ud")


def flip_lr(data: Any) -> Any:
    """Flip horizontally (along x-axis), negating horizontal velocity component u."""
    return _apply_transform(data, op="flip_lr")


def rotate_90_cw(data: Any) -> Any:
    """Rotate 90 degrees clockwise."""
    return _apply_transform(data, op="rotate_90_cw")


def rotate_90_ccw(data: Any) -> Any:
    """Rotate 90 degrees counter-clockwise."""
    return _apply_transform(data, op="rotate_90_ccw")


def rotate_180(data: Any) -> Any:
    """Rotate 180 degrees."""
    return _apply_transform(data, op="rotate_180")


def swap_uv(data: Any) -> Any:
    """Swap u and v velocity components, and x and y coordinates."""
    return _apply_transform(data, op="swap_uv")


def invert_uv(data: Any) -> Any:
    """Negate both u and v velocity components."""
    return _apply_transform(data, op="invert_uv")


def scale_coords(data: Any, factor: float) -> Any:
    """Multiply spatial coordinates x and y by factor (e.g. 1e-3 for mm to m)."""
    return _apply_transform(data, op="scale_coords", factor=factor)


def scale_velocity(data: Any, factor: float) -> Any:
    """Multiply velocity components u, v, w by factor."""
    return _apply_transform(data, op="scale_velocity", factor=factor)


def transform(data: Any, operations: Union[str, Sequence[str]]) -> Any:
    """
    Apply a sequence of operations to a VectorField or xarray.Dataset.

    Parameters
    ----------
    data : VectorField | xr.Dataset
    operations : str or list of str
        e.g. 'flip_ud', ['flip_lr', 'rotate_90_cw', 'scale_velocity:1000']
    """
    if isinstance(operations, str):
        operations = [operations]

    current = data
    for op_str in operations:
        op_str = op_str.strip()
        if ":" in op_str:
            name, arg = op_str.split(":", 1)
            factor = float(arg.strip())
            current = _apply_transform(current, op=name.strip(), factor=factor)
        else:
            current = _apply_transform(current, op=op_str)

    return current


def _apply_transform(data: Any, op: str, factor: float = 1.0) -> Any:
    if isinstance(data, VectorField):
        return _transform_vectorfield(data, op=op, factor=factor)
    elif HAS_XARRAY and isinstance(data, xr.Dataset):
        return _transform_dataset(data, op=op, factor=factor)
    else:
        raise TypeError(f"Unsupported data type for transform: {type(data)}")


def _transform_vectorfield(vf: VectorField, op: str, factor: float = 1.0) -> VectorField:
    out = copy.deepcopy(vf)

    if op == "flip_ud":
        # Flip rows: y coordinates reversed, v negated
        out.u = out.u[::-1, :]
        out.v = -out.v[::-1, :]
        if out.w is not None:
            out.w = out.w[::-1, :]
        if out.choice is not None:
            out.choice = out.choice[::-1, :]
        if out.peak_ratio is not None:
            out.peak_ratio = out.peak_ratio[::-1, :]
        out.mask = out.mask[::-1, :]
        out.y = out.y[::-1]

    elif op == "flip_lr":
        # Flip columns: x coordinates reversed, u negated
        out.u = -out.u[:, ::-1]
        out.v = out.v[:, ::-1]
        if out.w is not None:
            out.w = out.w[:, ::-1]
        if out.choice is not None:
            out.choice = out.choice[:, ::-1]
        if out.peak_ratio is not None:
            out.peak_ratio = out.peak_ratio[:, ::-1]
        out.mask = out.mask[:, ::-1]
        out.x = out.x[::-1]

    elif op == "rotate_90_cw":
        # 90 deg clockwise: (x, y) -> (y, -x); (u, v) -> (v, -u)
        new_u = np.rot90(out.v, -1)
        new_v = -np.rot90(out.u, -1)
        out.u = new_u
        out.v = new_v
        if out.w is not None:
            out.w = np.rot90(out.w, -1)
        if out.choice is not None:
            out.choice = np.rot90(out.choice, -1)
        if out.peak_ratio is not None:
            out.peak_ratio = np.rot90(out.peak_ratio, -1)
        out.mask = np.rot90(out.mask, -1)
        old_x, old_y = out.x, out.y
        out.x = old_y
        out.y = -old_x

    elif op == "rotate_90_ccw":
        # 90 deg counter-clockwise: (x, y) -> (-y, x); (u, v) -> (-v, u)
        new_u = -np.rot90(out.v, 1)
        new_v = np.rot90(out.u, 1)
        out.u = new_u
        out.v = new_v
        if out.w is not None:
            out.w = np.rot90(out.w, 1)
        if out.choice is not None:
            out.choice = np.rot90(out.choice, 1)
        if out.peak_ratio is not None:
            out.peak_ratio = np.rot90(out.peak_ratio, 1)
        out.mask = np.rot90(out.mask, 1)
        old_x, old_y = out.x, out.y
        out.x = -old_y
        out.y = old_x

    elif op == "rotate_180":
        out.u = -np.rot90(out.u, 2)
        out.v = -np.rot90(out.v, 2)
        if out.w is not None:
            out.w = np.rot90(out.w, 2)
        if out.choice is not None:
            out.choice = np.rot90(out.choice, 2)
        if out.peak_ratio is not None:
            out.peak_ratio = np.rot90(out.peak_ratio, 2)
        out.mask = np.rot90(out.mask, 2)
        out.x = -out.x[::-1]
        out.y = -out.y[::-1]

    elif op == "swap_uv":
        out.u, out.v = out.v.T, out.u.T
        if out.w is not None:
            out.w = out.w.T
        if out.choice is not None:
            out.choice = out.choice.T
        if out.peak_ratio is not None:
            out.peak_ratio = out.peak_ratio.T
        out.mask = out.mask.T
        out.x, out.y = out.y, out.x

    elif op == "invert_uv":
        out.u = -out.u
        out.v = -out.v

    elif op == "scale_coords":
        out.x = out.x * factor
        out.y = out.y * factor

    elif op == "scale_velocity":
        out.u = out.u * factor
        out.v = out.v * factor
        if out.w is not None:
            out.w = out.w * factor

    else:
        raise ValueError(f"Unknown transformation: {op}")

    return out


def _transform_dataset(ds: xr.Dataset, op: str, factor: float = 1.0) -> xr.Dataset:
    from .pivpy_io import to_dataset
    # Convert to VectorField or transform arrays directly
    ds_out = ds.copy(deep=True)

    if op == "flip_ud":
        ds_out = ds_out.reindex(y=ds_out.y[::-1])
        ds_out['v'] = -ds_out['v']

    elif op == "flip_lr":
        ds_out = ds_out.reindex(x=ds_out.x[::-1])
        ds_out['u'] = -ds_out['u']

    elif op == "invert_uv":
        ds_out['u'] = -ds_out['u']
        ds_out['v'] = -ds_out['v']

    elif op == "scale_coords":
        ds_out = ds_out.assign_coords(x=ds_out.x * factor, y=ds_out.y * factor)

    elif op == "scale_velocity":
        ds_out['u'] = ds_out['u'] * factor
        ds_out['v'] = ds_out['v'] * factor
        if 'w' in ds_out.data_vars:
            ds_out['w'] = ds_out['w'] * factor

    elif op in ("rotate_90_cw", "rotate_90_ccw", "rotate_180", "swap_uv"):
        # For full matrix rotation across dimensions, unpack to VectorField and reconstruct
        vf = VectorField(
            u=np.asarray(ds_out['u'].values).squeeze(),
            v=np.asarray(ds_out['v'].values).squeeze(),
            w=np.asarray(ds_out['w'].values).squeeze() if 'w' in ds_out.data_vars else None,
            x=np.asarray(ds_out.coords['x'].values),
            y=np.asarray(ds_out.coords['y'].values),
            choice=np.asarray(ds_out['ch'].values).squeeze() if 'ch' in ds_out.data_vars else None,
            peak_ratio=np.asarray(ds_out['p'].values).squeeze() if 'p' in ds_out.data_vars else None,
            mask=np.asarray(ds_out['mask'].values).squeeze().astype(bool) if 'mask' in ds_out.data_vars else np.zeros_like(ds_out['u'].values, dtype=bool).squeeze(),
            units={
                'x': ds_out.attrs.get('units', ['mm', 'mm', 'm/s', 'm/s'])[0],
                'y': ds_out.attrs.get('units', ['mm', 'mm', 'm/s', 'm/s'])[1],
                'u': ds_out.attrs.get('units', ['mm', 'mm', 'm/s', 'm/s'])[2],
                'v': ds_out.attrs.get('units', ['mm', 'mm', 'm/s', 'm/s'])[3],
                'w': '',
            },
            attributes=dict(ds_out.attrs),
            vector_grid=ds_out.attrs.get('vector_grid', 1),
            is_3d='w' in ds_out.data_vars,
        )
        vf_t = _transform_vectorfield(vf, op=op, factor=factor)
        t_val = ds_out.coords['t'].values[0] if 't' in ds_out.coords else 0
        ds_out = to_dataset(vf_t, t=t_val)
    else:
        raise ValueError(f"Unknown transformation: {op}")

    return ds_out
