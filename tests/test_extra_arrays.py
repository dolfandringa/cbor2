import pytest

np = pytest.importorskip("numpy")
arrays = pytest.importorskip("cbor2.extra.arrays")

encode_arrays = arrays.encode_arrays


@pytest.fixture
def tag_hook():
    return arrays.ArrayHandler()


@pytest.mark.parametrize("endian", [">", "<"])
@pytest.mark.parametrize("width", [2, 4, 8])
@pytest.mark.parametrize("dtype", ["u", "i", "f"])
def test_basic_arrays(impl, tag_hook, endian, dtype, width):
    payload = np.array(range(20), dtype=f"{endian}{dtype}{width}")
    encoded = impl.dumps(payload, default=encode_arrays)
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert np.array_equal(payload, decoded)


@pytest.mark.parametrize("dtype", ["u", "i"])
def test_smallints(impl, tag_hook, dtype):
    payload = np.array(range(20), dtype=f"|{dtype}1")
    encoded = impl.dumps(payload, default=encode_arrays)
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert np.array_equal(payload, decoded)


def test_bigfloat(impl, tag_hook):
    payload = np.array(range(20), dtype="<f16")
    encoded = impl.dumps(payload, default=encode_arrays)
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert np.array_equal(payload, decoded)


def test_shaped_arrays(impl, tag_hook):
    payload = np.array([[1, 2, 3], [4, 5, 6]], dtype="|u1", order="C")
    encoded = impl.dumps(payload, default=encode_arrays)
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert np.array_equal(payload, decoded)


def test_decode_fortran_order(impl, tag_hook):
    a = np.array([[1, 2], [3, 4]], dtype="|u1", order="F")
    # Force fortran order (not the default for numpy, but we want to read it.)
    encoded = impl.dumps(
        impl.CBORTag(1040, [a.shape, impl.CBORTag(64, a.tobytes("A"))])
    )
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert np.array_equal(a, decoded)


def test_bool_arrays(impl, tag_hook):
    payload = np.array([True, False, False, True])
    encoded = impl.dumps(payload, default=encode_arrays)
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert np.array_equal(payload, decoded)


def test_fail(impl, tag_hook):
    myobj = type("myobj", (object,), {})
    with pytest.raises(ValueError) as e:
        impl.dumps(myobj(), default=encode_arrays)
    assert (
        str(e.value) == "unable to serialize <class 'test_extra_arrays.myobj'> instance"
    )


def test_return_tag(impl, tag_hook):
    encoded = impl.dumps(impl.CBORTag(99999, "unknown tag"))
    decoded = impl.loads(encoded, tag_hook=tag_hook)
    assert isinstance(decoded, impl.CBORTag)
    assert decoded.tag == 99999 and decoded.value == "unknown tag"
