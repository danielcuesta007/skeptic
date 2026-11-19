import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import switcher
import widget_switch


@unittest.skipUnless(sys.platform == "darwin", "Requires macOS Terminal integration tools")
class HotkeyLaunchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='skeptic launch ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.provider = {'id': 'codex', 'label': 'Codex', 'executable': '/bin/echo', 'local': False}
        home = patch.object(Path, 'home', return_value=self.root)
        home.start()
        self.addCleanup(home.stop)

    def launch(self, packet, provider=None):
        with patch.object(switcher.subprocess, 'run') as terminal:
            _, finalize = switcher.spawn_provider_terminal(provider or self.provider, self.root, packet)
        finalize()
        return terminal.call_args.args[0]

    def test_delayed_tab_launches_keep_their_own_context(self):
        first = self.launch("first 'packet'\n$(echo wrong)")
        second = self.launch('second packet')
        self.assertNotEqual(first[-1], second[-1])
        for argv, packet in ((second, 'second packet'), (first, "first 'packet'\n$(echo wrong)")):
            script, launcher = argv[2:]
            subprocess.run(['/usr/bin/osacompile', '-o', str(self.root / 'launch.scpt'), '-e', script], check=True)
            self.assertEqual(Path(launcher).stat().st_mode & 0o777, 0o600)
            result = subprocess.run(['/bin/zsh', launcher], capture_output=True, text=True, check=True)
            self.assertIn('-- ' + packet + '\n', result.stdout)
            self.assertFalse(Path(launcher).exists())

    def test_terminal_failure_is_reported_and_removes_staged_files(self):
        provider = dict(self.provider, id='hermes')
        with patch.object(switcher.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'osascript')):
            with self.assertRaisesRegex(switcher.host.Denied, 'Could not open Terminal'):
                switcher.spawn_provider_terminal(provider, self.root, 'packet', scratch=self.root)
        self.assertEqual(list(self.root.rglob('*.command')), [])
        self.assertEqual(list(self.root.glob('hermes-*.md')), [])

    def test_hermes_can_read_delayed_query_and_removes_it_after_exit(self):
        engine = self.root / 'fake hermes'
        engine.write_text('#!/bin/sh\n/bin/cat "$5"\n')
        engine.chmod(0o700)
        argv = self.launch('hermes context', dict(self.provider, id='hermes', executable=str(engine)))
        result = subprocess.run(['/bin/zsh', argv[-1]], capture_output=True, text=True, check=True)
        self.assertIn('hermes context', result.stdout)
        self.assertEqual(list(self.root.rglob('hermes-*.md')), [])


class HotkeySessionPickerTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'SKEPTIC_HOTKEY': '1', 'SKEPTIC_HINT_TTY': 'ttys009'})
        environment.start()
        self.addCleanup(environment.stop)
        for stream in (switcher.sys.stdin, switcher.sys.stdout):
            terminal = patch.object(stream, 'isatty', return_value=False)
            terminal.start()
            self.addCleanup(terminal.stop)

    def test_shell_tab_can_continue_with_no_discovered_agents(self):
        row = {'tty': 'ttys009', 'continue_command': ['skeptic', 'continue', '--with', 'codex']}
        with patch('live_sessions.handoff_row_for_tty', return_value=row), \
             patch('widget_switch.pick_engine', return_value='codex'), \
             patch('widget_switch.confirm_active_session', return_value=True):
            commands = []
            self.assertEqual(switcher.switch_open_session(rows=[], run=lambda argv: commands.append(argv) or 0), 0)
        self.assertEqual(commands, [['continue', '--with', 'codex', '--widget-switch']])

    def test_headless_picker_preserves_explicit_selection_and_shows_blocker(self):
        rows = [
            {'tty': 'ttys009', 'label': 'Same label', 'project': 'demo', 'agent': 'Codex', 'next_step': 'Wait for this turn'},
            {'tty': 'ttys009', 'label': 'Same label', 'project': 'demo', 'agent': 'Codex',
             'continue_command': ['skeptic', 'continue', '--with', 'codex']},
        ]
        with patch('live_sessions.handoff_row_for_tty') as infer, \
             patch('widget_switch.pick_engine_osascript', return_value=0) as picker, \
             patch('widget_switch.handoff_error') as error:
            self.assertEqual(switcher.switch_open_session(rows=rows), 2)
        infer.assert_not_called()
        error.assert_called_once_with('Handoff paused: Wait for this turn')
        self.assertEqual(len(set(picker.call_args.args[1])), 2)

    def test_native_picker_distinguishes_os_error_from_cancel(self):
        def invoke(exit_code):
            result = subprocess.CompletedProcess([], exit_code, '', '')
            return widget_switch.pick_engine_osascript([0], ['Session'], run=lambda *args, **kwargs: result)

        self.assertIsNone(invoke(1))
        self.assertIs(invoke(0), False)

    def test_error_dialog_passes_message_as_an_argument(self):
        message = 'Could not read “this tab’s” context.\nTry again.'
        with patch('widget_switch._native_dialog', return_value=None), patch('widget_switch.subprocess.run') as run:
            widget_switch.handoff_error(message)
        command = run.call_args.args[0]
        self.assertEqual(command[-2], message)
        self.assertNotIn(message, command[-3])
        self.assertTrue(run.call_args.kwargs['check'])

    def test_removed_working_directory_stops_launch_and_shows_error(self):
        row = {'tty': 'ttys009', 'continue_cwd': '/removed',
               'continue_command': ['skeptic', 'continue', '--with', 'codex']}
        with patch('live_sessions.handoff_row_for_tty', return_value=row), \
             patch('widget_switch.pick_engine', return_value='codex'), \
             patch('widget_switch.confirm_active_session', return_value=True), \
             patch.object(os, 'chdir', side_effect=FileNotFoundError), \
             patch('widget_switch.handoff_error') as error:
            self.assertEqual(switcher.switch_open_session(rows=[], run=lambda argv: self.fail('Provider launched')), 2)
        error.assert_called_once_with('The selected session’s working directory is no longer accessible.')


