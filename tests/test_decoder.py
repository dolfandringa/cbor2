import math
import struct
import sys
from binascii import unhexlify
from io import BytesIO

import pytest

from cbor2.types import CBORSimpleValue, FrozenDict


def test_fp_attr(impl):
    with pytest.raises(ValueError):
        impl.CBORDecoder(None)
    with pytest.raises(ValueError):

        class A:
            pass

        foo = A()
        foo.read = None
        impl.CBORDecoder(foo)
    with BytesIO(b"foobar") as stream:
        decoder = impl.CBORDecoder(stream)
        assert decoder.fp is stream
        with pytest.raises(AttributeError):
            del decoder.fp


def test_tag_hook_attr(impl):
    with BytesIO(b"foobar") as stream:
        with pytest.raises(ValueError):
            impl.CBORDecoder(stream, tag_hook="foo")
        decoder = impl.CBORDecoder(stream)

        def tag_hook(decoder, tag):
            return None  # noqa: E731

        decoder.tag_hook = tag_hook
        assert decoder.tag_hook is tag_hook
        with pytest.raises(AttributeError):
            del decoder.tag_hook


def test_object_hook_attr(impl):
    with BytesIO(b"foobar") as stream:
        with pytest.raises(ValueError):
            impl.CBORDecoder(stream, object_hook="foo")
        decoder = impl.CBORDecoder(stream)

        def object_hook(decoder, data):
            return None  # noqa: E731

        decoder.object_hook = object_hook
        assert decoder.object_hook is object_hook
        with pytest.raises(AttributeError):
            del decoder.object_hook


def test_str_errors_attr(impl):
    with BytesIO(b"foobar") as stream:
        with pytest.raises(ValueError):
            impl.CBORDecoder(stream, str_errors=False)
        with pytest.raises(ValueError):
            impl.CBORDecoder(stream, str_errors="foo")
        decoder = impl.CBORDecoder(stream)
        decoder.str_errors = "replace"
        assert decoder.str_errors == "replace"
        with pytest.raises(AttributeError):
            del decoder.str_errors


def test_read(impl):
    with BytesIO(b"foobar") as stream:
        decoder = impl.CBORDecoder(stream)
        assert decoder.read(3) == b"foo"
        assert decoder.read(3) == b"bar"
        with pytest.raises(TypeError):
            decoder.read("foo")
        with pytest.raises(impl.CBORDecodeError):
            decoder.read(10)


def test_decode_from_bytes(impl):
    with BytesIO(b"foobar") as stream:
        decoder = impl.CBORDecoder(stream)
        assert decoder.decode_from_bytes(b"\x01") == 1
        with pytest.raises(TypeError):
            decoder.decode_from_bytes("foo")


