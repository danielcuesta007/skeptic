"""Native Skeptic-branded handoff confirmation (AppKit) with AppleScript fallback."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

DIALOG_TITLE = 'Skeptic · Session Handoff'
APPROVE_BUTTON = 'Hand off'
CANCEL_BUTTON = 'Cancel'
CLOSE_APPROVE_BUTTON = 'Close stuck tab'
CLOSE_KEEP_BUTTON = 'Keep tab'
ACTIVE_APPROVE_BUTTON = 'Switch agent'
ACTIVE_KEEP_BUTTON = 'Keep working'

SCRIPT = rf'''on run argv
    set messageText to item 1 of argv
    set response to display dialog messageText with title "{DIALOG_TITLE}" buttons {{"{CANCEL_BUTTON}", "{APPROVE_BUTTON}"}} default button "{APPROVE_BUTTON}" cancel button "{CANCEL_BUTTON}" with icon note
    return button returned of response
end run'''

EXISTING_SCRIPT = rf'''on run argv
    set targetTTY to item 1 of argv
    display dialog "SKEPTIC · Session Handoff

Another handoff window is still open. Finish or cancel it before starting a new one." with title "{DIALOG_TITLE}" buttons {{"{CANCEL_BUTTON}", "Show window"}} default button "Show window" cancel button "{CANCEL_BUTTON}" with icon caution
    tell application "Terminal"
        repeat with win in windows
            repeat with tabItem in tabs of win
                if tty of tabItem is targetTTY then
                    set selected tab of win to tabItem
                    set index of win to 1
                    activate
                    return
                end if
            end repeat
        end repeat
    end tell
end run'''


def _dialog_binary():
    env = os.environ.get('SKEPTIC_HANDOFF_DIALOG', '').strip()
    if env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve().parent
    for candidate in (here / 'bin' / 'skeptic-handoff-dialog',
                      Path.home() / '.local' / 'bin' / 'skeptic-handoff-dialog'):
        if candidate.is_file():
            return candidate
    return None


def _native_dialog_run(payload, run=None):
    """Run the AppKit sheet. Returns (exit_code, choice_text) or None if the binary is missing."""
    binary = _dialog_binary()
    if not binary:
        return None
    run = run or subprocess.run
    fd, path = tempfile.mkstemp(prefix='skeptic-handoff-', suffix='.json')
    result_fd, result_path = tempfile.mkstemp(prefix='skeptic-handoff-result-')
    os.close(result_fd)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(payload, out, ensure_ascii=False)
            out.write('\n')
        os.chmod(path, 0o600)
        os.chmod(result_path, 0o600)
        try:
            completed = run(
                [str(binary), '--payload', path, '--result', result_path],
                timeout=300,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        choice = ''
        try:
            if os.path.isfile(result_path):
                choice = Path(result_path).read_text(encoding='utf-8').strip()
        except OSError:
            choice = ''
        if completed.returncode not in (0, 1):
            return None
        return completed.returncode, choice
    finally:
        for name in (path, result_path):
            try:
                os.unlink(name)
            except OSError:
                pass


ENGINE_LIST_SCRIPT = r'''on run argv
    set titleText to item 1 of argv
    set promptText to item 2 of argv
    set choiceList to items 3 thru (count of argv) of argv
    set picked to choose from list choiceList with title titleText with prompt promptText default items item 1 of choiceList
    if picked is false then return ""
    return item 1 of picked
end run'''


def pick_engine_osascript(engine_ids, labels, run=None):
    """Standard macOS list — reliable when AppKit sheet cannot run in this context."""
    run = run or subprocess.run
    if not labels:
        return None
    try:
        result = run(
            ['/usr/bin/osascript', '-e', ENGINE_LIST_SCRIPT, DIALOG_TITLE,
             'Choose the engine to continue your work.'] + list(labels),
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return False
    picked = (result.stdout or '').strip()
    if not picked:
        return False
    try:
        index = labels.index(picked)
    except ValueError:
        return None
    return engine_ids[index]


def _native_dialog(payload, run=None):
    ran = _native_dialog_run(payload, run=run)
    if ran is None:
        return None
    return ran[0] == 0


def _handoff_session_name(row, hint_title=''):
    """Human label for the stuck session — not the picker tab title."""
    junk = 'session handoff'
    title = (hint_title or '').strip()
    if title and junk not in title.lower():
        return title[:240]
    for key in ('label', 'project', 'agent'):
        value = str(row.get(key) or '').strip()
        if value and junk not in value.lower():
            return value[:240]
    return 'Open session'


def _stuck_tab_caption(hint_tty, hint_title=''):
    junk = 'session handoff'
    title = (hint_title or '').strip()
    tty = (hint_tty or '').strip()
    if title and junk not in title.lower():
        return ' · '.join(p for p in (tty, title) if p)[:240]
    return tty or '—'


def handoff_error(message, run=None):
    """Branded failure for ⌘⇧S — sheet when possible, otherwise a native alert."""
    run = run or subprocess.run
    body = str(message or 'Handoff could not continue.').strip()[:900]
    payload = {'kind': 'error', 'conversation': body}
    if _native_dialog(payload, run=run) is not None:
        os.environ['SKEPTIC_HANDOFF_ERROR_SHOWN'] = '1'
        return
    script = (
        f'display dialog {json.dumps(body)} with title "{DIALOG_TITLE}" '
        f'buttons {{"OK"}} default button "OK" with icon caution'
    )
    try:
        run(['/usr/bin/osascript', '-e', script], timeout=120)
    except (OSError, subprocess.SubprocessError):
        pass
    os.environ['SKEPTIC_HANDOFF_ERROR_SHOWN'] = '1'


def pick_engine(engine_ids, labels, row, hint_tty='', hint_title='', run=None):
    """Branded native engine list for ⌘⇧S; OS list if AppKit cannot return a choice."""
    run = run or subprocess.run
    engines = [{'id': e, 'label': l} for e, l in zip(engine_ids, labels)]
    payload = {
        'kind': 'engine_picker',
        'conversation': _handoff_session_name(row, hint_title),
        'tty': hint_tty or row.get('tty') or '',
        'tabTitle': _stuck_tab_caption(hint_tty, hint_title),
        'engines': engines,
    }
    ran = _native_dialog_run(payload, run=run)
    choice = None
    if ran is not None:
        code, text = ran
        if code == 1 or text == 'cancel':
            return False
        if code == 0 and text in engine_ids:
            choice = text
    if choice is None:
        choice = pick_engine_osascript(engine_ids, labels, run=run)
    return choice


def confirm(summary, evidence, provider, packet, run=None):
    """The click approves this packet and attests to the original writer check."""
    run = run or subprocess.run
    document = (evidence.get('document') or {}).get('text', '')
    latest = document.split('\n[message ', 1)[0].split(':\n', 1)[-1].strip() if document.startswith('Latest recorded human request') else ''
    latest = ' '.join(latest.split())
    project = str(summary.get('cwd', '') or '')
    short_project = project.replace(str(Path.home()), '~', 1) if project else 'Unknown folder'
    digest = hashlib.sha256(packet.encode()).hexdigest()
    digest_short = digest[:16] + '…' + digest[-8:]
    payload = {
        'kind': 'confirm',
        'provider': str(provider),
        'conversation': str(evidence.get('title') or 'Untitled'),
        'lastRequest': latest[:400] if latest else '',
        'folder': short_project,
        'digest': digest_short,
    }
    approved = _native_dialog(payload, run=run)
    if approved is not None:
        return approved
    lines = [
        'SKEPTIC · Session Handoff',
        'Your work. Your memory. Any AI.',
        '',
        'Hand off to: ' + str(provider),
        'Conversation: ' + str(evidence.get('title') or 'Untitled'),
    ]
    if latest:
        lines.append('Last request: ' + (latest[:200] + '…' if len(latest) > 200 else latest))
    lines.extend([
        'Folder: ' + short_project,
        '',
        'Skeptic sends the filtered packet shown in Terminal to the new engine. '
        'Confirm background tools in the original tab are idle. '
        'After the new engine is running, Skeptic will ask whether to close the stuck tab.',
        '',
        'Packet SHA-256: ' + digest_short,
    ])
    text = '\n'.join(lines)
    try:
        result = run(['/usr/bin/osascript', '-e', SCRIPT, text], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == APPROVE_BUTTON


CLOSE_SCRIPT = rf'''on run argv
    set messageText to item 1 of argv
    set response to display dialog messageText with title "{DIALOG_TITLE}" buttons {{"{CLOSE_KEEP_BUTTON}", "{CLOSE_APPROVE_BUTTON}"}} default button "{CLOSE_APPROVE_BUTTON}" cancel button "{CLOSE_KEEP_BUTTON}" with icon note
    return button returned of response
end run'''


ACTIVE_SCRIPT = rf'''on run argv
    set messageText to item 1 of argv
    set response to display dialog messageText with title "{DIALOG_TITLE}" buttons {{"{ACTIVE_KEEP_BUTTON}", "{ACTIVE_APPROVE_BUTTON}"}} default button "{ACTIVE_KEEP_BUTTON}" cancel button "{ACTIVE_KEEP_BUTTON}" with icon caution
    return button returned of response
end run'''


def confirm_active_session(row, hint_tty='', hint_title='', run=None):
    """Before handoff: this tab's agent looks mid-turn; confirm with quota hint."""
    run = run or subprocess.run
    import live_sessions as live
    if not live.needs_active_handoff_confirm(row, hint_title):
        return True
    name = live.NAMES.get(row.get('source') or '', row.get('agent') or 'This agent')
    usage = live.usage_hint_for_row(row) or 'Usage unknown — open the Skeptic widget for live totals'
    tab_line = ' · '.join(p for p in (hint_tty or row.get('tty'), hint_title or row.get('tab_title')) if p) or '—'
    payload = {
        'kind': 'active_session',
        'provider': name,
        'conversation': str(row.get('label') or row.get('title') or 'Untitled')[:240],
        'tty': hint_tty or row.get('tty') or '',
        'tabTitle': hint_title or row.get('tab_title') or '',
        'usageQuota': usage,
    }
    approved = _native_dialog(payload, run=run)
    if approved is not None:
        return approved
    lines = [
        'SKEPTIC · Session Handoff',
        '',
        'This session is still running.',
        '',
        'On this tab: ' + name,
        'Quota: ' + usage,
        'Terminal tab: ' + tab_line,
        '',
        'End this session and switch to another agent? The handoff packet will open in a new engine.',
    ]
    text = '\n'.join(lines)
    try:
        result = run(['/usr/bin/osascript', '-e', ACTIVE_SCRIPT, text], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == ACTIVE_APPROVE_BUTTON


def confirm_close_source(provider, conversation, source_tty, tab_title='', run=None):
    """After the destination CLI is running, ask whether to close the stuck source tab."""
    run = run or subprocess.run
    conversation = str(conversation or 'Untitled')
    provider = str(provider or 'New engine')
    tty = str(source_tty or '')
    title = str(tab_title or '').strip()
    tab_line = ' · '.join(p for p in (tty, title) if p) or tty or '—'
    payload = {
        'kind': 'close_source',
        'provider': provider,
        'conversation': conversation,
        'tty': tty,
        'tabTitle': title,
    }
    approved = _native_dialog(payload, run=run)
    if approved is not None:
        return approved
    lines = [
        'SKEPTIC · Session Handoff',
        '',
        'The new engine is running.',
        '',
        'Continuing in: ' + provider,
        'Conversation: ' + conversation,
        'Stuck tab: ' + tab_line,
        '',
        'Your recovery packet was delivered. Close the stuck tab now? '
        'That ends the live CLI only; session files on disk stay intact.',
    ]
    text = '\n'.join(lines)
    try:
        result = run(['/usr/bin/osascript', '-e', CLOSE_SCRIPT, text], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == CLOSE_APPROVE_BUTTON


def _lock_holder_tty(lock_path, run=None):
    import re
    run = run or subprocess.run
    try:
        holders = run(['/usr/sbin/lsof', '-t', str(lock_path)], capture_output=True, text=True, timeout=5)
        pids = {p for p in holders.stdout.splitlines() if re.fullmatch(r'[0-9]{1,10}', p)}
        if holders.returncode or len(pids) != 1:
            return None
        pid = next(iter(pids))
        for spec in ('0', '0,1,2'):
            descriptors = run(['/usr/sbin/lsof', '-a', '-p', pid, '-d', spec, '-Fn'],
                                capture_output=True, text=True, timeout=5)
            terminals = [line[1:] for line in descriptors.stdout.splitlines()
                         if re.fullmatch(r'n/dev/ttys[0-9]{3,6}', line)]
            if descriptors.returncode == 0 and len(terminals) == 1:
                return terminals[0]
        descriptors = run(['/usr/sbin/lsof', '-a', '-p', pid, '-Fn'], capture_output=True, text=True, timeout=5)
        terminals = sorted({line[1:] for line in descriptors.stdout.splitlines()
                            if re.fullmatch(r'n/dev/ttys[0-9]{3,6}', line)})
        return terminals[0] if len(terminals) == 1 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _focus_terminal(tty, run=None):
    run = run or subprocess.run
    short = tty.rsplit('/', 1)[-1] if tty else ''
    if not short:
        return False
    script = r'''
tell application "Terminal"
    repeat with win in windows
        repeat with tabItem in tabs of win
            if tty of tabItem contains "''' + short + r'''"" then
                set selected tab of win to tabItem
                set index of win to 1
                activate
                return "ok"
            end if
        end repeat
    end repeat
end tell
'''
    try:
        result = run(['/usr/bin/osascript', '-e', script], capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and result.stdout.strip() == 'ok'
    except (OSError, subprocess.SubprocessError):
        return False


def present_busy_handoff(lock_path, run=None):
    """When a second ⌘⇧S hits an in-flight handoff, explain and raise the active tab."""
    run = run or subprocess.run
    tty = _lock_holder_tty(lock_path, run=run)
    payload = {'kind': 'existing', 'tty': tty or ''}
    _native_dialog(payload, run=run)
    if not tty:
        return False
    return _focus_terminal(tty, run=run)


def show_existing(lock_path, run=None):
    """Offer the sole terminal attached to the live reservation; never stop it."""
    run = run or subprocess.run
    tty = _lock_holder_tty(lock_path, run=run)
    if not tty:
        return False
    approved = _native_dialog({'kind': 'existing', 'tty': tty}, run=run)
    if approved is not None:
        if approved:
            return _focus_terminal(tty, run=run)
        return False
    result = run(['/usr/bin/osascript', '-e', EXISTING_SCRIPT, tty],
                 capture_output=True, text=True, timeout=300)
    return result.returncode == 0