class HotkeyInstallTests(unittest.TestCase):
    def test_upgrade_replaces_known_launcher_and_preserves_custom_picker(self):
        import contextlib
        import hashlib
        import io

        import install

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            bindir = root / '.local/bin'
            install.safe_parent(bindir)
            install.install_hotkey_widget(root, bindir)
            switch = bindir / 'skeptic-switch'
            installed = switch.read_text()
            old = '# Known previous shortcut'
            switch.write_text(old)
            picker = root / '.skeptic-widget/skeptic-picker.command'
            picker.write_text('# Custom picker')
            with patch.object(install, 'LEGACY_HOTKEY', {hashlib.sha256(old.encode()).hexdigest()}), \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                install.install_hotkey_widget(root, bindir, upgrade=True)
            self.assertEqual(switch.read_text(), installed)
            self.assertEqual(picker.read_text(), '# Custom picker')
            self.assertIn('Existing file differs; preserved', stderr.getvalue())


class HotkeyWriterTests(unittest.TestCase):
    def test_destination_writer_holds_reservation_through_provider_call(self):
        import terminal_writer

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve() / 'state'
            observer = switcher.State(directory)
            self.addCleanup(observer.close)

            def run(command):
                self.assertEqual(command, ['/bin/true'])
                with self.assertRaises(switcher.host.Denied):
                    with switcher.writer_reservation(observer):
                        self.fail('Writer reservation was released during provider execution')
                return 0

            with patch('terminal_writer.subprocess.call', side_effect=run):
                self.assertEqual(terminal_writer.main(str(directory), ['/bin/true']), 0)
            with switcher.writer_reservation(observer):
                pass


    def test_ctrl_c_reaches_provider_without_releasing_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / 'state'
            observer = switcher.State(directory)
            try:
                code = (
                    "import signal, time; from pathlib import Path\n"
                    "signal.signal(signal.SIGINT, lambda *_: Path('interrupted').touch())\n"
                    "Path('started').touch()\n"
                    "while not Path('stop').exists(): time.sleep(.01)\n"
                )
                argv = [sys.executable, '-B', str(Path(switcher.__file__).with_name('terminal_writer.py')),
                        str(directory), sys.executable, '-c', code]
                with subprocess.Popen(argv, cwd=root, start_new_session=True) as writer:
                    def await_file(path):
                        deadline = time.monotonic() + 5
                        while not path.exists() and writer.poll() is None and time.monotonic() < deadline:
                            time.sleep(.01)
                        self.assertTrue(path.exists())

                    try:
                        await_file(root / 'started')
                        os.killpg(writer.pid, signal.SIGINT)
                        await_file(root / 'interrupted')
                        with self.assertRaises(switcher.host.Denied):
                            with switcher.writer_reservation(observer):
                                self.fail('Provider is still running')
                    finally:
                        (root / 'stop').touch()
                        try:
                            writer.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(writer.pid, signal.SIGKILL)
                            raise
                    self.assertEqual(writer.returncode, 0)
            finally:
                observer.close()