def test_load(impl):
    with pytest.raises(TypeError):
        impl.load()
    with pytest.raises(TypeError):
        impl.loads()
    assert impl.loads(s=b"\x01") == 1
    with BytesIO(b"\x01") as stream:
        assert impl.load(fp=stream) == 1


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("00", 0),
        ("01", 1),
        ("0a", 10),
        ("17", 23),
        ("1818", 24),
        ("1819", 25),
        ("1864", 100),
        ("1903e8", 1000),
        ("1a000f4240", 1000000),
        ("1b000000e8d4a51000", 1000000000000),
        ("1bffffffffffffffff", 18446744073709551615),
        ("c249010000000000000000", 18446744073709551616),
        ("3bffffffffffffffff", -18446744073709551616),
        ("c349010000000000000000", -18446744073709551617),
        ("20", -1),
        ("29", -10),
        ("3863", -100),
        ("3903e7", -1000),
    ],
)
def test_integer(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


def test_invalid_integer_subtype(impl):
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(b"\x1c")
        assert str(exc.value).endswith("unknown unsigned integer subtype 0x1c")
        assert isinstance(exc, ValueError)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("f90000", 0.0),
        ("f98000", -0.0),
        ("f93c00", 1.0),
        ("fb3ff199999999999a", 1.1),
        ("f93e00", 1.5),
        ("f97bff", 65504.0),
        ("fa47c35000", 100000.0),
        ("fa7f7fffff", 3.4028234663852886e38),
        ("fb7e37e43c8800759c", 1.0e300),
        ("f90001", 5.960464477539063e-8),
        ("f90400", 0.00006103515625),
        ("f9c400", -4.0),
        ("fbc010666666666666", -4.1),
        ("f97c00", float("inf")),
        ("f9fc00", float("-inf")),
        ("fa7f800000", float("inf")),
        ("faff800000", float("-inf")),
        ("fb7ff0000000000000", float("inf")),
        ("fbfff0000000000000", float("-inf")),
    ],
)
def test_float(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize("payload", ["f97e00", "fa7fc00000", "fb7ff8000000000000"])
def test_float_nan(impl, payload):
    decoded = impl.loads(unhexlify(payload))
    assert math.isnan(decoded)


@pytest.fixture(
    params=[("f4", False), ("f5", True), ("f6", None), ("f7", "undefined")],
    ids=["false", "true", "null", "undefined"],
)
def special_values(request, impl):
    payload, expected = request.param
    if expected == "undefined":
        expected = impl.undefined
    return payload, expected


def test_special(impl, special_values):
    payload, expected = special_values
    decoded = impl.loads(unhexlify(payload))
    assert decoded is expected


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("40", b""),
        ("4401020304", b"\x01\x02\x03\x04"),
    ],
)
def test_binary(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("60", ""),
        ("6161", "a"),
        ("6449455446", "IETF"),
        ("62225c", '"\\'),
        ("62c3bc", "\u00fc"),
        ("63e6b0b4", "\u6c34"),
    ],
)
def test_string(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("80", []),
        ("83010203", [1, 2, 3]),
        ("8301820203820405", [1, [2, 3], [4, 5]]),
        (
            "98190102030405060708090a0b0c0d0e0f101112131415161718181819",
            list(range(1, 26)),
        ),
    ],
)
def test_array(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize(
    "payload, expected", [("a0", {}), ("a201020304", {1: 2, 3: 4})]
)
def test_map(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("a26161016162820203", {"a": 1, "b": [2, 3]}),
        ("826161a161626163", ["a", {"b": "c"}]),
        (
            "a56161614161626142616361436164614461656145",
            {"a": "A", "b": "B", "c": "C", "d": "D", "e": "E"},
        ),
    ],
)
def test_mixed_array_map(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("5f42010243030405ff", b"\x01\x02\x03\x04\x05"),
        ("7f657374726561646d696e67ff", "streaming"),
        ("9fff", []),
        ("9f018202039f0405ffff", [1, [2, 3], [4, 5]]),
        ("9f01820203820405ff", [1, [2, 3], [4, 5]]),
        ("83018202039f0405ff", [1, [2, 3], [4, 5]]),
        ("83019f0203ff820405", [1, [2, 3], [4, 5]]),
        (
            "9f0102030405060708090a0b0c0d0e0f101112131415161718181819ff",
            list(range(1, 26)),
        ),
        ("bf61610161629f0203ffff", {"a": 1, "b": [2, 3]}),
        ("826161bf61626163ff", ["a", {"b": "c"}]),
        ("bf6346756ef563416d7421ff", {"Fun": True, "Amt": -2}),
        ("d901029f010203ff", {1, 2, 3}),
    ],
)
def test_streaming(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


@pytest.mark.parametrize(
    "payload",
    [
        "5f42010200",
        "7f63737472a0",
    ],
)
def test_bad_streaming_strings(impl, payload):
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(unhexlify(payload))
        assert exc.match(r"non-(byte)?string found in indefinite length \1string")
        assert isinstance(exc, ValueError)


@pytest.fixture(
    params=[
        ("e0", 0),
        ("e2", 2),
        ("f3", 19),
        ("f820", 32),
    ]
)
def simple_value(request, impl):
    payload, expected = request.param
    return payload, expected, impl.CBORSimpleValue(expected)


def test_simple_value(impl, simple_value):
    payload, expected, wrapped = simple_value
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected
    assert decoded == wrapped


def test_simple_val_as_key(impl):
    decoded = impl.loads(unhexlify("A1F86301"))
    assert decoded == {CBORSimpleValue(99): 1}


def test_premature_end_of_stream(impl):
    """
    Test that the decoder detects a situation where read() returned fewer than expected bytes.

    """
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(unhexlify("437879"))
        exc.match(
            r"premature end of stream \(expected to read 3 bytes, got 2 instead\)"
        )
        assert isinstance(exc, EOFError)


def test_object_hook(impl):
    class DummyType:
        def __init__(self, state):
            self.state = state

    payload = unhexlify("A2616103616205")
    decoded = impl.loads(payload, object_hook=lambda decoder, value: DummyType(value))
    assert isinstance(decoded, DummyType)
    assert decoded.state == {"a": 3, "b": 5}


def test_load_from_file(impl, tmpdir):
    path = tmpdir.join("testdata.cbor")
    path.write_binary(b"\x82\x01\x0a")
    with path.open("rb") as fp:
        obj = impl.load(fp)

    assert obj == [1, 10]


def test_nested_dict(impl):
    value = impl.loads(unhexlify("A1D9177082010201"))
    assert type(value) is dict
    assert value == {impl.CBORTag(6000, (1, 2)): 1}


def test_set(impl):
    payload = unhexlify("d9010283616361626161")
    value = impl.loads(payload)
    assert type(value) is set
    assert value == {"a", "b", "c"}


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("a1a1616161626163", {FrozenDict({"a": "b"}): "c"}),
        (
            "A1A1A10101A1666E6573746564F5A1666E6573746564F4",
            {
                FrozenDict({FrozenDict({1: 1}): FrozenDict({"nested": True})}): {
                    "nested": False
                }
            },
        ),
        ("a182010203", {(1, 2): 3}),
        ("a1d901028301020304", {frozenset({1, 2, 3}): 4}),
        ("A17f657374726561646d696e67ff01", {"streaming": 1}),
        ("d9010282d90102820102d90102820304", {frozenset({1, 2}), frozenset({3, 4})}),
    ],
)
def test_immutable_keys(impl, payload, expected):
    value = impl.loads(unhexlify(payload))
    assert value == expected


