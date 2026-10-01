"""
readim7.export: Interoperability Exporters
=========================================

Export DaVis vector fields and PIVPy datasets to standard community formats:
- PIVMAT (.mat) for MATLAB PIV toolbox
- Tecplot (.dat) for CFD and post-processing tools
- HDF5 (.h5) for high-performance self-describing archival
- OpenPIV (.txt) for OpenPIV evaluation pipelines
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union
import numpy as np

from .vectors import VectorField, unpack_vector_field

try:
    import scipy.io as sio
    HAS_SCIPY = True
except ImportError:
    sio = None
    HAS_SCIPY = False

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    h5py = None
    HAS_H5PY = False


def _atomic_write(target_path: Union[str, Path], write_fn) -> None:
    """Safely write to target_path using a temporary file and atomic rename."""
    target = Path(target_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = target.parent

    with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=".tmp") as tmp:
        tmp_name = tmp.name

    try:
        write_fn(tmp_name)
        os.replace(tmp_name, target)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def _extract_components(data: Any) -> Dict[str, Any]:
    """Extract standard x, y, u, v, w, choice, mask, units from VectorField, Dataset, or file."""
    if isinstance(data, str):
        vf = unpack_vector_field(data, fill_invalid_with_nan=False)
        return _extract_components(vf)

    if isinstance(data, VectorField):
        # 1D or 2D meshgrid
        xx, yy = np.meshgrid(data.x, data.y)
        return {
            'x': data.x,
            'y': data.y,
            'xx': xx,
            'yy': yy,
            'u': data.u,
            'v': data.v,
            'w': data.w if data.w is not None else np.zeros_like(data.u),
            'has_w': data.w is not None,
            'choice': data.choice if data.choice is not None else np.ones_like(data.u, dtype=int),
            'peak_ratio': data.peak_ratio,
            'mask': data.mask,
            'units': data.units,
            'extent': data.extent,
            'attrs': data.attributes,
        }

    # If xarray.Dataset
    if hasattr(data, 'data_vars') and hasattr(data, 'coords'):
        x = np.asarray(data.coords['x'].values)
        y = np.asarray(data.coords['y'].values)
        xx, yy = np.meshgrid(x, y) if x.ndim == 1 and y.ndim == 1 else (x, y)

        u = np.asarray(data['u'].values)
        v = np.asarray(data['v'].values)
        # Squeeze leading time dimension if present
        if u.ndim == 3 and u.shape[0] == 1:
            u = u[0]
            v = v[0]

        has_w = 'w' in data.data_vars
        w = np.asarray(data['w'].values) if has_w else np.zeros_like(u)
        if has_w and w.ndim == 3 and w.shape[0] == 1:
            w = w[0]

        choice = np.asarray(data['ch'].values) if 'ch' in data.data_vars else np.ones_like(u, dtype=int)
        if choice.ndim == 3 and choice.shape[0] == 1:
            choice = choice[0]

        mask = np.asarray(data['mask'].values).astype(bool) if 'mask' in data.data_vars else np.isnan(u)
        if mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]

        units_list = data.attrs.get('units', ['mm', 'mm', 'm/s', 'm/s'])
        units = {
            'x': units_list[0] if len(units_list) > 0 else 'mm',
            'y': units_list[1] if len(units_list) > 1 else 'mm',
            'u': units_list[2] if len(units_list) > 2 else 'm/s',
            'v': units_list[3] if len(units_list) > 3 else 'm/s',
            'w': units_list[2] if has_w else '',
        }

        return {
            'x': x,
            'y': y,
            'xx': xx,
            'yy': yy,
            'u': u,
            'v': v,
            'w': w,
            'has_w': has_w,
            'choice': choice,
            'peak_ratio': np.asarray(data['p'].values) if 'p' in data.data_vars else None,
            'mask': mask,
            'units': units,
            'extent': data.attrs.get('extent', (x.min(), x.max(), y.min(), y.max())),
            'attrs': dict(data.attrs),
        }

    raise TypeError(f"Unsupported data format for export: {type(data)}")


def export_pivmat(
    filename: Union[str, Path],
    data: Any,
    setname: str = "readim7_field",
) -> None:
    """
    Export vector data to MATLAB PIVMAT (.mat) format.

    Compatible with the PIVMAT toolbox:
    http://www.fast.u-psud.fr/pivmat/

    Parameters
    ----------
    filename : str | Path
        Output .mat filename.
    data : VectorField | xr.Dataset | str
        Input vector field.
    setname : str
        Name tag for the dataset.
    """
    if not HAS_SCIPY:
        raise ImportError("scipy is required for export_pivmat(). Install via: pip install scipy")

    c = _extract_components(data)

    mat_dict = {
        'x': c['x'],
        'y': c['y'],
        'vx': np.nan_to_num(c['u'], nan=0.0),
        'vy': np.nan_to_num(c['v'], nan=0.0),
        'vz': np.nan_to_num(c['w'], nan=0.0) if c['has_w'] else np.zeros_like(c['u']),
        'choice': c['choice'].astype(np.float64),
        'namex': 'x',
        'namey': 'y',
        'namevx': 'vx',
        'namevy': 'vy',
        'unitx': c['units'].get('x', 'mm'),
        'unity': c['units'].get('y', 'mm'),
        'unitvx': c['units'].get('u', 'm/s'),
        'unitvy': c['units'].get('v', 'm/s'),
        'ysign': 'Y axis upward',
        'setname': setname,
        'source': 'readim7',
        'history': np.array(['readim7 export_pivmat'], dtype=object),
        'pivmat_version': 'readim7-interop',
    }

    _atomic_write(filename, lambda p: sio.savemat(p, mat_dict, do_compression=True))


def export_tecplot(
    filename: Union[str, Path],
    data: Any,
    title: str = "readim7 vector field",
) -> None:
    """
    Export vector data to standard Tecplot ASCII (.dat) format.

    Parameters
    ----------
    filename : str | Path
        Output .dat filename.
    data : VectorField | xr.Dataset | str
        Input vector field.
    title : str
        Title in Tecplot header.
    """
    c = _extract_components(data)
    ny, nx = c['u'].shape
    xx = c['xx']
    yy = c['yy']
    u = np.nan_to_num(c['u'], nan=0.0)
    v = np.nan_to_num(c['v'], nan=0.0)
    w = np.nan_to_num(c['w'], nan=0.0)
    vmag = np.sqrt(u ** 2 + v ** 2 + (w ** 2 if c['has_w'] else 0.0))

    def write_tecplot(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'TITLE = "{title}"\n')
            if c['has_w']:
                f.write('VARIABLES = "X", "Y", "U", "V", "W", "Vmag", "Choice", "Mask"\n')
            else:
                f.write('VARIABLES = "X", "Y", "U", "V", "Vmag", "Choice", "Mask"\n')
            f.write(f'ZONE I={nx}, J={ny}, F=POINT\n')

            for j in range(ny):
                for i in range(nx):
                    ch = int(c['choice'][j, i]) if c['choice'] is not None else 1
                    m = 1 if c['mask'][j, i] else 0
                    if c['has_w']:
                        f.write(
                            f"{xx[j, i]:.6e} {yy[j, i]:.6e} {u[j, i]:.6e} {v[j, i]:.6e} "
                            f"{w[j, i]:.6e} {vmag[j, i]:.6e} {ch} {m}\n"
                        )
                    else:
                        f.write(
                            f"{xx[j, i]:.6e} {yy[j, i]:.6e} {u[j, i]:.6e} {v[j, i]:.6e} "
                            f"{vmag[j, i]:.6e} {ch} {m}\n"
                        )

    _atomic_write(filename, write_tecplot)


def export_hdf5(
    filename: Union[str, Path],
    data: Any,
    group: str = "piv",
    compression: str = "gzip",
) -> None:
    """
    Export vector data to hierarchical HDF5 format with self-describing metadata.

    Parameters
    ----------
    filename : str | Path
        Output .h5 / .hdf5 filename.
    data : VectorField | xr.Dataset | str
        Input vector field.
    group : str
        HDF5 group name.
    compression : str
        HDF5 compression filter (default: 'gzip').
    """
    if not HAS_H5PY:
        raise ImportError("h5py is required for export_hdf5(). Install via: pip install h5py")

    c = _extract_components(data)

    def write_h5(path):
        with h5py.File(path, 'w') as f:
            g = f.create_group(group)
            g.create_dataset('x', data=c['x'], compression=compression)
            g.create_dataset('y', data=c['y'], compression=compression)
            g.create_dataset('u', data=c['u'], compression=compression)
            g.create_dataset('v', data=c['v'], compression=compression)
            if c['has_w']:
                g.create_dataset('w', data=c['w'], compression=compression)
            if c['choice'] is not None:
                g.create_dataset('choice', data=c['choice'], compression=compression)
            if c['peak_ratio'] is not None:
                g.create_dataset('peak_ratio', data=c['peak_ratio'], compression=compression)
            g.create_dataset('mask', data=c['mask'].astype(np.int8), compression=compression)

            # Metadata attributes
            for k, val in c['units'].items():
                g.attrs[f'unit_{k}'] = val
            g.attrs['extent'] = np.array(c['extent'])
            for k, val in c['attrs'].items():
                if isinstance(val, (int, float, str, bytes, bool)):
                    g.attrs[k] = val

    _atomic_write(filename, write_h5)


def export_openpiv_txt(
    filename: Union[str, Path],
    data: Any,
    delimiter: str = "\t",
) -> None:
    """
    Export vector data to standard OpenPIV tab-separated ASCII format.

    Columns: x  y  u  v  mask

    Parameters
    ----------
    filename : str | Path
        Output .txt filename.
    data : VectorField | xr.Dataset | str
        Input vector field.
    delimiter : str
        Column separator (default tab).
    """
    c = _extract_components(data)
    xx = c['xx'].flatten()
    yy = c['yy'].flatten()
    u = np.nan_to_num(c['u'].flatten(), nan=0.0)
    v = np.nan_to_num(c['v'].flatten(), nan=0.0)
    mask = c['mask'].flatten().astype(int)

    table = np.column_stack([xx, yy, u, v, mask])

    def write_openpiv(path):
        header = f"x\ty\tu\tv\tmask"
        np.savetxt(
            path,
            table,
            fmt="%.6e",
            delimiter=delimiter,
            header=header,
            comments="# ",
        )

    _atomic_write(filename, write_openpiv)
