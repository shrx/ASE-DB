from __future__ import print_function
"""Simple and efficient pythonic file-format.

Stores ndarrays as binary data and Python's built-in datatypes (int, float,
bool, str, dict, list) as json.

File layout for a single item::
    
    0: "AFFormat" (magic prefix, ascii)
    8: "                " (tag, ascii)
    24: version (int64)
    32: nitems (int64)
    40: 48 (position of offsets, int64)
    48: p0 (offset to json data, int64)
    56: array1, array2, ... (8-byte aligned ndarrays)
    p0: n (length of json data, int64)
    p0+8: json data
    p0+8+n: EOF

Writing:
    
>>> from ase.io.aff import affopen
>>> w = affopen('x.aff', 'w')
>>> w.write(a=np.ones(7), b=42, c='abc')
>>> w.write(d=3.14)
>>> w.close()
    
Reading:
    
>>> r = affopen('x.aff')
>>> print(r.c)
'abc'

To see what's inside 'x.aff' do this::
    
    $ python -m ase.io.aff x.aff
    x.aff  (tag: "", 1 item)
    item #0:
    {
        a: <ndarray shape=(7,) dtype=float64>,
        b: 42,
        c: abc,
        d: 3.14}

"""

# endianness ???

import os
import optparse

import numpy as np

from ase.io.jsonio import encode, decode
from ase.utils import plural, basestring


VERSION = 1
N1 = 42  # block size - max number of items: 1, N1, N1*N1, N1*N1*N1, ...


def affopen(filename, mode='r', index=None, tag=''):
    """Open aff-file."""
    if mode == 'r':
        return Reader(filename, index or 0)
    if mode not in 'wa':
        2 / 0
    assert index is None
    return Writer(filename, mode, tag)


def align(fd):
    """Advance file descriptor to 8 byte alignment and return position."""
    pos = fd.tell()
    r = pos % 8
    if r == 0:
        return pos
    fd.write(b'#' * (8 - r))
    return pos + 8 - r


def writeint(fd, n, pos=None):
    """Write 64 bit integer n at pos or current position."""
    if pos is not None:
        fd.seek(pos)
    np.array(n, np.int64).tofile(fd)
    
    
class Writer:
    def __init__(self, fd, mode='w', tag='', data=None):
        """Create writer object.
        
        fd: str
            Filename.
        mode: str
            Mode.  Must be 'w' for writing to a new file (overwriting an
            existing one) and 'a' for appending to an existing file.
        tag: str
            Magic ID string.
        """

        assert np.little_endian  # deal with this later
        assert mode in 'aw'
        
        if data is None:
            data = {}
            if mode == 'w' or not os.path.isfile(fd):
                self.nitems = 0
                self.pos0 = 48
                self.offsets = np.array([-1], np.int64)

                fd = open(fd, 'wb')
            
                # Write file format identifier:
                fd.write('AFFormat{0:16}'.format(tag).encode('ascii'))
                np.array([VERSION, self.nitems, self.pos0],
                         np.int64).tofile(fd)
                self.offsets.tofile(fd)
            else:
                fd = open(fd, 'r+b')
            
                version, self.nitems, self.pos0, offsets = read_header(fd)[1:]
                assert version == VERSION
                n = 1
                while self.nitems > n:
                    n *= N1
                padding = np.zeros(n - self.nitems, np.int64)
                self.offsets = np.concatenate((offsets, padding))
                fd.seek(0, 2)
            
        self.fd = fd
        self.data = data
        
        # Shape and dtype of array beeing filled:
        self.shape = (0,)
        self.dtype = None
        
    def add_array(self, name, shape, dtype=float):
        """Add ndarray object."""
        
        if isinstance(shape, int):
            shape = (shape,)
            
        i = align(self.fd)
        
        self.data[name + '.'] = {'ndarray':
                                 (shape,
                                  np.dtype(dtype).name,
                                  i)}
            
        assert self.shape[0] == 0, 'last array not done'
        
        self.dtype = dtype
        self.shape = shape
        
    def fill(self, a):
        assert a.dtype == self.dtype
        if a.shape[1:] == self.shape[1:]:
            assert a.shape[0] <= self.shape[0]
            self.shape = (self.shape[0] - a.shape[0],) + self.shape[1:]
        else:
            assert a.shape == self.shape[1:]
            self.shape = (self.shape[0] - 1,) + self.shape[1:]
        assert self.shape[0] >= 0
            
        a.tofile(self.fd)

    def sync(self):
        """Write data dictionary.

        Write bool, int, float, complex and str data, shapes and
        dtypes for ndarrays."""

        assert self.shape[0] == 0
        i = self.fd.tell()
        s = encode(self.data).encode()
        writeint(self.fd, len(s))
        self.fd.write(s)
        
        n = len(self.offsets)
        if self.nitems >= n:
            offsets = np.zeros(n * N1, np.int64)
            offsets[:n] = self.offsets
            self.pos0 = align(self.fd)
            offsets.tofile(self.fd)
            writeint(self.fd, self.pos0, 40)
            self.offsets = offsets
            
        self.offsets[self.nitems] = i
        writeint(self.fd, i, self.pos0 + self.nitems * 8)
        self.nitems += 1
        writeint(self.fd, self.nitems, 32)
        self.fd.flush()
        self.fd.seek(0, 2)  # end of file
        self.data = {}
        
    def write(self, **kwargs):
        """Write data.

        Use::

            writer.write(n=7, s='abc', a=np.zeros(3), density=density).
        """
        
        for name, value in kwargs.items():
            if isinstance(value, (bool, int, float, complex,
                                  dict, list, tuple, basestring)):
                self.data[name] = value
            elif isinstance(value, np.ndarray):
                self.add_array(name, value.shape, value.dtype)
                self.fill(value)
            else:
                value.write(self.child(name))
      
    def child(self, name):
        dct = self.data[name + '.'] = {}
        return Writer(self.fd, data=dct)
        
    def close(self):
        if self.data:
            self.sync()
        self.fd.close()
        
    def __len__(self):
        return int(self.nitems)
        
        
