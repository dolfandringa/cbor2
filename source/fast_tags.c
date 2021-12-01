// To be inlined in "decoder.c" if CBOR2_FAST_TAGS is defined

static PyObject *
parse_datestr(CBORDecoderObject *self, PyObject *str)
{
    const char* buf;
    char *p;
    Py_ssize_t size;
    PyObject *tz, *delta, *ret = NULL;
    bool offset_sign;
    unsigned long int Y, m, d, H, M, S, offset_H, offset_M, uS;

    if (!_CBOR2_timezone_utc && _CBOR2_init_timezone_utc() == -1)
        return NULL;
    buf = PyUnicode_AsUTF8AndSize(str, &size);
    if (
            size < 20 || buf[4] != '-' || buf[7] != '-' ||
            buf[10] != 'T' || buf[13] != ':' || buf[16] != ':')
    {
        PyErr_Format(
            _CBOR2_CBORDecodeValueError, "invalid isoformat string %R", str);
        return NULL;
    }
    if (buf) {
        Y = strtoul(buf, NULL, 10);
        m = strtoul(buf + 5, NULL, 10);
        d = strtoul(buf + 8, NULL, 10);
        H = strtoul(buf + 11, NULL, 10);
        M = strtoul(buf + 14, NULL, 10);
        S = strtoul(buf + 17, &p, 10);
        uS = 0;
        if (*p == '.') {
            unsigned long int scale = 100000;
            p++;
            while (*p >= '0' && *p <= '9') {
                uS += (*p++ - '0') * scale;
                scale /= 10;
            }
        }
        if (*p == 'Z') {
            offset_sign = false;
            Py_INCREF(_CBOR2_timezone_utc);
            tz = _CBOR2_timezone_utc;
        } else {
            tz = NULL;
            offset_sign = *p == '-';
            if (offset_sign || *p == '+') {
                p++;
                offset_H = strtoul(p, &p, 10);
                offset_M = strtoul(p + 1, &p, 10);
                delta = PyDelta_FromDSU(0,
                    (offset_sign ? -1 : 1) *
                    (offset_H * 3600 + offset_M * 60), 0);
                if (delta) {
#if PY_VERSION_HEX >= 0x03070000
                    tz = PyTimeZone_FromOffset(delta);
#else
                    tz = PyObject_CallFunctionObjArgs(
                        _CBOR2_timezone, delta, NULL);
#endif
                    Py_DECREF(delta);
                }
            } else
                PyErr_Format(
                    _CBOR2_CBORDecodeValueError,
                    "invalid isoformat string %R", str);
        }
        if (tz) {
            ret = PyDateTimeAPI->DateTime_FromDateAndTime(
                    Y, m, d, H, M, S, uS, tz, PyDateTimeAPI->DateTimeType);
            Py_DECREF(tz);
        }
    }
    return ret;
}


