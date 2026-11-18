#!/bin/zsh -l
# ⌘⇧S handoff — no visible shell steps; Skeptic sheets handle the UX.
printf '\033[3J\033[H\033[2J\033]0;Skeptic · Session Handoff\007'
export SKEPTIC_HINT_TTY="$(cat "$HOME/.skeptic-widget/hint-tty" 2>/dev/null)"
export SKEPTIC_HINT_TITLE="$(cat "$HOME/.skeptic-widget/hint-title" 2>/dev/null)"
if [[ -z "$SKEPTIC_HINT_TTY" ]]; then
  printf '\033[1;97;40m Skeptic: missing tab hint — press ⌘⇧S with Terminal on the stuck tab. \033[0m\n' >&2
  exit 2
fi
exec "$HOME/.local/bin/skeptic"