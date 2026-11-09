"""Install the website's locked dependencies when a fresh checkout doesn't have them yet."""
import shutil
import subprocess


def ensure_website_deps(website, env=None, which=shutil.which, run=subprocess.run, log=print):
    if (website / 'node_modules').is_dir():
        return False
    if not which('npm'):
        raise SystemExit('Full validation needs Node 22+ with npm for the website build. '
                         'Install Node, then run tests/validate.py again.')
    log('Website dependencies are missing; installing the locked versions with npm ci.', flush=True)
    try:
        run(['npm', 'ci'], cwd=website, env=env, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f'npm ci failed with exit status {error.returncode}. Check your network, '
                         'then run: npm ci --prefix apps/website') from error
    return True
