"""
Unified data loader and abstraction for DaVis IMS streams, IM7 image sequences, and VC7 vector files.
"""
from abc import ABC, abstractmethod
from functools import lru_cache
import os
from pathlib import Path
import numpy as np

import readim7
from readim7.extra import get_sample_image_filenames, get_sample_vector_filenames


class BaseDataSource(ABC):
    """Abstract interface for all DaVis data sources."""
    
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.title = self.path.name
        self.metadata = {}
        self.num_frames = 1
        self.channels = ["Default"]
        self.nx = 0
        self.ny = 0

    @abstractmethod
    def get_frame(self, frame_idx=0, channel_idx=0):
        """Return 2D ndarray of shape (ny, nx)."""
        pass

    def get_stats(self, frame_idx=0, channel_idx=0):
        """Return (min, max, p1, p99) for contrast auto-scaling."""
        arr = self.get_frame(frame_idx, channel_idx)
        # Sample or compute percentiles
        vmin = float(np.min(arr))
        vmax = float(np.max(arr))
        if arr.size > 256 * 256:
            # Subsample for sub-millisecond percentile computation
            sub = arr[::4, ::4]
            p1, p99 = np.percentile(sub, [1.0, 99.0])
        else:
            p1, p99 = np.percentile(arr, [1.0, 99.0])
        return vmin, vmax, float(p1), float(p99)


class ImsDataSource(BaseDataSource):
    """DaVis camera stream (.ims) data source."""

    def __init__(self, path):
        super().__init__(path)
        self.info = readim7.ims_info(self.path)
        self.num_frames = self.info['n_pairs']
        self.nx = self.info['nx']
        self.ny = self.info['ny']
        self.frames_per_pair = self.info['frames_per_pair']
        
        if self.frames_per_pair == 2:
            self.channels = ["Pulse A (Frame 0)", "Pulse B (Frame 1)"]
        else:
            self.channels = [f"Pulse {i}" for i in range(self.frames_per_pair)]
            
        self.metadata = {
            "Format": "DaVis Camera Stream (.ims)",
            "Stream Path": self.info['ims_path'],
            "Index Path": str(self.info.get('index_path') or "None"),
            "Pairs / Frames": self.num_frames,
            "Resolution": f"{self.nx} x {self.ny}",
            "Bit Depth": "12-bit packed",
            "Pair Bytes": f"{self.info['pair_bytes']:,} bytes",
        }
        self.title = Path(self.info['ims_path']).name

    @lru_cache(maxsize=16)
    def _read_pair(self, frame_idx):
        return readim7.read_ims_pair(self.info, frame_idx)

    def get_frame(self, frame_idx=0, channel_idx=0):
        frame_idx = max(0, min(frame_idx, self.num_frames - 1))
        channel_idx = max(0, min(channel_idx, len(self.channels) - 1))
        pulse_a, pulse_b = self._read_pair(frame_idx)
        return pulse_a if channel_idx == 0 else pulse_b


class Im7DataSource(BaseDataSource):
    """DaVis IM7 image or image-sequence data source."""

    def __init__(self, path, files=None, initial_idx=0):
        super().__init__(path)
        self.files = [Path(f) for f in files] if files else [self.path]
        self.num_frames = len(self.files)
        self.initial_idx = initial_idx
        
        # Probe first file to determine dimensions and channels
        first_buff, first_attrs = readim7.get_Buffer_andAttributeList(str(self.files[0]))
        self.nx = first_buff.nx
        self.ny = first_buff.ny
        self.nf = first_buff.nf
        
        if self.nf > 1:
            self.channels = [f"Pulse {i+1}" for i in range(self.nf)]
        else:
            self.channels = ["Intensity"]
            
        self.metadata = {
            "Format": "DaVis Image (.im7)",
            "Files": len(self.files),
            "Resolution": f"{self.nx} x {self.ny}",
            "Pulses per file": self.nf,
            "Attributes": first_attrs,
        }
        self.title = self.files[0].name if len(self.files) == 1 else f"{self.path.name} ({len(self.files)} files)"

    @lru_cache(maxsize=16)
    def _load_file(self, file_idx):
        filepath = str(self.files[file_idx])
        buff, _ = readim7.get_Buffer_andAttributeList(filepath)
        arr, _ = readim7.buffer_as_array(buff)
        return arr

    def get_frame(self, frame_idx=0, channel_idx=0):
        frame_idx = max(0, min(frame_idx, self.num_frames - 1))
        arr = self._load_file(frame_idx)
        channel_idx = max(0, min(channel_idx, self.nf - 1))
        if arr.ndim == 3:
            return arr[channel_idx]
        return arr


