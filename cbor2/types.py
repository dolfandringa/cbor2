from collections.abc import Mapping
from functools import total_ordering
from reprlib import recursive_repr
from enum import IntEnum


class CBORError(Exception):
    "Base class for errors that occur during CBOR encoding or decoding."


class CBOREncodeError(CBORError):
    "Raised for exceptions occurring during CBOR encoding."


class CBOREncodeTypeError(CBOREncodeError, TypeError):
    "Raised when attempting to encode a type that cannot be serialized."


class CBOREncodeValueError(CBOREncodeError, ValueError):
    "Raised when the CBOR encoder encounters an invalid value."


class CBORDecodeError(CBORError):
    "Raised for exceptions occurring during CBOR decoding."


class CBORDecodeValueError(CBORDecodeError, ValueError):
    "Raised when the CBOR stream being decoded contains an invalid value."


class CBORDecodeEOF(CBORDecodeError, EOFError):
    "Raised when decoding unexpectedly reaches EOF."


@total_ordering
class CBORTag:
    """
    Represents a CBOR semantic tag.

    :param int tag: tag number
    :param value: encapsulated value (any object)
    """

    __slots__ = "tag", "value"

    def __init__(self, tag, value):
        if not isinstance(tag, int) or tag not in range(2**64):
            raise TypeError("CBORTag tags must be positive integers less than 2**64")
        self.tag = tag
        self.value = value

    def __eq__(self, other):
        if isinstance(other, CBORTag):
            return (self.tag, self.value) == (other.tag, other.value)
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, CBORTag):
            return (self.tag, self.value) <= (other.tag, other.value)
        return NotImplemented

    @recursive_repr()
    def __repr__(self):
        return "CBORTag({self.tag}, {self.value!r})".format(self=self)

    def __hash__(self):
        return hash((self.tag, self.value))

_simple_values_lo = [(f'_{n:03d}', n) for n in range(20)]
_simple_values_hi = [(f'_{n:03d}', n) for n in range(32, 256)]
CBORSimpleValue = IntEnum('CBORSimpleValue', _simple_values_lo + _simple_values_hi)



class FrozenDict(Mapping):
    """
    A hashable, immutable mapping type.

    The arguments to ``FrozenDict`` are processed just like those to ``dict``.
    """

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __repr__(self):
        return f"{self.__class__.__name__}({self._d})"

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((frozenset(self), frozenset(self.values())))
        return self._hash


class UndefinedType:
    __slots__ = ()

    def __new__(cls):
        try:
            return undefined
        except NameError:
            return super().__new__(cls)

    def __repr__(self):
        return "undefined"

    def __bool__(self):
        return False

    __nonzero__ = __bool__  # Py2.7 compat


class BreakMarkerType:
    __slots__ = ()

    def __new__(cls):
        try:
            return break_marker
        except NameError:
            return super().__new__(cls)

    def __repr__(self):
        return "break_marker"

    def __bool__(self):
        return True

    __nonzero__ = __bool__  # Py2.7 compat


#: Represents the "undefined" value.
undefined = UndefinedType()
break_marker = BreakMarkerType()
