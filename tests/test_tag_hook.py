import re
from binascii import unhexlify
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.message import Message
from fractions import Fraction
from ipaddress import ip_address, ip_network
from uuid import UUID

import pytest

from cbor2.tag_handler import TagHandler
from cbor2.types import CBORDecodeError

#
# Tests for extension tags
#


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            "c074323031332d30332d32315432303a30343a30305a",
            datetime(2013, 3, 21, 20, 4, 0, tzinfo=timezone.utc),
        ),
        (
            "c0781b323031332d30332d32315432303a30343a30302e3338303834315a",
            datetime(2013, 3, 21, 20, 4, 0, 380841, tzinfo=timezone.utc),
        ),
        (
            "c07819323031332d30332d32315432323a30343a30302b30323a3030",
            datetime(2013, 3, 21, 22, 4, 0, tzinfo=timezone(timedelta(hours=2))),
        ),
        ("c11a514b67b0", datetime(2013, 3, 21, 20, 4, 0, tzinfo=timezone.utc)),
        (
            "c11a514b67b0",
            datetime(2013, 3, 21, 22, 4, 0, tzinfo=timezone(timedelta(hours=2))),
        ),
    ],
    ids=[
        "datetime/utc",
        "datetime+micro/utc",
        "datetime/eet",
        "timestamp/utc",
        "timestamp/eet",
    ],
)
def test_datetime(impl, payload, expected):
    decoded = impl.loads(unhexlify(payload))
    assert decoded == expected


