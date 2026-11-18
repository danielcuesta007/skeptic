import hashlib
import json
import subprocess
import unittest
from unittest.mock import Mock
import widget_switch as w


class WidgetSwitchTests(unittest.TestCase):
    def confirm(self, result=None, error=None, native=None):
        run = Mock(side_effect=error, return_value=result or subprocess.CompletedProcess([], 0, w.APPROVE_BUTTON + '\n', ''))
        evidence = {'id': 'selected-uuid', 'title': 'Vitals restart', 'document': {'text': 'Latest recorded human request (completion unverified):\nwhy does cadence ask twice?\n' + 'x' * 400 + '\n[message m1; user]\nrest'}}
        with unittest.mock.patch.object(w, '_dialog_binary', return_value=None if native is False else None):
            approved = w.confirm({'cwd': '/project/" & do shell script "bad'}, evidence, 'Codex', 'exact packet', run=run)
        return approved, run

    def test_switch_approves_fallback_osascript(self):
        approved, run = self.confirm()
        self.assertTrue(approved)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ['/usr/bin/osascript', '-e', w.SCRIPT])
        digest = hashlib.sha256(b'exact packet').hexdigest()
        self.assertIn(digest[:16], argv[3])
        self.assertIn('SKEPTIC · Session Handoff', argv[3])
        self.assertIn('Hand off to: Codex', argv[3])
        self.assertIn('Conversation: Vitals restart', argv[3])
        self.assertIn('Last request: why does cadence ask twice?', argv[3])

    def test_native_dialog_short_circuits_osascript(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        evidence = {'id': 'u', 'title': 'T', 'document': {'text': ''}}
        with unittest.mock.patch.object(w, '_dialog_binary', return_value='/bin/echo'), unittest.mock.patch.object(w, '_native_dialog', return_value=True):
            self.assertTrue(w.confirm({}, evidence, 'Cursor', 'pkt', run=run))
            run.assert_not_called()

    def test_native_payload_fields(self):
        captured = {}
        def fake_native(payload, run=None):
            captured.update(payload)
            return True
        evidence = {'title': 'Widget spacing', 'document': {'text': 'Latest recorded human request (completion unverified):\nfix tiles\n'}}
        with unittest.mock.patch.object(w, '_native_dialog', side_effect=fake_native):
            self.assertTrue(w.confirm({'cwd': '/Users/x/proj'}, evidence, 'Codex', 'packet-bytes', run=Mock()))
        self.assertEqual(captured['kind'], 'confirm')
        self.assertEqual(captured['provider'], 'Codex')
        self.assertIn('fix tiles', captured['lastRequest'])

    def test_active_session_skips_when_idle_tab(self):
        row = {'activity': 'idle', 'source': 'terminal', 'agent': 'Terminal tab'}
        self.assertTrue(w.confirm_active_session(row, 'ttys010', '', run=Mock()))

    def test_active_session_native_payload(self):
        captured = {}
        def fake_native(payload, run=None):
            captured.update(payload)
            return False
        row = {'activity': 'working', 'source': 'codex', 'label': 'Addisuna', 'tty': 'ttys001'}
        with unittest.mock.patch.object(w, '_native_dialog', side_effect=fake_native):
            self.assertFalse(w.confirm_active_session(row, 'ttys001', 'Addisuna', run=Mock()))
        self.assertEqual(captured['kind'], 'active_session')
        self.assertEqual(captured['provider'], 'Codex')

    def test_engine_picker_native_failure_skips_osascript(self):
        row = {'label': 'Work', 'tty': 'ttys003'}
        osa = unittest.mock.Mock(return_value='codex')
        with unittest.mock.patch.object(w, 'pick_engine_osascript', osa), unittest.mock.patch.object(w, '_native_dialog_run', return_value=(2, '')):
            self.assertIsNone(w.pick_engine(['codex'], ['Codex'], row))
        osa.assert_not_called()

    def test_engine_picker_native_returns_choice(self):
        row = {'label': 'Spacing', 'tty': 'ttys014', 'tab_title': 'Work'}
        with unittest.mock.patch.object(w, '_native_dialog_run', return_value=(0, 'hermes')):
            self.assertEqual(w.pick_engine(['codex', 'hermes'], ['Codex', 'Hermes'], row, 'ttys014', 'Work'), 'hermes')
        with unittest.mock.patch.object(w, '_native_dialog_run', return_value=(1, 'cancel')):
            self.assertFalse(w.pick_engine(['codex'], ['Codex'], row))
        with unittest.mock.patch.object(w, '_native_dialog_run', return_value=(0, '')), unittest.mock.patch.object(w, 'pick_engine_osascript', return_value='codex'):
            self.assertEqual(w.pick_engine(['codex'], ['Codex — room'], row), 'codex')

    def test_engine_picker_payload_shape(self):
        captured = {}
        def fake_run(payload, run=None):
            captured.update(payload)
            return 0, 'codex'
        row = {'label': 'Atlas', 'tty': 'ttys002'}
        with unittest.mock.patch.object(w, '_native_dialog_run', side_effect=lambda p, run=None: (captured.update(p) or (0, 'codex'))):
            w.pick_engine(['codex', 'claude'], ['A', 'B'], row, 'ttys002', 'Atlas')
        self.assertEqual(captured['kind'], 'engine_picker')
        self.assertEqual(len(captured['engines']), 2)
        self.assertEqual(captured['engines'][0]['id'], 'codex')

    def test_close_source_native_payload(self):
        captured = {}
        def fake_native(payload, run=None):
            captured.update(payload)
            return False
        with unittest.mock.patch.object(w, '_native_dialog', side_effect=fake_native):
            self.assertFalse(w.confirm_close_source('Codex', 'Vitals', 'ttys003', 'Spacing fixes', run=Mock()))
        self.assertEqual(captured['kind'], 'close_source')
        self.assertEqual(captured['provider'], 'Codex')
        self.assertEqual(captured['tty'], 'ttys003')
        self.assertEqual(captured['tabTitle'], 'Spacing fixes')

    def test_cancel_errors_and_unexpected_output_never_approve(self):
        for code, output in ((1, w.APPROVE_BUTTON), (0, w.CANCEL_BUTTON), (0, ''), (0, w.APPROVE_BUTTON + ' extra')):
            with self.subTest(code=code, output=output):
                self.assertFalse(self.confirm(subprocess.CompletedProcess([], code, output, ''))[0])
        for error in (OSError('unavailable'), subprocess.TimeoutExpired('osascript', 300)):
            self.assertFalse(self.confirm(error=error)[0])


class ExistingWindowTests(unittest.TestCase):
    def test_show_only_the_unique_lock_holders_terminal(self):
        run = Mock(side_effect=[subprocess.CompletedProcess([], 0, '123\n', ''), subprocess.CompletedProcess([], 0, 'p123\nn/dev/ttys007\n', ''), subprocess.CompletedProcess([], 0, 'ok\n', '')])
        with unittest.mock.patch.object(w, '_native_dialog', return_value=True):
            self.assertTrue(w.show_existing('/state/lock', run=run))
        self.assertEqual(run.call_count, 3)

    def test_ambiguous_holder_does_not_guess_window(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, '123\n456\n', ''))
        self.assertFalse(w.show_existing('/state/lock', run=run))
        self.assertEqual(run.call_count, 1)