"""Run the public pipeline in a disposable session, preserving committed goldens.

python tools/isolated_run.py --mode real [--only invoice] [--legacy-dir samples/legacy]
Credentials stay in the parent environment; session directories contain no .env.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('fake', 'real'), default='real')
    parser.add_argument('--only', help='any module id; its dependencies run first')
    parser.add_argument('--legacy-dir', default='legacy',
                        help='COBOL codebase folder, relative to the repo (default: legacy)')
    args = parser.parse_args()
    if Path(args.legacy_dir).is_absolute() or not (ROOT / args.legacy_dir).is_dir():
        parser.error(f'--legacy-dir must be a folder inside the repo: {args.legacy_dir}')
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    if args.mode == 'real' and not os.getenv('NVIDIA_API_KEY', '').startswith('nvapi-'):
        parser.error('Configure NVIDIA_API_KEY in the local .env first')
    runs = ROOT / 'runs'
    runs.mkdir(exist_ok=True)
    with (runs / 'session.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('A managed pipeline run is already active')
        name = time.strftime('%Y%m%d-%H%M%S') + '-' + args.mode + '-' + uuid.uuid4().hex[:6]
        session = runs / 'sessions' / name
        shutil.copytree(ROOT, session, ignore=shutil.ignore_patterns(
            '.git', '.env', '.env.*', '__pycache__', '.pytest_cache', '.cache', '.venv*',
            'runs', 'bin', 'modern', 'specs', 'equivalence', 'unit', 'validation'))
        metadata = {'session': name, 'mode': args.mode, 'only': args.only, 'legacy_dir': args.legacy_dir,
                    'status': 'running',
                    'started_at': time.strftime('%Y-%m-%dT%H:%M:%S')}
        metadata_path = session / 'session.json'
        metadata_path.write_text(json.dumps(metadata, indent=2))
        temporary = runs / 'latest_session.tmp'
        temporary.write_text(json.dumps({'session': name}))
        os.replace(temporary, runs / 'latest_session.json')
        command = [sys.executable, '-u', str(session / 'run.py'), str(session / args.legacy_dir)]
        if args.only:
            command += ['--only', args.only]
        environment = dict(os.environ, LLM_MODE=args.mode, LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')
        environment.pop('P4_FORCE_LOCAL_LLM', None)
        print(f'Session: {session}', flush=True)
        # Full output is retained for inspection; only our pipeline prints here.
        with (session / 'pipeline.log').open('w') as log:
            process = subprocess.Popen(command, cwd=session, env=environment, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, bufsize=1)
            try:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    print(line, end='', flush=True)
                code = process.wait()
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                metadata.update(status='done' if process.returncode == 0 else 'failed',
                                returncode=process.returncode, finished_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
                metadata_path.write_text(json.dumps(metadata, indent=2))
        return code


if __name__ == '__main__':
    sys.exit(main())