// CBORDecoder.decode_datetime_string(self)
static PyObject *
CBORDecoder_decode_datetime_string(CBORDecoderObject *self)
{
    // semantic type 0
    PyObject *match, *str, *ret = NULL;

    if (!_CBOR2_datestr_re && _CBOR2_init_re_compile() == -1)
        return NULL;
    str = decode(self, DECODE_NORMAL);
    if (str) {
        if (PyUnicode_Check(str)) {
            match = PyObject_CallMethodObjArgs(
                    _CBOR2_datestr_re, _CBOR2_str_match, str, NULL);
            if (match) {
                if (match != Py_None)
                    ret = parse_datestr(self, str);
                else
                    PyErr_Format(
                        _CBOR2_CBORDecodeValueError,
                        "Invalid isoformat string: %R", str);
                Py_DECREF(match);
            }
        } else
            PyErr_Format(
                _CBOR2_CBORDecodeValueError, "invalid datetime value: %R", str);
        Py_DECREF(str);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_epoch_datetime(self)
static PyObject *
CBORDecoder_decode_epoch_datetime(CBORDecoderObject *self)
{
    // semantic type 1
    PyObject *num, *tuple, *ret = NULL;

    if (!_CBOR2_timezone_utc && _CBOR2_init_timezone_utc() == -1)
        return NULL;
    num = decode(self, DECODE_NORMAL);
    if (num) {
        if (PyNumber_Check(num)) {
            tuple = PyTuple_Pack(2, num, _CBOR2_timezone_utc);
            if (tuple) {
                ret = PyDateTime_FromTimestamp(tuple);
                Py_DECREF(tuple);
            }
        } else {
            PyErr_Format(
                _CBOR2_CBORDecodeValueError, "invalid timestamp value %R", num);
        }
        Py_DECREF(num);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_positive_bignum(self)
static PyObject *
CBORDecoder_decode_positive_bignum(CBORDecoderObject *self)
{
    // semantic type 2
    PyObject *bytes, *ret = NULL;

    bytes = decode(self, DECODE_NORMAL);
    if (bytes) {
        if (PyBytes_CheckExact(bytes))
            ret = PyObject_CallMethod(
                (PyObject*) &PyLong_Type, "from_bytes", "Os", bytes, "big");
        else
            PyErr_Format(
                _CBOR2_CBORDecodeValueError, "invalid bignum value %R", bytes);
        Py_DECREF(bytes);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_negative_bignum(self)
static PyObject *
CBORDecoder_decode_negative_bignum(CBORDecoderObject *self)
{
    // semantic type 3
    PyObject *value, *one, *neg, *ret = NULL;

    value = CBORDecoder_decode_positive_bignum(self);
    if (value) {
        one = PyLong_FromLong(1);
        if (one) {
            neg = PyNumber_Negative(value);
            if (neg) {
                ret = PyNumber_Subtract(neg, one);
                Py_DECREF(neg);
            }
            Py_DECREF(one);
        }
        Py_DECREF(value);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_fraction(self)
static PyObject *
CBORDecoder_decode_fraction(CBORDecoderObject *self)
{
    // semantic type 4
    PyObject *payload_t, *tmp, *sig, *exp, *ret = NULL;
    PyObject *decimal_t, *sign, *digits, *args = NULL;

    if (!_CBOR2_Decimal && _CBOR2_init_Decimal() == -1)
        return NULL;
    // NOTE: There's no particular necessity for this to be immutable, it's
    // just a performance choice
    payload_t = decode(self, DECODE_IMMUTABLE | DECODE_UNSHARED);
    if (payload_t) {
        if (PyTuple_CheckExact(payload_t) && PyTuple_GET_SIZE(payload_t) == 2) {
            exp = PyTuple_GET_ITEM(payload_t, 0);
            sig = PyTuple_GET_ITEM(payload_t, 1);
            tmp = PyObject_CallFunction(_CBOR2_Decimal, "O", sig);
            if (tmp) {
                decimal_t = PyObject_CallMethod(tmp, "as_tuple", NULL);
                if (decimal_t) {
                    sign = PyTuple_GET_ITEM(decimal_t, 0);
                    digits = PyTuple_GET_ITEM(decimal_t, 1);
                    args = PyTuple_Pack(3, sign, digits, exp);
                    ret = PyObject_CallFunction(_CBOR2_Decimal, "(O)", args);
                    Py_DECREF(decimal_t);
                    Py_DECREF(args);
                }
                Py_DECREF(tmp);
            }
        } else {
            PyErr_Format(
                _CBOR2_CBORDecodeValueError,
                            "Incorrect tag 4 payload");
            }
        Py_DECREF(payload_t);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_bigfloat
static PyObject *
CBORDecoder_decode_bigfloat(CBORDecoderObject *self)
{
    // semantic type 5
    PyObject *tuple, *tmp, *sig, *exp, *two, *ret = NULL;

    if (!_CBOR2_Decimal && _CBOR2_init_Decimal() == -1)
        return NULL;
    // NOTE: see semantic type 4
    tuple = decode(self, DECODE_IMMUTABLE | DECODE_UNSHARED);
    if (tuple) {
        if (PyTuple_CheckExact(tuple) && PyTuple_GET_SIZE(tuple) == 2) {
            exp = PyTuple_GET_ITEM(tuple, 0);
            sig = PyTuple_GET_ITEM(tuple, 1);
            two = PyObject_CallFunction(_CBOR2_Decimal, "i", 2);
            if (two) {
                tmp = PyNumber_Power(two, exp, Py_None);
                if (tmp) {
                    ret = PyNumber_Multiply(sig, tmp);
                    Py_DECREF(tmp);
                }
                Py_DECREF(two);
            }
        } else {
            PyErr_Format(
                _CBOR2_CBORDecodeValueError,
                            "Incorrect tag 5 payload");
            }
        Py_DECREF(tuple);
    }
    set_shareable(self, ret);
    return ret;
}

// CBORDecoder.decode_rational(self)
static PyObject *
CBORDecoder_decode_rational(CBORDecoderObject *self)
{
    // semantic type 30
    PyObject *tuple, *ret = NULL;

    if (!_CBOR2_Fraction && _CBOR2_init_Fraction() == -1)
        return NULL;
    // NOTE: see semantic type 4
    tuple = decode(self, DECODE_IMMUTABLE | DECODE_UNSHARED);
    if (tuple) {
        if (PyTuple_CheckExact(tuple) && PyTuple_GET_SIZE(tuple) == 2) {
            ret = PyObject_CallFunctionObjArgs(
                    _CBOR2_Fraction,
                    PyTuple_GET_ITEM(tuple, 0),
                    PyTuple_GET_ITEM(tuple, 1),
                    NULL);
        } else {
            PyErr_Format(
                _CBOR2_CBORDecodeValueError,
                            "Incorrect tag 30 payload");
        }
        Py_DECREF(tuple);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_regexp(self)
static PyObject *
CBORDecoder_decode_regexp(CBORDecoderObject *self)
{
    // semantic type 35
    PyObject *pattern, *ret = NULL;

    if (!_CBOR2_re_compile && _CBOR2_init_re_compile() == -1)
        return NULL;
    pattern = decode(self, DECODE_UNSHARED);
    if (pattern) {
        ret = PyObject_CallFunctionObjArgs(_CBOR2_re_compile, pattern, NULL);
        Py_DECREF(pattern);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_mime(self)
static PyObject *
CBORDecoder_decode_mime(CBORDecoderObject *self)
{
    // semantic type 36
    PyObject *value, *parser, *ret = NULL;

    if (!_CBOR2_Parser && _CBOR2_init_Parser() == -1)
        return NULL;
    value = decode(self, DECODE_UNSHARED);
    if (value) {
        parser = PyObject_CallFunctionObjArgs(_CBOR2_Parser, NULL);
        if (parser) {
            ret = PyObject_CallMethodObjArgs(parser,
                    _CBOR2_str_parsestr, value, NULL);
            Py_DECREF(parser);
        }
        Py_DECREF(value);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_uuid(self)
static PyObject *
CBORDecoder_decode_uuid(CBORDecoderObject *self)
{
    // semantic type 37
    PyObject *bytes, *ret = NULL;

    if (!_CBOR2_UUID && _CBOR2_init_UUID() == -1)
        return NULL;
    bytes = decode(self, DECODE_UNSHARED);
    if (bytes) {
        ret = PyObject_CallFunctionObjArgs(_CBOR2_UUID, Py_None, bytes, NULL);
        Py_DECREF(bytes);
    }
    set_shareable(self, ret);
    return ret;
}

// CBORDecoder.decode_set(self)
static PyObject *
CBORDecoder_decode_set(CBORDecoderObject *self)
{
    // semantic type 258
    PyObject *array, *ret = NULL;

    array = decode(self, DECODE_IMMUTABLE);
    if (array) {
        if (PyList_CheckExact(array) || PyTuple_CheckExact(array)) {
            if (self->immutable)
                ret = PyFrozenSet_New(array);
            else
                ret = PySet_New(array);
        } else
            PyErr_Format(
                _CBOR2_CBORDecodeValueError, "invalid set array %R", array);
        Py_DECREF(array);
    }
    // This can be done after construction of the set/frozenset because,
    // unlike lists/dicts a set cannot contain a reference to itself (a set
    // is unhashable). Nor can a frozenset contain a reference to itself
    // because it can't refer to itself during its own construction.
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_ipaddress(self)
static PyObject *
CBORDecoder_decode_ipaddress(CBORDecoderObject *self)
{
    // semantic type 260
    PyObject *tag, *bytes, *ret = NULL;

    if (!_CBOR2_ip_address && _CBOR2_init_ip_address() == -1)
        return NULL;
    bytes = decode(self, DECODE_UNSHARED);
    if (bytes) {
        if (PyBytes_CheckExact(bytes)) {
            if (PyBytes_GET_SIZE(bytes) == 4 || PyBytes_GET_SIZE(bytes) == 16)
                ret = PyObject_CallFunctionObjArgs(_CBOR2_ip_address, bytes, NULL);
            else if (PyBytes_GET_SIZE(bytes) == 6) {
                // MAC address
                tag = CBORTag_New(260);
                if (tag) {
                    if (CBORTag_SetValue(tag, bytes) == 0) {
                        if (self->tag_hook == Py_None) {
                            Py_INCREF(tag);
                            ret = tag;
                        } else {
                            ret = PyObject_CallFunctionObjArgs(
                                    self->tag_hook, tag, NULL);
                        }
                    }
                    Py_DECREF(tag);
                }
            } else
                PyErr_Format(
                    _CBOR2_CBORDecodeValueError,
                    "invalid ipaddress value %R", bytes);
        } else
            PyErr_Format(
                _CBOR2_CBORDecodeValueError,
                "invalid ipaddress value %R", bytes);
        Py_DECREF(bytes);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_ipnetwork(self)
static PyObject *
CBORDecoder_decode_ipnetwork(CBORDecoderObject *self)
{
    // semantic type 261
    PyObject *map, *tuple, *bytes, *prefixlen, *ret = NULL;
    Py_ssize_t pos = 0;

    if (!_CBOR2_ip_network && _CBOR2_init_ip_address() == -1)
        return NULL;
    map = decode(self, DECODE_UNSHARED);
    if (map) {
        if (PyDict_CheckExact(map) && PyDict_Size(map) == 1) {
            if (PyDict_Next(map, &pos, &bytes, &prefixlen)) {
                if (
                        PyBytes_CheckExact(bytes) &&
                        PyLong_CheckExact(prefixlen) &&
                        (PyBytes_GET_SIZE(bytes) == 4 ||
                         PyBytes_GET_SIZE(bytes) == 16)) {
                    tuple = PyTuple_Pack(2, bytes, prefixlen);
                    if (tuple) {
                        ret = PyObject_CallFunctionObjArgs(
                                _CBOR2_ip_network, tuple, Py_False, NULL);
                        Py_DECREF(tuple);
                    }
                } else
                    PyErr_Format(
                        _CBOR2_CBORDecodeValueError,
                        "invalid ipnetwork value %R", map);
            } else
                // We've already checked the size is 1 so this shouldn't be
                // possible
                assert(0);
        } else
            PyErr_Format(
                _CBOR2_CBORDecodeValueError,
                "invalid ipnetwork value %R", map);
        Py_DECREF(map);
    }
    set_shareable(self, ret);
    return ret;
}


// CBORDecoder.decode_self_describe_cbor(self)
static PyObject *
CBORDecoder_decode_self_describe_cbor(CBORDecoderObject *self)
{
    // semantic tag 55799
    return decode(self, DECODE_NORMAL);
}

