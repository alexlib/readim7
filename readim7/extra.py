from __future__ import division, print_function, absolute_import

__metaclass__ = type


from . import core
import os
import numpy as np
import inspect
import glob


__all__ = ['BunchMappable', 'get_Buffer_andAttributeList', 'buffer_as_array',
           'buffer_mask_as_array', 'newBuffer', 'WriteIM7',
           'get_sample_folder', 'get_sample_image_filenames',
           'get_sample_vector_filenames']


class BunchMappable():
    """
    An object for iterative access to a mappable object. The keys must always
    be alpha_numeric
    """
    def __init__(self, mappable, immutable=False, str2num=None, parent=None, key=None):
        """str2num can be a method for converting strings to numbers.
        val = str2num(val). Not the converter must return values even if it cannot convert.
        """
        self._parent    = parent
        self._key       = key
        self._immutable = immutable


        super(BunchMappable, self).__setattr__('_mappable', mappable)

        if hasattr(mappable, 'items'):
            for key,val in list(mappable.items()):
                if key.find('_') == 0:
                    continue #Skip intended hidden files
                if hasattr(val, 'items'):
                    self.__dict__[key] = self.__class__(val, immutable=immutable,
                                          str2num=str2num, parent=self, key=key)
                else:
                    if str2num is None:
                        self.__dict__[key] = val
                    else:
                        self.__dict__[key] = str2num(val)


    def __repr__(self):
        return repr(self._mappable)

    def __str__(self):
        rep = ''
        for key, val in list(self.__dict__.items()):
            rep = rep + key + '\n'
        return '\n'.join(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __getattr__(self, name):
        return self[name] # just force a __getitem__ type error

    def __getitem__(self, key):

        if key in self.__dict__:
            return self.__dict__[key]

        else: # Get some info before raising an error
            parent = self
            depth = 0
            keys = [key]
            while hasattr(parent, '_parent'):
                depth += 1
                keys.append(getattr(parent,'_key', ''))
                parent = parent._parent or parent._mappable

            description = getattr(parent, 'filename', None) or repr(parent)
            keys.pop(-1)
            raise KeyError('"{0}" is missing from:"{1}" (depth={2})'.format(
                            '->'.join(reversed(keys)), description, depth))


    def __iter__(self):
        for key in sorted(self._mappable.keys()):
            yield key

    def __setattr__(self,name, value):
        if name in ['_immutable', '_key', '_parent']:
            super(BunchMappable, self).__setattr__(name,value)
        elif self._immutable:
            raise AttributeError('This Object is immutable')
        else:

            if name in self._mappable:
                self._mappable[name] = value
                try:
                    object.__setattr__(self, name, value)
                except AttributeError:
                    pass

    def get(self, key, arg=None):
        if key in self.__dict__:
            return self[key]
        else:
            return arg


def get_Buffer_andAttributeList(filename):
    """
    Load 'filename' (IM7/VC7/IMX/IMG/VEC) and return a buffer and its
    attributes.

    Parameters
    ----------
    filename: str
        path to IM7 or VC7 file.

    Returns
    -------
    buff: BunchMappable
        nx, ny, nz, nf, vector_grid, image_sub_type, is_float,
        scaleX/scaleY/scaleI (each with factor/offset/description/unit),
        array (ndarray), mask (ndarray or None).
    attributes: dict
        {attribute name: value}

    Notes
    -----
        Unlike older versions of readim7 (ReadIM) there is nothing to destroy manually:
        the C buffer is copied into numpy arrays and freed before this
        function returns.
    """

    if not os.path.isfile(filename):
        raise IOError('file not found %s' % filename)

    try:
        data = core.read_file(filename)
    except RuntimeError as e:
        raise IOError(str(e))

    attributes = {_decode_attr(k): _decode_attr(v) for k, v in data.pop('attributes').items()}
    buff = BunchMappable(data, immutable=True)
    return buff, attributes


def _decode_attr(raw):
    """Attribute bytes are not guaranteed to be valid UTF-8 (e.g. LaVision
    writes a raw latin-1 micro sign byte for '\xb5'/unit strings)."""
    val = raw.decode('utf-8', errors='surrogateescape')
    return val.replace('\udcb5', '\xb5')


def buffer_as_array(buff):
    """
    Return (array, buff). array has shape (components, buff.ny, buff.nx)
    where components = core.get_vector_components(buff.image_sub_type) * buff.nf
    for vectors and buff.nf for images.
    """
    return buff.array, buff


def buffer_mask_as_array(buff):
    """
    Return (mask, buff). mask has shape (buff.nf, buff.ny, buff.nx), or
    mask is None if the file has no mask (DaVis < 8).
    """
    return buff.mask, buff


def newBuffer(window, nx=None, ny=None, vectorGrid=24,
              image_sub_type=core.BUFFER_FORMAT_VECTOR_2D,
              frames=1, scaleIoffset=0, scaleIfactor=1):
    """
    Create a new buffer (in-memory only, ready for WriteIM7) using a window
    to describe the extents.

    Parameters
    ----------
     window : 2x2 list
        [(x,y),(x,y)] --> [top left, bottom right]
     nx: int
        Number of columns
     ny: int
        Number of rows
     vectorGrid: int
        Reduction of nx * ny /vectorGrid (for vectors only)
     image_sub_type: int
        One of the following
         -11: 'BUFFER_FORMAT_RGB_32',
         -10: 'BUFFER_FORMAT_RGB_MATRIX',
         -6: 'BUFFER_FORMAT_FLOAT_VALID',
         -5: 'BUFFER_FORMAT_DOUBLE',
         -4: 'BUFFER_FORMAT_WORD',
         -3: 'BUFFER_FORMAT_FLOAT',
         -2: 'BUFFER_FORMAT_MEMPACKWORD',
         -1: 'BUFFER_FORMAT__NOTUSED',
         0: 'BUFFER_FORMAT_IMAGE',
         1: 'BUFFER_FORMAT_VECTOR_2D_EXTENDED',
         2: 'BUFFER_FORMAT_VECTOR_2D',
         3: 'BUFFER_FORMAT_VECTOR_2D_EXTENDED_PEAK',
         4: 'BUFFER_FORMAT_VECTOR_3D',
         5: 'BUFFER_FORMAT_VECTOR_3D_EXTENDED_PEAK'
     frames: int
        number of frames
    scaleIfactor: float
        Scale factor for intensity.
    scaleIoffset: float
        Offset for intensity.

    Returns
    -------
    buff: BunchMappable
    """

    if not nx:
        nx = window[1][0] - window[0][0]
    if not ny:
        ny = window[0][1] - window[1][1]
    nx, ny = int(nx), int(ny)

    is_vector = image_sub_type > 0
    components = core.get_vector_components(image_sub_type) if is_vector else 1
    is_float = True if is_vector else True  # DaVis images are float too by default

    dtype = np.float32 if is_float else np.uint16
    array = np.zeros((components * frames, ny, nx), dtype=dtype)

    info = dict(
        nx=nx, ny=ny, nz=1, nf=int(frames),
        vector_grid=int(vectorGrid), image_sub_type=int(image_sub_type),
        is_float=bool(is_float),
        scaleX=dict(factor=float(window[1][0] - window[0][0]) / nx / vectorGrid,
                    offset=float(window[0][0]), description='', unit='pixel'),
        scaleY=dict(factor=float(window[1][1] - window[0][1]) / ny / vectorGrid,
                    offset=float(window[0][1]), description='', unit='pixel'),
        scaleI=dict(factor=float(scaleIfactor), offset=float(scaleIoffset),
                    description='', unit='counts'),
        array=array,
        mask=None,
    )

    return BunchMappable(info)


def WriteIM7(filename, buff, attributes=None, is_packed=True):
    """
    Write 'buff' (as returned by get_Buffer_andAttributeList or newBuffer)
    to an IM7 file.

    Parameters
    ----------
    filename: str
    buff: BunchMappable | dict
    attributes: dict, optional
    is_packed: bool
        Write as packed (compressed) IMX data.
    """
    info = buff._mappable if isinstance(buff, BunchMappable) else dict(buff)
    try:
        core.write_file(filename, is_packed, info, dict(attributes or {}))
    except RuntimeError as e:
        raise IOError(str(e))


def get_sample_folder():
    folder = os.path.dirname(inspect.getfile(BunchMappable))
    folder = os.path.join(folder, 'sample_files')
    assert os.path.isdir(folder), 'Sample files not found!'
    return folder

def get_sample_image_filenames():
    ptn = get_sample_folder()
    ptn = os.path.join(ptn, '*.im7')
    return glob.glob(ptn)

def get_sample_vector_filenames():
    ptn = get_sample_folder()
    ptn = os.path.join(ptn, '*.vc7')
    return glob.glob(ptn)
