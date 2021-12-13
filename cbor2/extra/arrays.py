import numpy as np

from cbor2 import CBORTag
from cbor2.tag_handler import TagHandler

_1D_ARRAY_TO_TAGS = {
    "|u1": 64,
    ">u2": 65,
    ">u4": 66,
    ">u8": 67,
    # "|u1": 68, # Clamped ints from javascript
    "<u2": 69,
    "<u4": 70,
    "<u8": 71,
    "|i1": 72,
    ">i2": 73,
    ">i4": 74,
    ">i8": 75,
    "<i2": 77,
    "<i4": 78,
    "<i8": 79,
    ">f2": 80,
    ">f4": 81,
    ">f8": 82,
    #'>f16': 83, Not natively supported for output on learch
    "<f2": 84,
    "<f4": 85,
    "<f8": 86,
    "<f16": 87,
}
_1D_ARRAY_FROM_TAGS = {
    64: "|u1",
    65: ">u2",
    66: ">u4",
    67: ">u8",
    68: "|u1",
    69: "<u2",
    70: "<u4",
    71: "<u8",
    72: "|i1",
    73: ">i2",
    74: ">i4",
    75: ">i8",
    77: "<i2",
    78: "<i4",
    79: "<i8",
    80: ">f2",
    81: ">f4",
    82: ">f8",
    83: ">f16",
    84: "<f2",
    85: "<f4",
    86: "<f8",
    87: "<f16",
}


def encode_arrays(encoder, value):
    if isinstance(value, np.ndarray):
        dtype = value.dtype.base.str
        dim = value.ndim
        tag_id = _1D_ARRAY_TO_TAGS.get(dtype)
        if dim == 1 and tag_id is not None:
            encoder.encode(CBORTag(tag_id, value.tobytes()))
        elif dim == 1 and tag_id is None:
            # tag as a homogenous array to save space
            encoder.encode(CBORTag(41, value.tolist()))
        else:
            if tag_id is not None:
                output = [value.shape, CBORTag(tag_id, value.tobytes())]
            else:
                output = [value.shape, CBORTag(41, list(value.flat))]
            encoder.encode(CBORTag(40, output))


class ArrayHandler(TagHandler):
    __slots__ = ("array_1d_tags",)

    def __init__(self):
        super().__init__()
        self.handlers[40] = self.unmarshal_ndarray
        self.handlers[1040] = self.unmarshal_fdarray
        self.array_1d_tags = _1D_ARRAY_FROM_TAGS

    def __call__(self, tag):
        if tag.tag == 41:
            return np.array(tag.value)
        if tag.tag in self.array_1d_tags:
            return np.frombuffer(tag.value, dtype=self.array_1d_tags[tag.tag])
        handler = self.handlers.get(tag.tag)
        if handler is None:
            return tag
        return handler(tag.value)

    @staticmethod
    def unmarshal_ndarray(value):
        shape, payload = value
        return payload.reshape(*shape)

    @staticmethod
    def unmarshal_fdarray(value):
        shape, payload = value
        return payload.reshape(*shape, order="F")


if __name__ == "__main__":
    import binascii

    import cbor2

    payload = []
    for dtype in _1D_ARRAY_TO_TAGS.keys():
        payload.append(np.array([1, 2, 3], dtype=dtype))
    encoded = cbor2.dumps(payload, default=encode_arrays)
    print(binascii.hexlify(encoded))
    decoded = cbor2.loads(encoded, tag_hook=ArrayHandler())
    assert all(np.array_equal(a, b) for a, b in zip(payload, decoded))
    md_payload = cbor2.dumps(np.ones((3, 4)), default=encode_arrays)
    md_decoded = cbor2.loads(md_payload, tag_hook=ArrayHandler())
    print(md_decoded)

    tx_payload = cbor2.dumps(
        np.array(list("abcdef")).reshape(2, 3), default=encode_arrays
    )
    print(binascii.hexlify(tx_payload).decode())
    tx_decoded = cbor2.loads(tx_payload, tag_hook=ArrayHandler())
    print(tx_decoded)

    mx_payload = cbor2.dumps(np.array(list("abcdef")), default=encode_arrays)
    print(binascii.hexlify(mx_payload).decode())
    mx_decoded = cbor2.loads(mx_payload, tag_hook=ArrayHandler())
    print(mx_decoded)
