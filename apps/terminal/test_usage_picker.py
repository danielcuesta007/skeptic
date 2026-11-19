import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import usage_picker as u


class UsagePickerTests(unittest.TestCase):
    def test_line_from_provider_windows(self):
        providers = {
            'codex': {
                'id': 'codex',
                'windows': [{'label': 'Weekly', 'used_pct': 88.0, 'resets_at': 1795026000}],
            }
        }
        line = u._line('codex', providers)
        self.assertIn('Codex', line)
        self.assertIn('left', line)
        self.assertIn('weekly', line)
        self.assertIn('resets', line)
        self.assertNotIn('frees', line)

    def test_zero_left_is_at_cap_not_almost_full(self):
        providers = {
            'claude': {
                'id': 'claude',
                'windows': [
                    {'label': '5-hour', 'used_pct': 40.0, 'resets_at': 1795000000},
                    {'label': 'Weekly', 'used_pct': 100.0, 'resets_at': 1795026000},
                ],
            }
        }
        line = u._line('claude', providers)
        self.assertIn('at cap', line)
        self.assertIn('5-hour rolling', line)
        self.assertIn('weekly', line)
        self.assertNotIn('almost full', line.lower())
        self.assertNotIn('frees', line)

    def test_missing_shows_hint(self):
        self.assertIn('no usage info', u._line('cursor', {}))

    def test_hermes_shows_default_model(self):
        with patch.object(u, '_hermes_handoff_model', return_value='hermes-local-v2'):
            line = u._line('hermes', {})
        self.assertIn('Hermes (hermes-local-v2)', line)
        self.assertIn('runs on your Mac', line)