def test_datetime_secfrac(impl):
    decoded = impl.loads(b"\xc0\x78\x182018-08-02T07:00:59.100Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 100000, tzinfo=timezone.utc)
    decoded = impl.loads(b"\xc0\x78\x182018-08-02T07:00:59.010Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 10000, tzinfo=timezone.utc)
    decoded = impl.loads(b"\xc0\x78\x182018-08-02T07:00:59.001Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 1000, tzinfo=timezone.utc)
    decoded = impl.loads(b"\xc0\x78\x1b2018-08-02T07:00:59.000100Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 100, tzinfo=timezone.utc)
    decoded = impl.loads(b"\xc0\x78\x1b2018-08-02T07:00:59.000010Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 10, tzinfo=timezone.utc)
    decoded = impl.loads(b"\xc0\x78\x1b2018-08-02T07:00:59.000001Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 1, tzinfo=timezone.utc)
    decoded = impl.loads(b"\xc0\x78\x1b2018-08-02T07:00:59.000000Z")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 0, tzinfo=timezone.utc)


def test_datetime_secfrac_naive_float_to_int_cast(impl):
    # A secfrac that would have rounding errors if naively parsed as
    # `int(float(secfrac) * 1000000)`.
    decoded = impl.loads(b"\xc0\x78\x202018-08-02T07:00:59.000251+00:00")
    assert decoded == datetime(2018, 8, 2, 7, 0, 59, 251, tzinfo=timezone.utc)


def test_bad_datetime(impl):
    with pytest.raises(ValueError) as excinfo:
        impl.loads(unhexlify("c06b303030302d3132332d3031"))
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "Invalid isoformat string: '0000-123-01'"


def test_positive_bignum(impl):
    # Example from RFC 8949 section 3.4.3.
    decoded = impl.loads(unhexlify("c249010000000000000000"))
    assert decoded == 18446744073709551616


def test_negative_bignum(impl):
    decoded = impl.loads(unhexlify("c349010000000000000000"))
    assert decoded == -18446744073709551617


def test_fraction(impl):
    decoded = impl.loads(unhexlify("c48221196ab3"))
    assert decoded == Decimal("273.15")


def test_decimal_precision(impl):
    decoded = impl.loads(unhexlify("c482384dc252011f1fe37d0c70ff50456ba8b891997b07d6"))
    assert decoded == Decimal("9.7703426561852468194804075821069770622934E-38")


def test_bigfloat(impl):
    decoded = impl.loads(unhexlify("c5822003"))
    assert decoded == Decimal("1.5")


def test_rational(impl):
    decoded = impl.loads(unhexlify("d81e820205"))
    assert decoded == Fraction(2, 5)


def test_bad_rational(impl):
    with pytest.raises(ValueError) as excinfo:
        impl.loads(unhexlify("d81e81196AB3"))
    assert str(excinfo.value) == "Incorrect tag 30 payload"


def test_regex(impl):
    decoded = impl.loads(unhexlify("d8236d68656c6c6f2028776f726c6429"))
    expr = re.compile("hello (world)")
    assert decoded == expr


def test_mime(impl):
    decoded = impl.loads(
        unhexlify(
            "d824787b436f6e74656e742d547970653a20746578742f706c61696e3b20636861727365743d2269736f2d38"
            "3835392d3135220a4d494d452d56657273696f6e3a20312e300a436f6e74656e742d5472616e736665722d45"
            "6e636f64696e673a2071756f7465642d7072696e7461626c650a0a48656c6c6f203d413475726f"
        )
    )
    assert isinstance(decoded, Message)
    assert decoded.get_payload() == "Hello =A4uro"


def test_uuid(impl):
    decoded = impl.loads(unhexlify("d825505eaffac8b51e480581277fdcc7842faf"))
    assert decoded == UUID(hex="5eaffac8b51e480581277fdcc7842faf")


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("d9010444c00a0a01", ip_address("192.10.10.1")),
        (
            "d901045020010db885a3000000008a2e03707334",
            ip_address("2001:db8:85a3::8a2e:370:7334"),
        ),
    ],
    ids=[
        "ipv4",
        "ipv6",
    ],
)
def test_ipaddress(impl, payload, expected):
    payload = unhexlify(payload)
    result = impl.loads(payload)
    assert result == expected


def test_macaddress(impl):
    payload, expected = ("d9010446010203040506", (260, b"\x01\x02\x03\x04\x05\x06"))
    result = impl.loads(unhexlify(payload))
    assert (result.tag, result.value) == expected


def test_bad_ipaddress(impl):
    with pytest.raises((CBORDecodeError, impl.CBORDecodeValueError)) as exc:
        impl.loads(unhexlify("d9010443c00a0a"))
        assert str(exc.value).endswith("invalid ipaddress value %r" % b"\xc0\x0a\x0a")
        assert isinstance(exc, ValueError)
    with pytest.raises((CBORDecodeError, impl.CBORDecodeValueError)) as exc:
        impl.loads(unhexlify("d9010401"))
        assert str(exc.value).endswith("invalid ipaddress value 1")
        assert isinstance(exc, ValueError)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("d90105a144c0a800641818", ip_network("192.168.0.100/24", False)),
        (
            "d90105a15020010db885a3000000008a2e000000001860",
            ip_network("2001:db8:85a3:0:0:8a2e::/96", False),
        ),
    ],
    ids=[
        "ipv4",
        "ipv6",
    ],
)
def test_ipnetwork(impl, payload, expected):
    # XXX The following pytest.skip is only included to work-around a bug in
    # pytest under python 3.3 (which prevents the decorator above from skipping
    # correctly); remove when 3.3 support is dropped
    payload = unhexlify(payload)
    assert impl.loads(payload) == expected


def test_bad_ipnetwork(impl):
    with pytest.raises((CBORDecodeError, impl.CBORDecodeValueError)) as exc:
        impl.loads(unhexlify("d90105a244c0a80064181844c0a800001818"))
        assert str(exc.value).endswith(
            "invalid ipnetwork value %r"
            % {b"\xc0\xa8\x00d": 24, b"\xc0\xa8\x00\x00": 24}
        )
        assert isinstance(exc, ValueError)
    with pytest.raises((CBORDecodeError, impl.CBORDecodeValueError)) as exc:
        impl.loads(unhexlify("d90105a144c0a80064420102"))
        assert str(exc.value).endswith(
            "invalid ipnetwork value %r" % {b"\xc0\xa8\x00d": b"\x01\x02"}
        )
        assert isinstance(exc, ValueError)


def test_bad_shared_reference(impl):
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(unhexlify("d81d05"))
        assert str(exc.value).endswith("shared reference 5 not found")
        assert isinstance(exc, ValueError)


def test_uninitialized_shared_reference(impl):
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(unhexlify("D81CA1D81D014161"))
        assert str(exc.value).endswith("shared value 0 has not been initialized")
        assert isinstance(exc, ValueError)


def test_immutable_shared_reference(impl):
    # a = (1, 2, 3)
    # b = ((a, a), a)
    # data = dumps(set(b))
    decoded = impl.loads(unhexlify("d90102d81c82d81c82d81c83010203d81d02d81d02"))
    a = [item for item in decoded if len(item) == 3][0]
    b = [item for item in decoded if len(item) == 2][0]
    assert decoded == set(((a, a), a))
    assert b[0] is a
    assert b[1] is a


def test_cyclic_array(impl):
    decoded = impl.loads(unhexlify("d81c81d81d00"))
    assert decoded == [decoded]


def test_cyclic_map(impl):
    decoded = impl.loads(unhexlify("d81ca100d81d00"))
    assert decoded == {0: decoded}


def test_string_ref(impl):
    decoded = impl.loads(
        unhexlify("d9010085656669727374d81900667365636f6e64d81900d81901")
    )
    assert isinstance(decoded, list)
    assert decoded[0] == "first"
    assert decoded[1] == "first"
    assert decoded[2] == "second"
    assert decoded[3] == "first"
    assert decoded[4] == "second"


def test_outside_string_ref_namespace(impl):
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(unhexlify("85656669727374d81900667365636f6e64d81900d81901"))
        assert str(exc.value).endswith("string reference outside of namespace")
        assert isinstance(exc, ValueError)


def test_invalid_string_ref(impl):
    with pytest.raises(impl.CBORDecodeError) as exc:
        impl.loads(
            unhexlify("d9010086656669727374d81900667365636f6e64d81900d81901d81903")
        )
        assert str(exc.value).endswith("string reference 3 not found")
        assert isinstance(exc, ValueError)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("d9d9f71903e8", 1000),
        ("d9d9f7c249010000000000000000", 18446744073709551616),
    ],
    ids=["self_describe_cbor+int", "self_describe_cbor+positive_bignum"],
)
def test_self_describe_cbor(impl, payload, expected):
    assert impl.loads(unhexlify(payload)) == expected


