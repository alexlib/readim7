"""
readim7.calc: Differential Fluid Mechanics, Statistics, and Outlier Filtering
=============================================================================

Spatial derivations (vorticity, divergence, strain rate), turbulent statistics
(Reynolds stresses, turbulent kinetic energy), and Westerweel normalized median test.
Inspired by jpiv, pyFlowStat, and PIVPy.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union
import numpy as np

from .vectors import VectorField

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    xr = None
    HAS_XARRAY = False


def _get_uv_and_grid(data: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Helper to extract u, v, x, y arrays."""
    if isinstance(data, VectorField):
        return data.u, data.v, data.x, data.y
    elif HAS_XARRAY and isinstance(data, xr.Dataset):
        u = np.asarray(data['u'].values).squeeze()
        v = np.asarray(data['v'].values).squeeze()
        x = np.asarray(data.coords['x'].values)
        y = np.asarray(data.coords['y'].values)
        return u, v, x, y
    else:
        raise TypeError(f"Unsupported data type: {type(data)}")


def calc_vorticity(data: Any) -> np.ndarray:
    """
    Compute the out-of-plane vorticity: omega_z = dv/dx - du/dy.

    Uses 2nd-order central differences with numpy.gradient.
    Units: 1 / s (if velocity is in m/s and coordinates in m), or 1000 / s (if coordinates in mm).

    Parameters
    ----------
    data : VectorField | xr.Dataset

    Returns
    -------
    np.ndarray (ny, nx)
        Vorticity field.
    """
    u, v, x, y = _get_uv_and_grid(data)

    # dx, dy spacing
    dx = float(np.mean(np.diff(x))) if len(x) > 1 else 1.0
    dy = float(np.mean(np.diff(y))) if len(y) > 1 else 1.0

    # In numpy, axis 0 is rows (y), axis 1 is cols (x)
    # gradient along axis 0 is d/dy; gradient along axis 1 is d/dx
    dudy = np.gradient(u, dy, axis=0)
    dvdx = np.gradient(v, dx, axis=1)

    omega_z = dvdx - dudy
    return omega_z


def calc_divergence(data: Any) -> np.ndarray:
    """
    Compute 2D velocity divergence: div = du/dx + dv/dy.

    Parameters
    ----------
    data : VectorField | xr.Dataset

    Returns
    -------
    np.ndarray (ny, nx)
    """
    u, v, x, y = _get_uv_and_grid(data)

    dx = float(np.mean(np.diff(x))) if len(x) > 1 else 1.0
    dy = float(np.mean(np.diff(y))) if len(y) > 1 else 1.0

    dudx = np.gradient(u, dx, axis=1)
    dvdy = np.gradient(v, dy, axis=0)

    return dudx + dvdy


def calc_shear_strain(data: Any) -> np.ndarray:
    """
    Compute shear strain rate: gamma_xy = 0.5 * (du/dy + dv/dx).

    Parameters
    ----------
    data : VectorField | xr.Dataset

    Returns
    -------
    np.ndarray (ny, nx)
    """
    u, v, x, y = _get_uv_and_grid(data)

    dx = float(np.mean(np.diff(x))) if len(x) > 1 else 1.0
    dy = float(np.mean(np.diff(y))) if len(y) > 1 else 1.0

    dudy = np.gradient(u, dy, axis=0)
    dvdx = np.gradient(v, dx, axis=1)

    return 0.5 * (dudy + dvdx)


