"""
Fast colormap generation and LUT mapping without heavy matplotlib dependencies.
"""
from functools import lru_cache
import numpy as np

# Control points for scientific colormaps (samples from standard maps)
_COLORMAP_DEFS = {
    "viridis": np.array([
        [0.267004, 0.004874, 0.329415],
        [0.282623, 0.140926, 0.457517],
        [0.253935, 0.265254, 0.529983],
        [0.206756, 0.371758, 0.553117],
        [0.163625, 0.471133, 0.558114],
        [0.127568, 0.566949, 0.550556],
        [0.134692, 0.658636, 0.517649],
        [0.266941, 0.748751, 0.440573],
        [0.477504, 0.821444, 0.318195],
        [0.741388, 0.873449, 0.149561],
        [0.993248, 0.906157, 0.143936]
    ]),
    "plasma": np.array([
        [0.050383, 0.029803, 0.527975],
        [0.254627, 0.013882, 0.615419],
        [0.417642, 0.000564, 0.658390],
        [0.562738, 0.051545, 0.641509],
        [0.692840, 0.165141, 0.564522],
        [0.798216, 0.280197, 0.469538],
        [0.881443, 0.392529, 0.383229],
        [0.949115, 0.517763, 0.295662],
        [0.988260, 0.652325, 0.211364],
        [0.988648, 0.809579, 0.145357],
        [0.940015, 0.975158, 0.131326]
    ]),
    "inferno": np.array([
        [0.001462, 0.000466, 0.013866],
        [0.087411, 0.044556, 0.224813],
        [0.231649, 0.038531, 0.428585],
        [0.390494, 0.057904, 0.517201],
        [0.548981, 0.126485, 0.490074],
        [0.704703, 0.218520, 0.399990],
        [0.844781, 0.334032, 0.278508],
        [0.942701, 0.485121, 0.138843],
        [0.979667, 0.669894, 0.030800],
        [0.957589, 0.871032, 0.236160],
        [0.988362, 0.998364, 0.644924]
    ]),
    "turbo": np.array([
        [0.18995, 0.07176, 0.23217],
        [0.19483, 0.33391, 0.77191],
        [0.12698, 0.59124, 0.95334],
        [0.15947, 0.81397, 0.78520],
        [0.43577, 0.94592, 0.47647],
        [0.71390, 0.92994, 0.22495],
        [0.93440, 0.76451, 0.15823],
        [0.99044, 0.50346, 0.10628],
        [0.86230, 0.21980, 0.07768],
        [0.47960, 0.01583, 0.01055]
    ])
}

AVAILABLE_COLORMAPS = ["gray", "viridis", "turbo", "plasma", "inferno"]


@lru_cache(maxsize=16)
def get_lut_rgba(name="gray"):
    """Return a (256, 4) float32 RGBA lookup table."""
    lut = np.ones((256, 4), dtype=np.float32)
    name = (name or "gray").lower()
    if name == "gray":
        v = np.linspace(0.0, 1.0, 256, dtype=np.float32)
        lut[:, 0] = v
        lut[:, 1] = v
        lut[:, 2] = v
    elif name in _COLORMAP_DEFS:
        pts = _COLORMAP_DEFS[name]
        x_pts = np.linspace(0.0, 1.0, len(pts))
        x_new = np.linspace(0.0, 1.0, 256)
        for c in range(3):
            lut[:, c] = np.interp(x_new, x_pts, pts[:, c]).astype(np.float32)
    else:
        return get_lut_rgba("gray")
    return lut


@lru_cache(maxsize=16)
def get_lut_rgb8(name="gray"):
    """Return a (256, 3) uint8 RGB lookup table."""
    rgba = get_lut_rgba(name)
    rgb8 = np.clip(rgba[:, :3] * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return rgb8


def normalize_to_uint8(arr, vmin, vmax):
    """Normalize numeric 2D array to uint8 indices [0, 255]."""
    if vmin is None or vmax is None or vmax <= vmin:
        vmin = float(arr.min())
        vmax = float(arr.max())
    span = vmax - vmin
    scale = 255.0 / (span if span > 1e-8 else 1.0)
    
    # Fast in-place clipping and conversion
    norm = (arr.astype(np.float32) - float(vmin)) * scale
    return np.clip(norm, 0.0, 255.0).astype(np.uint8)


def apply_colormap_rgba(arr, vmin, vmax, colormap="gray"):
    """Convert 2D array to (ny, nx, 4) float32 RGBA image."""
    u8 = normalize_to_uint8(arr, vmin, vmax)
    lut = get_lut_rgba(colormap)
    return lut[u8]


def apply_colormap_rgb8(arr, vmin, vmax, colormap="gray"):
    """Convert 2D array to (ny, nx, 3) uint8 RGB image."""
    u8 = normalize_to_uint8(arr, vmin, vmax)
    lut = get_lut_rgb8(colormap)
    return lut[u8]
