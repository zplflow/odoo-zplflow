# -*- coding: utf-8 -*-
"""Binary IPP (RFC 8010) request encoder used to talk to Zebra Link-OS printers.

The Internet Printing Protocol encapsulates its operations in a binary
attribute stream.  This module implements the small subset required to send a
``Print-Job`` operation carrying a raw ZPL document to a Zebra printer that
exposes an IPP endpoint (``ipps://host:631/ipp/print``).
"""

import struct

__all__ = ['IPPPayloadBuilder']


class IPPPayloadBuilder:
    """Encoder for binary IPP (RFC 8010) Print-Job requests targeting Zebra Link-OS."""

    # Delimiter tags (RFC 8010 section 3.5.1)
    TAG_OPERATION_ATTRIBUTES = 0x01
    TAG_END_OF_ATTRIBUTES = 0x03

    # Value tags (RFC 8010 section 3.5.2)
    TAG_CHARSET = 0x47
    TAG_NATURAL_LANGUAGE = 0x48
    TAG_URI = 0x45
    TAG_MIME_MEDIA_TYPE = 0x49
    TAG_NAME_WITHOUT_LANGUAGE = 0x42

    # IPP protocol version 2.0 and operation id of Print-Job.
    IPP_VERSION = 0x0200
    OPERATION_PRINT_JOB = 0x0002
    REQUEST_ID = 1

    @classmethod
    def _encode_attribute(cls, tag: int, name: str, value: str) -> bytes:
        """Encode a single ``attribute-with-1-value`` structure."""
        name_bytes = name.encode('utf-8')
        val_bytes = value.encode('utf-8')
        return (
            struct.pack('>B', tag) +
            struct.pack('>H', len(name_bytes)) + name_bytes +
            struct.pack('>H', len(val_bytes)) + val_bytes
        )

    @classmethod
    def build_print_job(cls, printer_uri: str, zpl_data: bytes, job_name: str = "zplflow-job") -> bytes:
        """Encodes an IPP 2.0 Print-Job request body followed by raw ZPL bytes."""
        header = struct.pack(
            '>HHI',
            cls.IPP_VERSION,
            cls.OPERATION_PRINT_JOB,
            cls.REQUEST_ID,
        )
        body = bytearray()
        body.append(cls.TAG_OPERATION_ATTRIBUTES)
        body.extend(cls._encode_attribute(cls.TAG_CHARSET, 'attributes-charset', 'utf-8'))
        body.extend(cls._encode_attribute(cls.TAG_NATURAL_LANGUAGE, 'attributes-natural-language', 'en'))
        body.extend(cls._encode_attribute(cls.TAG_URI, 'printer-uri', printer_uri))
        body.extend(cls._encode_attribute(cls.TAG_NAME_WITHOUT_LANGUAGE, 'job-name', job_name))
        body.extend(cls._encode_attribute(cls.TAG_MIME_MEDIA_TYPE, 'document-format', 'application/vnd.zebra'))
        body.append(cls.TAG_END_OF_ATTRIBUTES)
        return bytes(header) + bytes(body) + zpl_data
