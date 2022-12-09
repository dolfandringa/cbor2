import os
import platform
import sys

from pkg_resources import parse_version
from setuptools import Extension, setup

min_glibc = parse_version("2.9")


def check_libc():
    """Return False if we have glibc < 2.9 and should not build the C extension."""

    # Borrowed from pip internals
    # https://github.com/pypa/pip/blob/20.1.1/src/pip/_internal/utils/glibc.py#L21-L36
    try:
        # os.confstr("CS_GNU_LIBC_VERSION") returns a string like "glibc 2.17":
        libc, version = os.confstr("CS_GNU_LIBC_VERSION").split()
    except (AttributeError, OSError, ValueError):
        # os.confstr() or CS_GNU_LIBC_VERSION not available (or a bad value)...
        return True

    if libc != "glibc":
        # Attempt to build with musl or other libc
        return True

    return parse_version(version) >= min_glibc


cpython = platform.python_implementation() == "CPython"
windows = sys.platform.startswith("win")
use_c_ext = os.environ.get("CBOR2_BUILD_C_EXTENSION", None)
if use_c_ext is not None:
    build_c_ext = use_c_ext.lower() in ("1", "true")
else:
    build_c_ext = cpython and (windows or check_libc())

# Enable GNU features for libc's like musl, should have no effect
# on Apple/BSDs
cflags = ["-std=c99"]
if not windows:
    cflags.append("-D_GNU_SOURCE")


if build_c_ext:
    _cbor2 = Extension(
        "_cbor2",
        # math.h routines are built-in to MSVCRT
        libraries=["m"] if not windows else [],
        extra_compile_args=cflags,
        sources=[
            "source/module.c",
            "source/encoder.c",
            "source/decoder.c",
            "source/tags.c",
            "source/halffloat.c",
        ],
        optional=True,
    )
    kwargs = {"ext_modules": [_cbor2]}
else:
    kwargs = {}


setup(
    use_scm_version={"version_scheme": "guess-next-dev", "local_scheme": "dirty-tag"},
    setup_requires=["setuptools >= 61", "setuptools_scm >= 6.4"],
    **kwargs
)
