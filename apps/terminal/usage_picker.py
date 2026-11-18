"""Read-only quota hints for the engine picker (Skeptic session tracker / ai_usage.py)."""
import datetime
import importlib.util
import json
import os
import re
from pathlib import Path

NAMES = {'codex': 'Codex', 'claude': 'Claude', 'hermes': 'Hermes', 'cursor': 'Cursor',
         'antigravity': 'Antigravity', 'copilot': 'Copilot', 'ollama': 'Ollama'}


def _short_reset(epoch):
    if epoch is None:
        return 'soon'
    try:
        dt = datetime.datetime.fromtimestamp(int(epoch), tz=datetime.datetime.now().astimezone().tzinfo)
    except (TypeError, ValueError, OSError):
        return 'soon'
    now = datetime.datetime.now(dt.tzinfo)
    if dt.date() == now.date():
        return dt.strftime('today %I:%M%p').lstrip('0').replace(' 0', ' ')
    if (dt.date() - now.date()).days == 1:
        return 'tomorrow ' + dt.strftime('%I:%M%p').lstrip('0').replace(' 0', ' ')
    return dt.strftime('%a %I:%M%p').lstrip('0').replace(' 0', ' ')


def _feel(left):
    if left is None:
        return None
    if left <= 0:
        return 'at cap'
    if left < 5:
        return 'nearly exhausted'
    if left >= 50:
        return 'plenty of room'
    if left >= 25:
        return 'some room'
    if left >= 10:
        return 'getting tight'
    return 'running low'


def _window_kind(label):
    low = (label or '').lower()
    if '5' in low and 'hour' in low:
        return '5-hour rolling'
    if 'week' in low or 'billing' in low:
        return 'weekly'
    if 'auto' in low:
        return 'auto pool'
    if 'hour' in low:
        return low.replace('-', ' ') + ' window'
    return (label or 'usage window').strip()


def _ordered_windows(windows):
    wins = [w for w in (windows or []) if isinstance(w, dict) and w.get('used_pct') is not None]
    def rank(w):
        lab = (w.get('label') or '').lower()
        if '5' in lab and 'hour' in lab:
            return 0
        if 'week' in lab or 'billing' in lab:
            return 1
        return 2
    return sorted(wins, key=rank)


def _format_window(w):
    used = w.get('used_pct')
    if used is None:
        return None
    left = max(0, min(100, 100 - float(used)))
    kind = _window_kind(w.get('label'))
    feel = _feel(left)
    reset = _short_reset(w.get('resets_at'))
    return f'{feel} ({int(left)}% left · {kind}, resets {reset})'


def _hermes_handoff_model():
    """Model Skeptic's Hermes handoff uses when it does not pass -m (env, then active config)."""
    env = os.environ.get('HERMES_MODEL', '').strip()
    if env:
        return env
    verified = Path.home() / '.hermes' / 'ollama' / 'verification' / 'active-config-verified.json'
    if verified.is_file():
        try:
            model = json.loads(verified.read_text()).get('model')
            if isinstance(model, str) and model.strip():
                return model.strip()
        except (OSError, ValueError, TypeError):
            pass
    cfg = Path.home() / '.hermes' / 'config.yaml'
    if not cfg.is_file():
        return None
    try:
        text = cfg.read_text()
    except OSError:
        return None
    match = re.search(r'^model:\s*\n(?:[ \t#].*\n)*?[ \t]+default:\s*["\']?([^"\'\s#]+)', text, re.MULTILINE)
    return match.group(1) if match else None


def _load_collect():
    script = Path.home() / 'ai-search-tracker' / 'scripts' / 'ai_usage.py'
    if not script.is_file():
        return {}
    spec = importlib.util.spec_from_file_location('ai_usage_picker', script)
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.collect()
    return {p['id']: p for p in data.get('providers', []) if isinstance(p, dict) and p.get('id')}


def _line(engine_id, providers):
    name = NAMES.get(engine_id, engine_id)
    if engine_id == 'hermes':
        model = _hermes_handoff_model()
        label = f'{name} ({model})' if model else name
        return f'{label} — runs on your Mac (no cloud weekly cap)'
    p = providers.get(engine_id)
    if not p or p.get('missing'):
        return f'{name} — no usage info yet (Skeptic session tracker)'
    parts = [_format_window(w) for w in _ordered_windows(p.get('windows'))[:2]]
    parts = [p for p in parts if p]
    if not parts:
        return f'{name} — usage unknown'
    if len(parts) == 1:
        return f'{name} — {parts[0]}'
    return f'{name} — {parts[0]}; {parts[1]}'


def choice_labels(engine_ids, providers=None):
    providers = providers if providers is not None else _load_collect()
    return [_line(e, providers) for e in engine_ids]