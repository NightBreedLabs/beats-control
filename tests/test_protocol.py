import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.modules.setdefault('gi', None)
import importlib.util
spec = importlib.util.spec_from_file_location('protocol', pathlib.Path(__file__).resolve().parents[1] / 'beatscontrol/protocol.py')
p = importlib.util.module_from_spec(spec)
sys.modules['protocol'] = p
spec.loader.exec_module(p)


class Protocol(unittest.TestCase):
    def test_real_frames_from_studio3(self):
        self.assertEqual(p.parse(bytes.fromhex('04 00 04 00 09 00 0d 02 00 00 00')), p.AncState(True))
        self.assertEqual(p.parse(bytes.fromhex('04 00 04 00 09 00 0d 01 00 00 00')), p.AncState(False))
        self.assertEqual(p.parse(bytes.fromhex('04 00 04 00 04 00 01 01 01 61 02 01')), p.Battery(97, False))
        self.assertIsInstance(p.parse(bytes.fromhex('01 00 04 00 00 00 01 00 00 00 0b 00 02 00 00 00 00 00')), p.HandshakeAck)

    def test_commands_match_tested_bytes(self):
        self.assertEqual(p.set_anc(True).hex(' '), '04 00 04 00 09 00 0d 02 00 00 00')
        self.assertEqual(p.set_anc(False).hex(' '), '04 00 04 00 09 00 0d 01 00 00 00')

    def test_ignores_unknown_and_bad_frames(self):
        for frame in ('', '04 00', '04 00 04 00 24 00 01 00 01 00 00', '04 00 04 00 06 00 00 03', '04 00 04 00 09 00 0d 03 00 00 00', '04 00 04 00 04 00 01 01 01 ff 02 01', '04 00 04 00 04 00 01 01'):
            self.assertIsNone(p.parse(bytes.fromhex(frame)), frame)


if __name__ == '__main__':
    unittest.main()