class Vc7DataSource(BaseDataSource):
    """DaVis VC7 vector field data source."""

    def __init__(self, path, files=None, initial_idx=0):
        super().__init__(path)
        self.files = [Path(f) for f in files] if files else [self.path]
        self.num_frames = len(self.files)
        self.initial_idx = initial_idx
        
        first_buff, first_attrs = readim7.get_Buffer_andAttributeList(str(self.files[0]))
        self.nx = first_buff.nx
        self.ny = first_buff.ny
        self.sub_type = first_buff.image_sub_type
        self.components_count = readim7.core.get_vector_components(self.sub_type)
        
        # Built-in channels: Velocity Magnitude, Vx, Vy, plus individual raw components
        self.channels = ["Velocity Magnitude |V|", "Vx (Horizontal)", "Vy (Vertical)"]
        for c in range(self.components_count):
            self.channels.append(f"Raw Component {c}")
            
        self.metadata = {
            "Format": "DaVis Vector (.vc7)",
            "Files": len(self.files),
            "Grid Resolution": f"{self.nx} x {self.ny}",
            "Vector Subtype": self.sub_type,
            "Components": self.components_count,
            "Attributes": first_attrs,
        }
        self.title = self.files[0].name if len(self.files) == 1 else f"{self.path.name} ({len(self.files)} files)"

    @lru_cache(maxsize=16)
    def _load_file(self, file_idx):
        filepath = str(self.files[file_idx])
        buff, _ = readim7.get_Buffer_andAttributeList(filepath)
        arr, _ = readim7.buffer_as_array(buff)
        return arr

    def get_frame(self, frame_idx=0, channel_idx=0):
        frame_idx = max(0, min(frame_idx, self.num_frames - 1))
        arr = self._load_file(frame_idx)
        
        # arr shape is (components, ny, nx)
        vx = arr[0] if arr.shape[0] > 0 else np.zeros((self.ny, self.nx), dtype=np.float32)
        vy = arr[1] if arr.shape[0] > 1 else np.zeros((self.ny, self.nx), dtype=np.float32)
        
        if channel_idx == 0:  # Magnitude
            return np.hypot(vx, vy)
        elif channel_idx == 1:  # Vx
            return vx
        elif channel_idx == 2:  # Vy
            return vy
        else:
            raw_c = channel_idx - 3
            if 0 <= raw_c < arr.shape[0]:
                return arr[raw_c]
            return vx


def open_dataset(path=None):
    """Open and return an appropriate BaseDataSource for a file or directory.
    
    If path is None or empty, returns sample data bundled with readim7.
    """
    if path is None or str(path).strip() == "":
        samples = get_sample_image_filenames()
        if samples:
            return open_dataset(samples[0])
        raise FileNotFoundError("No input path provided and no sample files found.")

    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p}")

    if p.is_dir():
        # Directory: check for .ims first
        ims_files = sorted(p.glob("*.ims"), key=lambda f: f.stat().st_size)
        if ims_files:
            return ImsDataSource(p)
            
        im7_files = sorted(p.glob("*.[iI][mM]7"))
        if im7_files:
            return Im7DataSource(p, files=im7_files)
            
        vc7_files = sorted(p.glob("*.[vV][cC]7"))
        if vc7_files:
            return Vc7DataSource(p, files=vc7_files)
            
        raise ValueError(f"No .ims, .im7, or .vc7 files found in directory: {p}")

    # File
    ext = p.suffix.lower()
    if ext == ".ims":
        return ImsDataSource(p)
    elif ext == ".im7":
        siblings = sorted(p.parent.glob("*.[iI][mM]7"))
        idx = siblings.index(p) if p in siblings else 0
        return Im7DataSource(p if len(siblings) <= 1 else p.parent, files=siblings, initial_idx=idx)
    elif ext == ".vc7":
        siblings = sorted(p.parent.glob("*.[vV][cC]7"))
        idx = siblings.index(p) if p in siblings else 0
        return Vc7DataSource(p if len(siblings) <= 1 else p.parent, files=siblings, initial_idx=idx)
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Expected .ims, .im7, or .vc7.")
