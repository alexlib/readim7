"""
readim7.vectors: Vector field extraction, decoding, and coordinate scaling
==========================================================================

Decodes raw multi-component DaVis vector buffers (formats 1, 2, 3, 4, 5) into
standard, physically scaled velocity fields (u, v, w) and coordinates (x, y),
with support for choice maps, peak ratios, and masks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np

from . import core


@dataclass
class VectorField:
    """
    Decoded and scaled PIV vector field.

    Attributes
    ----------
    u : np.ndarray
        Horizontal velocity component (ny, nx), in physical units (e.g. m/s).
    v : np.ndarray
        Vertical velocity component (ny, nx), in physical units (e.g. m/s).
    w : np.ndarray or None
        Out-of-plane velocity component (ny, nx) for 3C stereo/volumetric data.
    x : np.ndarray
        1D horizontal spatial coordinates (nx,), in physical units (e.g. mm).
    y : np.ndarray
        1D vertical spatial coordinates (ny,), in physical units (e.g. mm).
    choice : np.ndarray or None
        Vector choice map (ny, nx): 0=masked/invalid, 1..4=correlation peaks, 5=post-processed/filled.
    peak_ratio : np.ndarray or None
        Correlation peak ratio (ny, nx) if present in buffer format.
    mask : np.ndarray
        Boolean mask (ny, nx) where True indicates invalid or masked vectors.
    units : dict
        Dictionary of units: {'x': str, 'y': str, 'u': str, 'v': str, 'w': str}.
    attributes : dict
        File or buffer metadata attributes.
    vector_grid : int
        Window step size in pixels.
    is_3d : bool
        True if 3-component vector field (stereo or volumetric).
    """
    u: np.ndarray
    v: np.ndarray
    w: Optional[np.ndarray]
    x: np.ndarray
    y: np.ndarray
    choice: Optional[np.ndarray]
    peak_ratio: Optional[np.ndarray]
    mask: np.ndarray
    units: Dict[str, str]
    attributes: Dict[str, Any]
    vector_grid: int
    is_3d: bool

    @property
    def shape(self) -> Tuple[int, int]:
        """(ny, nx) shape of the vector field."""
        return self.u.shape

    @property
    def vmag(self) -> np.ndarray:
        """Velocity magnitude: sqrt(u^2 + v^2 + w^2)."""
        sq = self.u ** 2 + self.v ** 2
        if self.w is not None:
            sq = sq + self.w ** 2
        return np.sqrt(sq)

    @property
    def extent(self) -> Tuple[float, float, float, float]:
        """Bounding box [x_min, x_max, y_min, y_max] in physical coordinates."""
        dx = float(self.x[1] - self.x[0]) if len(self.x) > 1 else 0.0
        dy = float(self.y[1] - self.y[0]) if len(self.y) > 1 else 0.0
        return (
            float(self.x.min() - dx / 2.0),
            float(self.x.max() + dx / 2.0),
            float(self.y.min() - dy / 2.0),
            float(self.y.max() + dy / 2.0),
        )


def _clean_unit(raw_unit: str) -> str:
    """Clean unit strings from DaVis brackets (e.g. '[mm]' -> 'mm')."""
    if not raw_unit:
        return ""
    u = raw_unit.strip()
    if u.startswith("[") and u.endswith("]"):
        u = u[1:-1].strip()
    return u


def compute_coordinates(
    nx: int,
    ny: int,
    vector_grid: int,
    scale_x: Any,
    scale_y: Any,
    invert_y: bool = True,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Compute physical 1D coordinates x and y for vector cell centers.

    Parameters
    ----------
    nx : int
        Number of grid columns.
    ny : int
        Number of grid rows.
    vector_grid : int
        Vector grid spacing in pixels.
    scale_x : dict or BufferScale
        Linear scaling for x: factor, offset, unit.
    scale_y : dict or BufferScale
        Linear scaling for y: factor, offset, unit.
    invert_y : bool
        If True and scale_y.factor < 0, invert row indexing so y is sorted
        strictly ascending (standard Cartesian coordinate system with origin bottom-left).

    Returns
    -------
    x : np.ndarray (nx,)
    y : np.ndarray (ny,)
    did_invert_y : bool
    """
    fx = getattr(scale_x, 'factor', 1.0)
    ox = getattr(scale_x, 'offset', 0.0)
    fy = getattr(scale_y, 'factor', 1.0)
    oy = getattr(scale_y, 'offset', 0.0)

    # Pixel centers of vector windows: (0.5, 1.5, ..., nx - 0.5) * vector_grid
    x_indices = np.arange(nx, dtype=np.float64) + 0.5
    y_indices = np.arange(ny, dtype=np.float64) + 0.5

    x = x_indices * vector_grid * fx + ox
    y = y_indices * vector_grid * fy + oy

    did_invert_y = False
    if invert_y and fy < 0:
        # Invert y order so y increases monotonically upwards
        y = y[::-1]
        did_invert_y = True

    return x, y, did_invert_y