def calc_turbulent_statistics(dataset: Any) -> Dict[str, np.ndarray]:
    """
    Compute ensemble flow statistics across the time dimension 't'.

    Returns
    -------
    dict with:
        'u_mean': mean horizontal velocity
        'v_mean': mean vertical velocity
        'w_mean': mean out-of-plane velocity (if 3D)
        'uu': normal Reynolds stress <u'u'>
        'vv': normal Reynolds stress <v'v'>
        'uv': Reynolds shear stress <u'v'>
        'tke': turbulent kinetic energy 0.5*(<u'u'> + <v'v'> [+ <w'w'>])
    """
    if not (HAS_XARRAY and isinstance(dataset, xr.Dataset)):
        raise TypeError("calc_turbulent_statistics expects an xarray.Dataset with a 't' dimension.")

    if 't' not in dataset.dims or dataset.sizes['t'] < 2:
        raise ValueError("Dataset must have a 't' dimension with at least 2 time steps.")

    u = dataset['u'].values  # (t, y, x)
    v = dataset['v'].values

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        u_mean = np.nanmean(u, axis=0)
        v_mean = np.nanmean(v, axis=0)

        u_prime = u - u_mean
        v_prime = v - v_mean

        uu = np.nanmean(u_prime ** 2, axis=0)
        vv = np.nanmean(v_prime ** 2, axis=0)
        uv = np.nanmean(u_prime * v_prime, axis=0)

        tke = 0.5 * (uu + vv)

        stats = {
            'u_mean': u_mean,
            'v_mean': v_mean,
            'uu': uu,
            'vv': vv,
            'uv': uv,
            'tke': tke,
        }

        if 'w' in dataset.data_vars:
            w = dataset['w'].values
            w_mean = np.nanmean(w, axis=0)
            w_prime = w - w_mean
            ww = np.nanmean(w_prime ** 2, axis=0)
            stats['w_mean'] = w_mean
            stats['ww'] = ww
            stats['tke'] = 0.5 * (uu + vv + ww)

    return stats


def normalized_median_filter(
    u: np.ndarray,
    v: np.ndarray,
    threshold: float = 2.0,
    epsilon: float = 0.1,
) -> np.ndarray:
    """
    Westerweel & Scarano (2005) Universal Outlier Detection (Normalized Median Test).

    Parameters
    ----------
    u : np.ndarray (ny, nx)
    v : np.ndarray (ny, nx)
    threshold : float
        Outlier detection threshold (standard value: 2.0).
    epsilon : float
        Normalizing constant representing measurement noise level.

    Returns
    -------
    outlier_mask : np.ndarray (ny, nx) of bool
        True where the vector is flagged as an outlier.
    """
    ny, nx = u.shape
    outlier_mask = np.zeros((ny, nx), dtype=bool)

    pad_u = np.pad(u, 1, mode='edge')
    pad_v = np.pad(v, 1, mode='edge')

    for j in range(ny):
        for i in range(nx):
            # 3x3 neighborhood centered at (j+1, i+1)
            win_u = pad_u[j:j+3, i:i+3].copy()
            win_v = pad_v[j:j+3, i:i+3].copy()

            # Center element
            u0 = win_u[1, 1]
            v0 = win_v[1, 1]

            if np.isnan(u0) or np.isnan(v0):
                outlier_mask[j, i] = True
                continue

            # Exclude center point for neighbor median
            neighbors_u = np.delete(win_u.flatten(), 4)
            neighbors_v = np.delete(win_v.flatten(), 4)

            # Mask NaNs in neighborhood
            valid = ~(np.isnan(neighbors_u) | np.isnan(neighbors_v))
            if valid.sum() < 3:
                # Too few neighbors
                continue

            nu = neighbors_u[valid]
            nv = neighbors_v[valid]

            u_med = np.median(nu)
            v_med = np.median(nv)

            r_u = np.abs(nu - u_med)
            r_v = np.abs(nv - v_med)

            r_u_med = np.median(r_u)
            r_v_med = np.median(r_v)

            norm_res_u = np.abs(u0 - u_med) / (r_u_med + epsilon)
            norm_res_v = np.abs(v0 - v_med) / (r_v_med + epsilon)

            res_mag = np.sqrt(norm_res_u ** 2 + norm_res_v ** 2)

            if res_mag > threshold:
                outlier_mask[j, i] = True

    return outlier_mask
