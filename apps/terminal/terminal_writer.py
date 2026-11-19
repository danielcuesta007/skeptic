"""Hold the CLI writer reservation while a headless handoff runs in Terminal."""
import signal
import subprocess
import sys

from switcher import State, host, writer_reservation


def main(state_dir, command):
    try:
        state = State(state_dir)
        try:
            with writer_reservation(state):
                # The provider shares the foreground group and handles Ctrl-C itself.
                # A caught signal handler resets to the default on exec in the child.
                previous = signal.signal(signal.SIGINT, lambda *_: None)
                try:
                    return subprocess.call(command)
                finally:
                    signal.signal(signal.SIGINT, previous)
        finally:
            state.close()
    except (OSError, host.Denied) as exc:
        print('Skeptic: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2:]))