def unpack_vector_field(
    buff_or_filename: Any,
    attributes: Optional[Dict[str, Any]] = None,
    choice_preference: str = "optimal",
    invert_y: bool = True,
    fill_invalid_with_nan: bool = True,
) -> VectorField:
    """
    Unpack a DaVis VC7 buffer or file into a structured VectorField.

    Parameters
    ----------
    buff_or_filename : str | BunchMappable | dict
        Either path to a VC7 file, or a buffer object from get_Buffer_andAttributeList.
    attributes : dict, optional
        Metadata attributes if buff_or_filename is a buffer.
    choice_preference : str
        'optimal' (default): follows choice map (1st, 2nd, 3rd, 4th, or post-processed).
        'first': forces first-choice correlation peak everywhere.
    invert_y : bool
        Whether to invert y when scaleY.factor is negative, placing Cartesian
        origin at bottom-left and adjusting v sign accordingly.
    fill_invalid_with_nan : bool
        If True, locations where choice == 0 (masked or invalid) are set to NaN.

    Returns
    -------
    VectorField
        Decoded vector field containing u, v, w, x, y, choice, peak_ratio, mask, etc.
    """
    from . import extra

    import os

    if isinstance(buff_or_filename, (str, os.PathLike)):
        buff, atts = extra.get_Buffer_andAttributeList(str(buff_or_filename))
    else:
        buff = buff_or_filename
        atts = attributes or {}

    sub_type = int(buff.image_sub_type)
    if sub_type <= 0:
        raise ValueError(
            f"Buffer format {sub_type} is not a recognized vector field format."
        )

    array = buff.array
    ny, nx = buff.ny, buff.nx
    vector_grid = max(1, int(getattr(buff, 'vector_grid', 1)))

    scale_x = buff.scaleX
    scale_y = buff.scaleY
    scale_i = buff.scaleI

    fi = float(getattr(scale_i, 'factor', 1.0))
    oi = float(getattr(scale_i, 'offset', 0.0))

    x, y, did_invert_y = compute_coordinates(
        nx, ny, vector_grid, scale_x, scale_y, invert_y=invert_y
    )

    is_3d = sub_type in (
        core.BUFFER_FORMAT_VECTOR_3D,
        core.BUFFER_FORMAT_VECTOR_3D_EXTENDED_PEAK,
    )

    u = np.zeros((ny, nx), dtype=np.float32)
    v = np.zeros((ny, nx), dtype=np.float32)
    w = np.zeros((ny, nx), dtype=np.float32) if is_3d else None
    choice_map = None
    peak_ratio = None
    mask = np.zeros((ny, nx), dtype=bool)

    if sub_type == core.BUFFER_FORMAT_VECTOR_2D:
        # Simple 2D: slice 0 = vx, slice 1 = vy
        u[...] = array[0] * fi + oi
        v[...] = array[1] * fi + oi

    elif sub_type == core.BUFFER_FORMAT_VECTOR_3D:
        # Simple 3D: slice 0 = vx, slice 1 = vy, slice 2 = vz
        u[...] = array[0] * fi + oi
        v[...] = array[1] * fi + oi
        w[...] = array[2] * fi + oi

    elif sub_type in (
        core.BUFFER_FORMAT_VECTOR_2D_EXTENDED,
        core.BUFFER_FORMAT_VECTOR_2D_EXTENDED_PEAK,
    ):
        raw_choice = np.round(array[0]).astype(np.int32)
        choice_map = raw_choice.copy()

        if choice_preference == "first":
            u[...] = array[1] * fi + oi
            v[...] = array[2] * fi + oi
        else:
            # Optimal choice mapping:
            # 1 -> slice 1, 2
            # 2 -> slice 3, 4
            # 3 -> slice 5, 6
            # 4 -> slice 7, 8
            # 5 (post-processed) -> slice 7, 8
            m1 = raw_choice == 1
            m2 = raw_choice == 2
            m3 = raw_choice == 3
            m4 = raw_choice == 4
            m5 = raw_choice == 5

            u[m1] = array[1][m1] * fi + oi
            v[m1] = array[2][m1] * fi + oi

            u[m2] = array[3][m2] * fi + oi
            v[m2] = array[4][m2] * fi + oi

            u[m3] = array[5][m3] * fi + oi
            v[m3] = array[6][m3] * fi + oi

            u[m4 | m5] = array[7][m4 | m5] * fi + oi
            v[m4 | m5] = array[8][m4 | m5] * fi + oi

        mask[raw_choice == 0] = True
        if sub_type == core.BUFFER_FORMAT_VECTOR_2D_EXTENDED_PEAK and array.shape[0] >= 10:
            peak_ratio = array[9].copy()

    elif sub_type == core.BUFFER_FORMAT_VECTOR_3D_EXTENDED_PEAK:
        raw_choice = np.round(array[0]).astype(np.int32)
        choice_map = raw_choice.copy()

        if choice_preference == "first":
            u[...] = array[1] * fi + oi
            v[...] = array[2] * fi + oi
            w[...] = array[3] * fi + oi
        else:
            # Slices:
            # 1..3: choice 1
            # 4..6: choice 2
            # 7..9: choice 3
            # 10..12: choice 4 / post-processed
            m1 = raw_choice == 1
            m2 = raw_choice == 2
            m3 = raw_choice == 3
            m4 = raw_choice == 4
            m5 = raw_choice == 5

            u[m1] = array[1][m1] * fi + oi
            v[m1] = array[2][m1] * fi + oi
            w[m1] = array[3][m1] * fi + oi

            u[m2] = array[4][m2] * fi + oi
            v[m2] = array[5][m2] * fi + oi
            w[m2] = array[6][m2] * fi + oi

            u[m3] = array[7][m3] * fi + oi
            v[m3] = array[8][m3] * fi + oi
            w[m3] = array[9][m3] * fi + oi

            u[m4 | m5] = array[10][m4 | m5] * fi + oi
            v[m4 | m5] = array[11][m4 | m5] * fi + oi
            w[m4 | m5] = array[12][m4 | m5] * fi + oi

        mask[raw_choice == 0] = True
        if array.shape[0] >= 14:
            peak_ratio = array[13].copy()

    # Incorporate buffer mask if present (from DaVis polygon mask)
    if buff.mask is not None:
        mask = mask | buff.mask[0]

    # Invert rows along axis 0 if y was inverted
    if did_invert_y:
        u = u[::-1, :]
        # Invert vertical velocity sign to keep physical consistency with inverted y
        v = -v[::-1, :]
        if w is not None:
            w = w[::-1, :]
        if choice_map is not None:
            choice_map = choice_map[::-1, :]
        if peak_ratio is not None:
            peak_ratio = peak_ratio[::-1, :]
        mask = mask[::-1, :]

    if fill_invalid_with_nan:
        u[mask] = np.nan
        v[mask] = np.nan
        if w is not None:
            w[mask] = np.nan

    unit_x = _clean_unit(getattr(scale_x, 'unit', 'mm'))
    unit_y = _clean_unit(getattr(scale_y, 'unit', 'mm'))
    unit_v = _clean_unit(getattr(scale_i, 'unit', 'm/s'))

    units = {
        'x': unit_x,
        'y': unit_y,
        'u': unit_v,
        'v': unit_v,
        'w': unit_v if is_3d else '',
    }

    return VectorField(
        u=u,
        v=v,
        w=w,
        x=x,
        y=y,
        choice=choice_map,
        peak_ratio=peak_ratio,
        mask=mask,
        units=units,
        attributes=dict(atts),
        vector_grid=vector_grid,
        is_3d=is_3d,
    )
