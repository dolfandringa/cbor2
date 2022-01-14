import pytest

from cbor2.types import CBORSimpleValue, FrozenDict


def test_undefined_bool(impl):
    assert not impl.undefined


def test_undefined_repr(impl):
    assert repr(impl.undefined) == "undefined"


def test_undefined_singleton(impl):
    assert type(impl.undefined)() is impl.undefined


def test_undefined_init(impl):
    with pytest.raises(TypeError):
        type(impl.undefined)("foo")


def test_break_bool(impl):
    assert impl.break_marker


def test_break_repr(impl):
    assert repr(impl.break_marker) == "break_marker"


def test_break_singleton(impl):
    assert type(impl.break_marker)() is impl.break_marker


def test_break_init(impl):
    with pytest.raises(TypeError):
        type(impl.break_marker)("foo")


def test_tag_init(impl):
    with pytest.raises(TypeError):
        impl.CBORTag("foo", "bar")


def test_tag_attr(impl):
    tag = impl.CBORTag(1, "foo")
    assert tag.tag == 1
    assert tag.value == "foo"


def test_tag_compare(impl):
    tag1 = impl.CBORTag(1, "foo")
    tag2 = impl.CBORTag(1, "foo")
    tag3 = impl.CBORTag(2, "bar")
    tag4 = impl.CBORTag(2, "baz")
    assert tag1 is not tag2
    assert tag1 == tag2
    assert not (tag1 == tag3)
    assert tag1 != tag3
    assert tag3 >= tag2
    assert tag3 > tag2
    assert tag2 < tag3
    assert tag2 <= tag3
    assert tag4 >= tag3
    assert tag4 > tag3
    assert tag3 < tag4
    assert tag3 <= tag4


def test_tag_compare_unimplemented(impl):
    tag = impl.CBORTag(1, "foo")
    assert not tag == (1, "foo")
    with pytest.raises(TypeError):
        tag <= (1, "foo")


def test_tag_recursive(impl):
    tag = impl.CBORTag(1, None)
    tag.value = tag
    assert repr(tag) == "CBORTag(1, ...)"
    assert tag is tag.value
    assert tag == tag.value
    assert not (tag != tag.value)


def test_tag_repr(impl):
    assert repr(impl.CBORTag(600, "blah")) == "CBORTag(600, 'blah')"


def test_simple_value_repr():
    assert repr(CBORSimpleValue(1)) == "<CBORSimpleValue._001: 1>"


def test_simple_value_equals():
    tag1 = CBORSimpleValue(1)
    tag2 = CBORSimpleValue(1)
    tag3 = CBORSimpleValue(32)
    tag4 = CBORSimpleValue(99)
    assert tag1 == tag2
    assert tag1 == 1
    assert not tag2 == "32"
    assert tag1 != tag3
    assert tag1 != 32
    assert tag2 != "32"
    assert tag4 > tag1
    assert tag4 >= tag3
    assert 99 <= tag4
    assert 100 > tag4
    assert tag4 <= 100
    assert 2 < tag4
    assert tag4 >= 99
    assert tag1 <= tag4


def test_simple_ordering():
    randints = [9, 7, 3, 8, 4, 0, 2, 5, 6, 1]
    expected = [CBORSimpleValue(v) for v in range(10)]
    disordered = [CBORSimpleValue(v) for v in randints]
    assert expected == sorted(disordered)
    assert expected == sorted(randints)

def test_simple_wierd_values(impl):
    assert len(impl.dumps(impl.CBORSimpleValue(19))) == 1
    assert impl.dumps(impl.CBORSimpleValue(32)) == b'\xf8\x20'
    assert impl.loads(impl.dumps(impl.CBORSimpleValue(20))) is False
    assert impl.loads(impl.dumps(impl.CBORSimpleValue(21))) is True
    assert impl.loads(impl.dumps(impl.CBORSimpleValue(22))) is None
    assert impl.loads(impl.dumps(impl.CBORSimpleValue(23))) is impl.undefined

def test_simple_too_small(impl):
    with pytest.raises(ValueError) as exc:
        impl.loads(b'\xf8\x14')
        assert str(exc.value) == "invalid 2 byte simple value: 0x14"


def test_simple_value_too_big():
    with pytest.raises(ValueError) as exc:
        CBORSimpleValue(256)
        assert str(exc.value) == '256 is not a valid CBORSimpleValue'


def test_frozendict():
    assert len(FrozenDict({1: 2, 3: 4})) == 2
    assert repr(FrozenDict({1: 2})) == "FrozenDict({1: 2})"
