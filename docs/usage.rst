Basic usage
===========

Serializing and deserializing with cbor2 is pretty straightforward::

    from cbor2 import dumps, loads

    # Serialize an object as a bytestring
    data = dumps(['hello', 'world'])

    # Deserialize a bytestring
    obj = loads(data)

    # Efficiently deserialize from a file
    with open('input.cbor', 'rb') as fp:
        obj = load(fp)

    # Efficiently serialize an object to a file
    with open('output.cbor', 'wb') as fp:
        dump(obj, fp)

Some data types, however, require extra considerations, as detailed below.

Dealing with Streams
--------------------

There are 3 distinct ways of dealing with streaming data to and from files:

Indefinite length Arrays
++++++++++++++++++++++++

with :class:`~cbor2.extra.streams.CBORArrayStreamWriter`::

    from cbor2.extra.streams import CBORArrayStream

    with open('out.cbor', 'wb') as fp:
       with CBORArrayStreamWriter(fp) as writer:
           for item in iterator:
               writer.write(item)

These files can be read with a single call to ``load`` since they contain a delimited indefinite-length array.

Indefinite length Maps
++++++++++++++++++++++

with :class:`~cbor2.extra.streams.CBORMapStreamWriter`::


   from cbor2.extra.streams import CBORMapStream

   with open('out.cbor', 'wb') as fp:
       with CBORMapStreamWriter(fp) as writer:
           for key, item in iterator:
               writer.write(key, item)

These files can also be read with a single call to ``load``.

CBOR Sequences (RFC8949 section 5.1)
++++++++++++++++++++++++++++++++++++

with :class:`cbor2.extra.streams.CBORSequenceWriter`::

    with open("out.cbor", "wb") as f:
        writer = CBORSequenceWriter(f)
        writer.writeheader(protocol_tag=0xDEADBEEF)
        for n in (x ** 2 / x ** 3 for x in range(1, 20)):
            writer.write({"mynum": n})

The ``writeheader`` method writes a leading data item to the file marking it as a CBOR sequence
(tag 55800), followed by a protocol identifier tag between ``0x01000000`` and ``0xFFFFFFFF`` and then the
letters "BOR" as the tagged data item. This gives a fixed 12 bytes at the beginning of the file that
can be used to identify the format.

To read a CBOR Sequence you can use class:`cbor2.extra.streams.CBORSequenceReader`::

    with open("out.cbor", "rb") as f:
        reader = CBORSequenceReader(f, header_tags=(55800, 0xDEADBEEF))
        for item in reader.readitems():
            print(item)

This will try to match the header tags and raise an error if they don't match. If there is no header,
you can pass an empty tuple as the ``header_tags`` argument.


Date/time handling
------------------

The CBOR specification does not support naïve datetimes (that is, datetimes where ``tzinfo`` is
missing). When the encoder encounters such a datetime, it needs to know which timezone it belongs
to. To this end, you can specify a default timezone by passing a :class:`~datetime.tzinfo` instance
to :func:`~cbor2.encoder.dump`/:func:`~cbor2.encoder.dumps` call as the ``timezone`` argument.
Decoded datetimes are always timezone aware.

By default, datetimes are serialized in a manner that retains their timezone offsets. You can
optimize the data stream size by passing ``datetime_as_timestamp=False`` to
:func:`~cbor2.encoder.dump`/:func:`~cbor2.encoder.dumps`, but this causes the timezone offset
information to be lost.

In versions prior to 4.2 the encoder would convert a ``datetime.date`` object into a
``datetime.datetime`` prior to writing. This can cause confusion on decoding so this has been
disabled by default in the next version. The behaviour can be re-enabled as follows::

    from cbor2 import dumps
    from datetime import date, timezone

    # Serialize dates as datetimes
    encoded = dumps(date(2019, 10, 28), timezone=timezone.utc, date_as_datetime=True)

A default timezone offset must be provided also.

Cyclic (recursive) data structures
----------------------------------

If the encoder encounters a shareable object (ie. list or dict) that it has seen before, it will
by default raise :exc:`~cbor2.encoder.CBOREncodeError` indicating that a cyclic reference has been
detected and value sharing was not enabled. CBOR has, however, an extension specification that
allows the encoder to reference a previously encoded value without processing it again. This makes
it possible to serialize such cyclic references, but value sharing has to be enabled by passing
``value_sharing=True`` to :func:`~cbor2.encoder.dump`/:func:`~cbor2.encoder.dumps`.

.. warning:: Support for value sharing is rare in other CBOR implementations, so think carefully
    whether you want to enable it. It also causes some line overhead, as all potentially shareable
    values must be tagged as such.

String references
-----------------

When ``string_referencing=True`` is passed to
:func:`~cbor2.encoder.dump`/:func:`~cbor2.encoder.dumps`, if the encoder would encode a string that
it has previously encoded and where a reference would be shorter than the encoded string, it
instead encodes a reference to the nth sufficiently long string already encoded.

.. warning:: Support for string referencing is rare in other CBOR implementations, so think carefully
    whether you want to enable it.

Tag support
-----------

In addition to all standard CBOR tags, this library supports many extended tags:

===== ======================================== ====================================================
Tag   Semantics                                Python type(s)
===== ======================================== ====================================================
0     Standard date/time string                datetime.date / datetime.datetime
1     Epoch-based date/time                    datetime.date / datetime.datetime
2     Positive bignum                          int / long
3     Negative bignum                          int / long
4     Decimal fraction                         decimal.Decimal
5     Bigfloat                                 decimal.Decimal
25    String reference                         str / bytes
28    Mark shared value                        N/A
29    Reference shared value                   N/A
30    Rational number                          fractions.Fraction
35    Regular expression                       ``_sre.SRE_Pattern`` (result of ``re.compile(...)``)
36    MIME message                             email.message.Message
37    Binary UUID                              uuid.UUID
256   String reference namespace               N/A
258   Set of unique items                      set
260   Network address                          :class:`ipaddress.IPv4Address` (or IPv6)
261   Network prefix                           :class:`ipaddress.IPv4Network` (or IPv6)
55799 Self-Described CBOR                      object
===== ======================================== ====================================================

Arbitary tags can be represented with the :class:`~cbor2.types.CBORTag` class.

If you want to write a file that is detected as CBOR by the Unix ``file`` utility, wrap your data in
a ``~cbor2.types.CBORTag`` object like so::

    from cbor2 import dump, CBORTag

    with open('output.cbor', 'wb') as fp:
        dump(CBORTag(55799, obj), fp)

This will be ignored on decode and the original data content will be returned.

Use Cases
---------

Here are some things that the cbor2 library could be (and in some cases, is being) used for:

- Experimenting with network protocols based on CBOR encoding
- Designing new data storage formats
- Submitting binary documents to ElasticSearch without base64 encoding overhead
- Storing and validating file metadata in a secure backup system
- RPC which supports Decimals with low overhead
