"""
readim7.attributes: DaVis Metadata & Attribute Parser
====================================================

Extracts, cleans, and structures native DaVis metadata attributes into typed
dictionaries and standard physical quantities (timing, calibration, scales).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union


def parse_scale_string(val_str: str) -> Dict[str, Any]:
    """
    Parse a multi-line DaVis scale attribute string.

    Format:
        Line 0: factor (float)
        Line 1: offset (float)
        Line 2: unit (str)
        Line 3+: description (optional str)
    """
    lines = [line.strip() for line in val_str.strip().splitlines() if line.strip()]
    out: Dict[str, Any] = {'factor': 1.0, 'offset': 0.0, 'unit': '', 'description': ''}

    if not lines:
        return out

    try:
        out['factor'] = float(lines[0])
    except ValueError:
        out['factor'] = 1.0

    if len(lines) > 1:
        try:
            out['offset'] = float(lines[1])
        except ValueError:
            out['offset'] = 0.0

    if len(lines) > 2:
        unit = lines[2].strip()
        if unit.startswith('[') and unit.endswith(']'):
            unit = unit[1:-1].strip()
        out['unit'] = unit

    if len(lines) > 3:
        out['description'] = ' '.join(lines[3:])

    return out


def parse_time_value(time_str: str) -> Optional[float]:
    """
    Parse time values with units (e.g. '10000 us', '500 µs', '10 ms', '0.01 s') into seconds.
    """
    if not time_str:
        return None

    cleaned = str(time_str).strip()
    match = re.match(r"^([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Zµμ]*)", cleaned)
    if not match:
        return None

    num_str, unit_str = match.groups()
    try:
        val = float(num_str)
    except ValueError:
        return None

    unit = unit_str.lower()
    if unit in ('us', 'µs', 'μs'):
        return val * 1e-6
    elif unit == 'ms':
        return val * 1e-3
    elif unit == 'ns':
        return val * 1e-9
    elif unit in ('s', 'sec', ''):
        return val

    return val


def parse_davis_attributes(raw_attrs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a dictionary of raw DaVis attributes into structured, typed metadata.

    Parameters
    ----------
    raw_attrs : dict
        Raw attributes dictionary from get_Buffer_andAttributeList.

    Returns
    -------
    dict
        Structured metadata with keys:
        - 'delta_t': pulse separation dt in seconds (float or None)
        - 'date': acquisition date string
        - 'time': acquisition time string
        - 'davis_version': DaVis software version string
        - 'scales': dict of parsed scales ('x', 'y', 'z', 'i')
        - 'cameras': dict of camera details (name, pixel size, exposure time)
        - 'laser_power': dict of laser power settings
        - 'raw': copy of cleaned string attributes
    """
    parsed: Dict[str, Any] = {
        'delta_t': None,
        'date': None,
        'time': None,
        'davis_version': None,
        'scales': {},
        'cameras': {},
        'laser_power': {},
        'raw': {},
    }

    # Extract date, time, DaVis version
    if '_DATE' in raw_attrs:
        parsed['date'] = str(raw_attrs['_DATE']).strip()
    if '_TIME' in raw_attrs:
        parsed['time'] = str(raw_attrs['_TIME']).strip()
    if '_DaVisVersion' in raw_attrs:
        parsed['davis_version'] = str(raw_attrs['_DaVisVersion']).strip()

    # Extract pulse separation dt in seconds
    for dt_key in ('FrameDt0', '_PULSE_SEPARATION_US', 'dt', 'DevDataScaleI2'):
        if dt_key in raw_attrs:
            dt_val = parse_time_value(raw_attrs[dt_key])
            if dt_val is not None:
                parsed['delta_t'] = dt_val
                break

    # Parse scales: FrameScaleX0, FrameScaleY0, FrameScaleZ0, FrameScaleI0, _SCALE_X, etc.
    for scale_prefix in ('FrameScale', '_SCALE_'):
        for dim in ('X', 'Y', 'Z', 'I'):
            key = f"{scale_prefix}{dim}0" if scale_prefix == 'FrameScale' else f"{scale_prefix}{dim}"
            if key in raw_attrs and dim.lower() not in parsed['scales']:
                parsed['scales'][dim.lower()] = parse_scale_string(str(raw_attrs[key]))

    # Parse camera details
    for k, v in raw_attrs.items():
        v_str = str(v).strip()
        parsed['raw'][k] = v_str

        # Camera Name
        cam_name_match = re.match(r"^CameraName(\d+)", k)
        if cam_name_match:
            cam_idx = int(cam_name_match.group(1))
            parsed['cameras'].setdefault(cam_idx, {})['name'] = v_str

        # Camera Pixel Size
        cam_pix_match = re.match(r"^CamPixelSize(\d+)", k)
        if cam_pix_match:
            cam_idx = int(cam_pix_match.group(1))
            parsed['cameras'].setdefault(cam_idx, {})['pixel_size'] = v_str

        # CCD Exposure Time
        exp_match = re.match(r"^CCDExposureTime(\d+)", k)
        if exp_match:
            cam_idx = int(exp_match.group(1))
            parsed['cameras'].setdefault(cam_idx, {})['exposure_time'] = v_str

        # Laser Power
        if 'laser power' in v_str.lower():
            parsed['laser_power'][k] = v_str

    return parsed
