"""Hold the CLI writer reservation while a headless handoff runs in Terminal."""
import subprocess
import sys

from switcher import State, host, writer_reservation


def main(state_dir, command):
    try:
        state = State(state_dir)
        try:
            with writer_reservation(state):
                return subprocess.call(command)
        finally:
            state.close()
    except (OSError, host.Denied) as exc:
        print('Skeptic: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2:]))