def test_unhandled_tag(impl):
    """
    Test that a tag is simply ignored and its associated value returned if there is no special
    handling available for it.

    """
    decoded = impl.loads(unhexlify("d917706548656c6c6f"))
    assert decoded == impl.CBORTag(6000, "Hello")


def test_set(impl):
    payload = unhexlify("d9010283616361626161")
    value = impl.loads(payload)
    assert type(value) is set
    assert value == {"a", "b", "c"}


@pytest.mark.parametrize(
    "data, expected",
    [("c400", "4"), ("c500", "5")],
)
def test_decimal_payload_unpacking(impl, data, expected):
    with pytest.raises(ValueError) as exc_info:
        impl.loads(unhexlify(data))
    assert exc_info.value.args[0] == f"Incorrect tag {expected} payload"


#
# Tests for custom hook decorator and class
#


def test_tag_hook(impl):
    tag_hook = TagHandler()

    @tag_hook.register(6000)
    def reverse(value):
        return value[::-1]

    decoded = impl.loads(unhexlify("d917706548656c6c6f"), tag_hook=reverse)
    assert decoded == "olleH"


def test_tag_hook_cyclic(impl):
    class DummyType(object):
        def __init__(self, value):
            self.value = value

    tag_hook = TagHandler()

    @tag_hook.register(3000, dynamic=True)
    def unmarshal_dummy(handler, value):
        instance = DummyType.__new__(DummyType)
        handler.decoder.set_shareable(instance)
        instance.value = handler.decoder.decode_from_bytes(value)
        return instance

    decoded = impl.loads(
        unhexlify("D81CD90BB849D81CD90BB843D81D00"), tag_hook=unmarshal_dummy
    )
    assert isinstance(decoded, DummyType)
    assert decoded.value.value is decoded


def test_tag_hook_subclass(impl):
    class MyHook(TagHandler):
        def __init__(self):
            super().__init__()
            self.handlers[6000] = self.reversed

        @staticmethod
        def reversed(value):
            return value[::-1]

    decoded = impl.loads(unhexlify("d917706548656c6c6f"), tag_hook=MyHook())
    assert decoded == "olleH"


def test_tag_hook_custom_class(impl):
    if hasattr(impl.CBORDecoder, "decode_epoch_datetime"):
        assert True
        return

    class MyHook:
        def __call__(self, tag):
            return {"$tag": tag.tag, "$value": tag.value}

    decoded = impl.loads(
        unhexlify("C16F6E6F7420612074696D657374616D70"), tag_hook=MyHook()
    )
    assert decoded == {"$tag": 1, "$value": "not a timestamp"}
