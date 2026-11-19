import contextlib
import hashlib
import io
import json
import subprocess
import unittest
from unittest.mock import Mock
import widget_switch as w


class WidgetSwitchTests(unittest.TestCase):
    def confirm(self, answer='project-clear send', error=None):
        run = Mock()
        evidence = {'id': 'selected-uuid', 'title': 'Vitals restart'}
        with contextlib.redirect_stdout(io.StringIO()) as output, \
             unittest.mock.patch.object(output, 'isatty', return_value=True), \
             unittest.mock.patch.object(w.sys.stdin, 'isatty', return_value=True), \
             unittest.mock.patch.object(w, '_dialog_binary', return_value=None), \
             unittest.mock.patch('builtins.input', return_value=answer, side_effect=error):
            approved = w.confirm({'cwd': '/project'}, evidence, 'Codex', 'exact packet', run=run)
        return approved, run, output.getvalue()

    def test_switch_fallback_requires_explicit_review_after_showing_packet(self):
        approved, run, output = self.confirm()
        self.assertTrue(approved)
        run.assert_not_called()
        self.assertIn('COMPLETE FILTERED RECOVERY PACKET\nexact packet', output)
        self.assertIn(hashlib.sha256(b'exact packet').hexdigest(), output)
        self.assertIn('Hand off to: Codex', output)
        self.assertIn('Conversation: Vitals restart', output)

    def test_native_dialog_short_circuits_osascript(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        evidence = {'id': 'u', 'title': 'T', 'document': {'text': ''}}
        with unittest.mock.patch.object(w, '_dialog_binary', return_value='/bin/echo'), unittest.mock.patch.object(w, '_native_dialog', return_value=True):
            self.assertTrue(w.confirm({}, evidence, 'Cursor', 'pkt', run=run))
            run.assert_not_called()

    def test_dialog_requires_explicit_approval_even_when_cancel_exits_zero(self):
        for result, expected in [((0, 'cancel'), False), ((0, ''), None), ((0, 'ok'), None), ((0, 'reviewed'), True), ((1, 'reviewed'), None)]:
            with self.subTest(result=result), unittest.mock.patch.object(w, '_native_dialog_run', return_value=result):
                self.assertIs(w._native_dialog({'kind': 'confirm'}), expected)

    def test_headless_old_dialog_cannot_approve_unseen_packet(self):
        run = Mock()
        with unittest.mock.patch.object(w.sys.stdout, 'isatty', return_value=False), \
             unittest.mock.patch.object(w, '_native_dialog_run', return_value=(0, 'ok')), \
             unittest.mock.patch.object(w, 'handoff_error') as error:
            self.assertFalse(w.confirm({}, {}, 'Codex', 'exact packet', run=run))
        run.assert_not_called()
        error.assert_called_once()

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
        self.assertEqual(captured['packet'], 'packet-bytes')
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
        for answer in ('', 'send', 'project-clear', 'project-clear send extra'):
            with self.subTest(answer=answer):
                self.assertFalse(self.confirm(answer)[0])
        for error in (EOFError(), KeyboardInterrupt()):
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