# Corrupted or invalid data checks


def test_huge_truncated_array(impl, will_overflow):
    with pytest.raises(impl.CBORDecodeError):
        impl.loads(unhexlify("9b") + will_overflow)


def test_huge_truncated_string(impl):
    huge_index = struct.pack("Q", sys.maxsize + 1)
    with pytest.raises((impl.CBORDecodeError, MemoryError)):
        impl.loads(unhexlify("7b") + huge_index + unhexlify("70717273"))


@pytest.mark.parametrize("dtype_prefix", ["7B", "5b"], ids=["string", "bytes"])
def test_huge_truncated_data(impl, dtype_prefix, will_overflow):
    with pytest.raises((impl.CBORDecodeError, MemoryError)):
        impl.loads(unhexlify(dtype_prefix) + will_overflow)


@pytest.mark.parametrize("tag_dtype", ["7F7B", "5f5B"], ids=["string", "bytes"])
def test_huge_truncated_indefinite_data(impl, tag_dtype, will_overflow):
    huge_index = struct.pack("Q", sys.maxsize + 1)
    with pytest.raises((impl.CBORDecodeError, MemoryError)):
        impl.loads(unhexlify(tag_dtype) + huge_index + unhexlify("70717273ff"))


@pytest.mark.parametrize(
    "data", ["7f61777f6177ffff", "5f41775f4177ffff"], ids=["string", "bytes"]
)
def test_embedded_indefinite_data(impl, data):
    with pytest.raises(impl.CBORDecodeValueError):
        impl.loads(unhexlify(data))


@pytest.mark.parametrize("data", ["7f01ff", "5f01ff"], ids=["string", "bytes"])
def test_invalid_indefinite_data_item(impl, data):
    with pytest.raises(impl.CBORDecodeValueError):
        impl.loads(unhexlify(data))


@pytest.mark.parametrize(
    "data",
    ["7f7bff0000000000000471717272ff", "5f5bff0000000000000471717272ff"],
    ids=["string", "bytes"],
)
def test_indefinite_overflow(impl, data):
    with pytest.raises(impl.CBORDecodeValueError):
        impl.loads(unhexlify(data))


def test_invalid_cbor(impl):
    with pytest.raises(impl.CBORDecodeError):
        impl.loads(
            unhexlify(
                "c788370016b8965bdb2074bff82e5a20e09bec21f8406e86442b87ec3ff245b70a47624dc9cdc682"
                "4b2a4c52e95ec9d6b0534b71c2b49e4bf9031500cee6869979c297bb5a8b381e98db714108415e5c"
                "50db78974c271579b01633a3ef6271be5c225eb2"
            )
        )


@pytest.mark.parametrize(
    "data, expected",
    [("fc", "1c"), ("fd", "1d"), ("fe", "1e")],
)
def test_reserved_special_tags(impl, data, expected):
    with pytest.raises(impl.CBORDecodeValueError) as exc_info:
        impl.loads(unhexlify(data))
    assert (
        exc_info.value.args[0]
        == "Undefined Reserved major type 7 subtype 0x" + expected
    )


@pytest.mark.parametrize(
    "data, expected",
    [("c400", "4"), ("c500", "5")],
)
def test_decimal_payload_unpacking(impl, data, expected):
    with pytest.raises(impl.CBORDecodeValueError) as exc_info:
        impl.loads(unhexlify(data))
    assert exc_info.value.args[0] == f"Incorrect tag {expected} payload"
