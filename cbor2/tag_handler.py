import datetime as dt
import re
import uuid
from collections.abc import Mapping
from decimal import Decimal
from email.parser import Parser
from fractions import Fraction
from ipaddress import ip_address, ip_network
from types import MethodType

from .types import CBORDecodeValueError, CBORTag


class TagHandler(object):

    __slots__ = ("handlers", "decoder")

    def __init__(self):
        self.handlers = {
            0: self.isodatetime,
            1: self.epochdatetime,
            2: self.bigint,
            3: self.negint,
            4: self.decimal,
            5: self.bigfloat,
            25: self.stringref,
            30: self.fraction,
            35: self.regexp,
            36: self.mime,
            37: self.uuid,
            258: self.set,
            260: self.ipaddress,
            261: self.ipnetwork,
            55799: lambda x: x,
        }

    def __call__(self, tag):
        handler = self.handlers.get(tag.tag)
        if handler is None:
            return tag
        return handler(tag.value)

    def _set_decoder(self, decoder):
        self.decoder = decoder

    def register(self, tag_id, dynamic=False):
        if dynamic:

            def decorator(fun):
                method = MethodType(fun, self)
                self.handlers.update({tag_id: method})
                return self

        else:

            def decorator(fun):
                self.handlers.update({tag_id: fun})
                return self

        return decorator

    @staticmethod
    def isodatetime(x):
        return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))

    @staticmethod
    def epochdatetime(x):
        return dt.datetime.fromtimestamp(x, tz=dt.timezone.utc)

    @staticmethod
    def bigint(x):
        return int.from_bytes(x, byteorder="big")

    @staticmethod
    def negint(x):
        return -(1 + int.from_bytes(x, byteorder="big"))

    @staticmethod
    def uuid(x):
        return uuid.UUID(bytes=x)

    @staticmethod
    def decimal(x):
        try:
            exp, sig = x
        except (TypeError, ValueError) as e:
            raise CBORDecodeValueError("Incorrect tag 4 payload") from e
        tmp = Decimal(sig).as_tuple()
        return Decimal((tmp.sign, tmp.digits, exp))

    def set(self, x):
        if self.decoder.immutable:
            return frozenset(x)
        return set(x)

    @staticmethod
    def bigfloat(x):
        # Semantic tag 5
        try:
            exp, sig = x
        except (TypeError, ValueError) as e:
            raise CBORDecodeValueError("Incorrect tag 5 payload") from e
        return Decimal(sig) * (2 ** Decimal(exp))

    def stringref(self, index):
        # Semantic tag 25
        ns = None
        if hasattr(self.decoder, "_stringref_namespace"):
            ns = getattr(self.decoder, "_stringref_namespace")
        if ns is None:
            raise CBORDecodeValueError("string reference outside of namespace")
        try:
            value = ns[index]
        except IndexError:
            raise CBORDecodeValueError("string reference %d not found" % index)

        return value

    @staticmethod
    def fraction(x):
        # Semantic tag 30
        try:
            num, denom = x
        except (TypeError, ValueError) as e:
            raise CBORDecodeValueError("Incorrect tag 30 payload") from e
        return Fraction(num, denom)

    @staticmethod
    def regexp(string):
        # Semantic tag 35
        return re.compile(string)

    @staticmethod
    def mime(message):
        # Semantic tag 36
        return Parser().parsestr(message)

    @staticmethod
    def ipaddress(buf):
        # Semantic tag 260
        if not isinstance(buf, bytes) or len(buf) not in (4, 6, 16):
            raise CBORDecodeValueError("invalid ipaddress value %r" % buf)
        elif len(buf) in (4, 16):
            return ip_address(buf)
        elif len(buf) == 6:
            # MAC address
            return CBORTag(260, buf)

    @staticmethod
    def ipnetwork(net_map):
        # Semantic tag 261
        if isinstance(net_map, Mapping) and len(net_map) == 1:
            for net in net_map.items():
                try:
                    return ip_network(net, strict=False)
                except (TypeError, ValueError):
                    break
        raise CBORDecodeValueError("invalid ipnetwork value %r" % net_map)