class DummyWriter:
    def add_array(self, name, shape, dtype=float):
        pass
        
    def fill(self, a):
        pass
        
    def sync(self):
        pass
        
    def write(self, **kwargs):
        pass
        
    def child(self, name):
        return self
        
    def close(self):
        pass
        
    def __len__(self):
        return 0
        
        
def read_header(fd):
    fd.seek(0)
    assert fd.read(8) == b'AFFormat'
    tag = fd.read(16).decode('ascii').rstrip()
    version, nitems, pos0 = np.fromfile(fd, np.int64, 3)
    fd.seek(pos0)
    offsets = np.fromfile(fd, np.int64, nitems)
    return tag, version, nitems, pos0, offsets

    
class Reader:
    def __init__(self, fd, index=0, data=None):
        """Create reader."""
        
        assert np.little_endian

        if isinstance(fd, str):
            fd = open(fd, 'rb')
        
        self._fd = fd
        self._index = index
        
        if data is None:
            (self._tag, self._version, self._nitems, self._pos0,
             self._offsets) = read_header(fd)
            data = self._read_data(index)
            
        self._parse_data(data)
        
    def _parse_data(self, data):
        self._data = {}
        for name, value in data.items():
            if name.endswith('.'):
                if 'ndarray' in value:
                    shape, dtype, offset = value['ndarray']
                    dtype = dtype.encode()  # compatibility with Numpy 1.4
                    value = NDArrayReader(self._fd,
                                          shape,
                                          np.dtype(dtype),
                                          offset)
                else:
                    value = Reader(self._fd, data=value)
                name = name[:-1]
        
            self._data[name] = value
            
    def get_tag(self):
        """Return special tag string."""
        return self._tag
        
    def __dir__(self):
        return self._data.keys()  # needed for tab-completion

    def __getattr__(self, attr):
        value = self._data[attr]
        if isinstance(value, NDArrayReader):
            return value.read()
        return value

    def __contains__(self, key):
        return key in self._data
        
    def __iter__(self):
        yield self
        for i in range(self._index + 1, self._nitems):
            self._index = i
            data = self._read_data(i)
            self._parse_data(data)
            yield self
    
    def get(self, attr, value=None):
        try:
            return self.__getattr__(attr)
        except KeyError:
            return value
            
    def proxy(self, name):
        value = self._data[name]
        assert isinstance(value, NDArrayReader)
        return value

    def __len__(self):
        return int(self._nitems)
        
    def _read_data(self, index):
        self._fd.seek(self._offsets[index])
        size = np.fromfile(self._fd, np.int64, 1)[0]
        data = decode(self._fd.read(size).decode())
        return data
    
    def __getitem__(self, index):
        data = self._read_data(index)
        return Reader(self._fd, index, data)
        
    def tostr(self, verbose=False, indent='    '):
        keys = sorted(self._data)
        strings = []
        for key in keys:
            value = self._data[key]
            if verbose and isinstance(value, NDArrayReader):
                value = value.read()
            if isinstance(value, NDArrayReader):
                s = '<ndarray shape={0} dtype={1}>'.format(value.shape,
                                                           value.dtype)
            elif isinstance(value, Reader):
                s = value.tostr(verbose, indent + '    ')
            else:
                s = str(value).replace('\n', '\n  ' + ' ' * len(key) + indent)
            strings.append('{0}{1}: {2}'.format(indent, key, s))
        return '{\n' + ',\n'.join(strings) + '}'
           
    def __str__(self):
        return self.tostr(False, '').replace('\n', ' ')

        
class NDArrayReader:
    def __init__(self, fd, shape, dtype, offset):
        self.fd = fd
        self.shape = tuple(shape)
        self.dtype = dtype
        self.offset = offset
        
        self.ndim = len(self.shape)
        self.itemsize = dtype.itemsize
        self.size = np.prod(self.shape)
        self.nbytes = self.size * self.itemsize
        
    def __len__(self):
        return int(self.shape[0])  # Python-2.6 needs int
        
    def read(self):
        return self[:]
        
    def __getitem__(self, i):
        if isinstance(i, int):
            return self[i:i + 1][0]
        start, stop, step = i.indices(len(self))
        offset = self.offset + start * self.nbytes // len(self)
        self.fd.seek(offset)
        count = (stop - start) * self.size // len(self)
        a = np.fromfile(self.fd, self.dtype, count)
        a.shape = (-1,) + self.shape[1:]
        if step != 1:
            return a[::step].copy()
        return a

        
def main():
    parser = optparse.OptionParser(
        usage='Usage: %prog [options] aff-file [item number]',
        description='Show content of aff-file')
    
    add = parser.add_option
    add('-v', '--verbose', action='store_true')
    opts, args = parser.parse_args()

    if not args:
        parser.error('No aff-file given')

    filename = args.pop(0)
    b = affopen(filename, 'r')
    indices = [int(args.pop())] if args else range(len(b))
    print('{0}  (tag: "{1}", {2})'.format(filename, b.get_tag(),
                                          plural(len(b), 'item')))
    for i in indices:
        print('item #{0}:'.format(i))
        print(b[i].tostr(opts.verbose))

    
if __name__ == '__main__':
    main()
