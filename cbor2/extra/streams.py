from cbor2 import (
    CBORDecoder,
    CBORDecodeValueError,
    CBOREncoder,
    CBOREncodeValueError,
    CBORTag,
)


def dump_to_tag(path, obj, **kwargs):
    """
    Dump a single object to a cbor file with the CBOR file magic.
    """
    with open(path, "wb") as fp:
        encoder = CBOREncoder(fp, **kwargs)
        encoder.encode(CBORTag(55799, obj))


class CBORSequenceWriter(object):
    "Write cbor data to a non-delimited stream, with optional header"

    def __init__(self, fp, **kwargs):
        self._encoder = CBOREncoder(fp, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_typ, exc_val, exc_tb):
        pass

    def write(self, data):
        self._encoder.encode(data)

    def writeheader(
        self, file_tag=55800, protocol_tag=0x1EAF1E55, protocol_payload="BOR"
    ):
        """
        write a file header containing file magic 558000 a protocol identifier tag between
        0x01000000 and 0xFFFFFFFF followed by the string "BOR"
        """
        if protocol_tag is not None:
            payload = CBORTag(protocol_tag, protocol_payload)
        else:
            payload = protocol_payload
        self._encoder.encode(CBORTag(file_tag, payload))


class CBORArrayStreamWriter(object):
    "write keys and values to an indefinite length cbor list"

    def __init__(self, fp, **kwargs):
        self._encoder = CBOREncoder(fp, **kwargs)
        self._begin = True

    def __enter__(self):
        return self

    def __exit__(self, exc_typ, exc_val, exc_tb):
        if exc_typ is None:
            self._encoder.write(b"\xff")

    def write(self, data):
        if self._begin:
            self._encoder.fp.write(b"\xD9\xD9\xF7\x9f")
            self._begin = False
        self._encoder.encode(data)


class CBORMapStreamWriter(object):
    "write key, value pairs to an indefinite length cbor map file"

    def __init__(self, fp, **kwargs):
        self._encoder = CBOREncoder(fp, **kwargs)
        self._begin = True

    def __enter__(self):
        return self

    def __exit__(self, exc_typ, exc_val, exc_tb):
        if exc_typ is None:
            self._encoder.write(b"\xff")

    def write(self, key, value):
        if self._begin:
            self._encoder.fp.write(b"\xD9\xD9\xF7\xbf")
            self._begin = False
        try:
            hash(key)
        except TypeError as e:
            raise CBOREncodeValueError(
                f"Cannot encode {key.__class__} as a map key"
            ) from e
        self._encoder.encode(key)
        self._encoder.encode(value)


class CBORSequenceReader(object):
    """
    Read CBOR items concatenated within a file.

    By default it expects the first item to be a header containing two tags,
    marking the string BOR::

        D9 D9F8         # tag(55800) CBOR Sequence file magic
           DA 4F50534E  # tag(1330664270) Protocol identifier tag
             43         # bytes(3)
              424F52    # "BOR"

    To recognise this header pass a tuple of expected tags::

        reader = CBORSequenceReader(opened_file, header_tags=(55800, 1330664270))

    To return the header as the first item, just pass the argument ``header_tags=()``
    """

    def __init__(self, fp, header_tags=(55800,), **kwargs):
        self._decoder = CBORDecoder(fp, **kwargs)
        self._header_tags = header_tags

    def check_tags(self, value):
        for tag_id in self._header_tags:
            try:
                if value.tag == tag_id:
                    value = value.value
                else:
                    raise CBORDecodeValueError(f"unexpected tag 0x{value.tag:08x}")
            except AttributeError:
                pass
        return value

    def readitems(self):
        item = self._decoder.decode()
        item = self.check_tags(item)
        if item != "BOR":
            yield item
        while True:
            try:
                yield self._decoder.decode()
            except EOFError:
                return


if __name__ == "__main__":
    with open("testy.cbor", "wb") as f1:
        with CBORArrayStreamWriter(f1) as writer:
            for n in range(20):
                writer.write(n)
    with open("testz.cbor", "wb") as f:
        with CBORMapStreamWriter(f) as w2:
            for k, v in zip("abcdef", range(6)):
                w2.write(k, v)
    with open("testk.cbor", "wb") as f:
        with CBORSequenceWriter(f) as w3:
            w3.writeheader(protocol_tag=1668546672)  # senml
            for n in (x ** 2 / x ** 3 for x in range(1, 20)):
                w3.write({"mynum": n})
    dump_to_tag("testj.cbor", 17.3)
    with open("testk.cbor", "rb") as f:
        reader = CBORSequenceReader(f, header_tags=(55800, 1668546672))
        for item in reader.readitems():
            print(item)
