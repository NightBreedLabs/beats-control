import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('eqconf', pathlib.Path(__file__).resolve().parents[1] / 'beatscontrol/eqconf.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


BRIGHT_SUM = 75.1
BRIGHT_TOP = (1.6, 1.8, 5.9, 8.0, 11, 13, 14, 6)


class EqConf(unittest.TestCase):
    def test_base_curve_plays_at_full_level(self):
        self.assertEqual(e.preset_level(e.MINE), 0.0)
        self.assertLess(e.preset_level(e.PRESETS['Deep Bass']), 0.0)

    def test_moving_a_band_changes_nothing_else(self):
        gains = list(e.MINE)
        moved = list(gains)
        moved[1] = 12.0
        before = e.render(gains, -1.5, 'X').splitlines()
        after = e.render(moved, -1.5, 'X').splitlines()
        changed = [b for a, b in zip(before, after) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertIn('name = eq2 ', changed[0])

    def test_matches_easyeffects_layout_and_curve(self):
        self.assertEqual(e.BANDS, 32)
        self.assertEqual(e.Q, 4.36)
        self.assertEqual(e.MINE[30], 12.0)
        self.assertEqual(e.MINE[10], 0.0)
        self.assertAlmostEqual(e.response(e.MINE, 14552.2), 12.0, delta=2.5)

    def test_gains_are_clamped_and_counted(self):
        self.assertEqual(e.clamp([99.0] + [-99.0] * 31)[:2], [12.0, -12.0])
        with self.assertRaises(ValueError):
            e.clamp([1.0])

    def test_render_has_all_bands_and_target(self):
        text = e.render(list(e.PRESETS['Deep Bass']), -2.0, 'bluez_output.X.1')
        self.assertIn('target.object = "bluez_output.X.1"', text)
        self.assertEqual(text.count('type = builtin'), 34)
        self.assertIn('capture.volumes = [ { control = "vol:Mult"', text)
        self.assertNotIn('"vol:Out"', text)
        self.assertEqual(text.count('input ='), 32)
        self.assertEqual(text.count('bq_peaking'), 32)
        self.assertIn('node.dont-move = true', text)
        self.assertIn('node.passive = true', text)

    def test_presets_are_gentle_changes_from_base_curve(self):
        base = e.MINE
        for name, gains in e.PRESETS.items():
            self.assertEqual(len(e.clamp(gains)), 32)
            if name != 'Flat':
                self.assertLessEqual(max(abs(a - b) for a, b in zip(gains, base)), 4.0, name)

    def test_preset_list(self):
        self.assertNotIn('My EasyEffects', e.PRESETS)
        self.assertIn('Treble Boost', e.PRESETS)

    def test_bright_is_frozen(self):
        self.assertEqual(sum(e.PRESETS['Bright']), BRIGHT_SUM)
        self.assertEqual(e.PRESETS['Bright'][24:32], BRIGHT_TOP)

    def test_live_props_cover_every_gain(self):
        text = e.props([1.0] * 32, -3.0)
        self.assertIn('"eq32:Gain" 1.00', text)
        self.assertIn('"pre:Gain" -3.00', text)


if __name__ == '__main__':
    unittest.main()
