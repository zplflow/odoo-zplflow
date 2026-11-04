import unittest
import struct
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from odoo_zplflow_bridge.models.ipp_builder import IPPPayloadBuilder


class TestIPPPayloadBuilder(unittest.TestCase):
    def test_build_print_job(self):
        zpl = b"^XA^FO50,50^FDTest^FS^XZ"
        uri = "ipps://192.168.1.100:631/ipp/print"
        payload = IPPPayloadBuilder.build_print_job(uri, zpl, job_name="test-label")

        # Verify header (8 bytes): IPP 2.0 (0x0200), Operation Print-Job (0x0002), Request-ID 1
        version, op_id, req_id = struct.unpack('>HHI', payload[:8])
        self.assertEqual(version, 0x0200)
        self.assertEqual(op_id, 0x0002)
        self.assertEqual(req_id, 1)

        # Verify operation attributes tag
        self.assertEqual(payload[8], 0x01)

        # Verify payload ends with exact ZPL bytes
        self.assertTrue(payload.endswith(zpl))

        # Verify attributes are packed
        self.assertIn(b"application/vnd.zebra", payload)
        self.assertIn(b"printer-uri", payload)

    def test_encode_attribute_structure(self):
        encoded = IPPPayloadBuilder._encode_attribute(
            IPPPayloadBuilder.TAG_URI, 'printer-uri', 'ipps://host/ipp/print'
        )
        self.assertEqual(encoded[0], 0x45)
        name_len = struct.unpack('>H', encoded[1:3])[0]
        self.assertEqual(name_len, len(b'printer-uri'))
        self.assertEqual(encoded[3:3 + name_len], b'printer-uri')
        value_len = struct.unpack('>H', encoded[3 + name_len:5 + name_len])[0]
        self.assertEqual(encoded[5 + name_len:], b'ipps://host/ipp/print')
        self.assertEqual(value_len, len(b'ipps://host/ipp/print'))

    def test_end_of_attributes_precedes_document(self):
        zpl = b"^XA^XZ"
        payload = IPPPayloadBuilder.build_print_job("ipps://host/ipp/print", zpl)
        self.assertEqual(payload[-len(zpl) - 1], IPPPayloadBuilder.TAG_END_OF_ATTRIBUTES)
        # Default job name is used when none is supplied.
        self.assertIn(b'zplflow-job', payload)
        # Charset and language attributes are always advertised.
        self.assertIn(b'attributes-charset', payload)
        self.assertIn(b'attributes-natural-language', payload)


if __name__ == '__main__':
    unittest.main()
