"""Streamlit dashboard: python -m streamlit run ui/app.py --server.address 127.0.0.1"""
from __future__ import annotations

import difflib
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import uuid

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui.dashboard_data import (artifact, blocked_on, calls, cobol_source, copybooks, migration_chains,
                               read_json, session_root)

st.set_page_config(page_title='Legacy → Verified', page_icon='✓', layout='wide')
st.markdown('''<style>
.stApp { background: #10151b; color: #edf1f5; }
.chain { font-family: ui-monospace, monospace; font-size: 1.05em; margin: 2px 0 10px; }
.chain b { background: #19232d; border: 1px solid #304251; border-radius: 6px; padding: 3px 9px; }
.badge { font-size: .75em; border-radius: 4px; padding: 1px 7px; margin-left: 6px; }
.sub { background: #2b3a55; color: #b9cdf2; } .blocked { background: #3a3f45; color: #b8bec6; }
[data-testid="stMetric"] { background: #19232d; border: 1px solid #304251; padding: 18px; border-radius: 10px; }
h1 { letter-spacing: -.04em; } code { font-size: .88em; }
</style>''', unsafe_allow_html=True)
st.caption('HACKUTD / NVIDIA NEMOTRON')
st.title('Legacy → Verified')
st.write('Read the original. Record its behavior. Accept Python only when the outputs match.')


def busy():
    (ROOT / 'runs').mkdir(exist_ok=True)
    with (ROOT / 'runs/session.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            return True


busy_at_render = busy()
with st.sidebar:
    st.header('Run controls')
    st.caption('Each run gets its own source and output folder. Saved goldens stay intact.')
    mode = st.selectbox('Execution', ['real', 'fake'], format_func=lambda x: 'Live NVIDIA models' if x == 'real' else 'Offline fixture demo')
    codebases = [d for d in ('legacy', 'samples/legacy') if (ROOT / d).is_dir()]
    legacy_dir = st.selectbox('Codebase', codebases)
    module_ids = sorted(p.stem.lower() for p in (ROOT / legacy_dir).glob('*.cbl'))
    only = st.selectbox('Modules', ['All modules'] + module_ids,
                        help='A single module also runs the modules it calls, first.')
    if st.button('Start pipeline', type='primary', disabled=busy_at_render):
        jobs = ROOT / 'runs/jobs'
        jobs.mkdir(parents=True, exist_ok=True)
        log_path = jobs / (uuid.uuid4().hex + '.log')
        command = [sys.executable, '-u', str(ROOT / 'tools/isolated_run.py'), '--mode', mode,
                   '--legacy-dir', legacy_dir]
        if only != 'All modules':
            command += ['--only', only]
        with log_path.open('w') as log:
            subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        st.session_state['job_log'] = str(log_path)
        st.success('Pipeline launched. Live progress appears below.')
    sessions = ROOT / 'runs/sessions'
    names = sorted((p.name for p in sessions.iterdir() if p.is_dir()), reverse=True) if sessions.exists() else []
    selected = st.selectbox('Inspect run', ['Latest'] + names)
    st.caption('Refreshes every 2 seconds. Keep this dashboard on localhost.')
    if st.session_state.get('job_log'):
        with st.expander('Launch log'):
            st.code(Path(st.session_state['job_log']).read_text()[-6000:] or 'Starting…')


@st.fragment(run_every=2)
def live_view():
    if busy_at_render != busy():
        st.rerun(scope='app')
    try:
        directory = session_root(ROOT, selected)
    except ValueError as error:
        st.info(str(error))
        return
    state = read_json(directory / 'runs/state.json', {}) or {}
    metadata = read_json(directory / 'session.json', {}) or {}
    if not state:
        st.info('Ready for the first run. Choose a mode and start the pipeline.')
        return
    real = state.get('mode') == 'real_model'
    if real:
        st.info('REAL MODEL RUN · NVIDIA agents · exact comparisons against actual COBOL outputs')
    else:
        st.warning('OFFLINE FIXTURE DEMO · handwritten agent responses · no model calls')
    st.caption(f"Session {directory.name} · started {state.get('started_at', '—')} · {metadata.get('status', 'unmanaged CLI run')}")
    modules = state.get('modules', {})
    verified = sum(m.get('status') == 'done' for m in modules.values())
    passed = sum(m.get('tests_passed', 0) for m in modules.values())
    total = sum(m.get('tests_total', 0) for m in modules.values())
    trace = calls(directory)
    a, b, c, d = st.columns(4)
    a.metric('Modules verified', f'{verified}/{len(modules)}')
    b.metric('Exact matches', f'{passed}/{total}')
    c.metric('Rewrite attempts', sum(m.get('attempts', 0) for m in modules.values()))
    d.metric('Live model calls', sum(r['source'] == 'live' and r['ok'] for r in trace))
    st.progress(verified / max(1, len(modules)))
    st.caption('UNDERSTAND → SPEC → RECORD → REWRITE → VERIFY → ACCEPT')
    chains, standalone = migration_chains(modules)
    st.markdown('**Migration order**')
    for chain in chains:
        st.markdown('<div class="chain">' + '  →  '.join(f'<b>{m.upper()}</b>' for m in chain) + '</div>',
                    unsafe_allow_html=True)
    if standalone:
        st.markdown('<div class="chain">' + ('Standalone: ' if chains else '')
                    + '  ·  '.join(f'<b>{m.upper()}</b>' for m in standalone) + '</div>', unsafe_allow_html=True)
    for module_id, module in modules.items():
        waiting = blocked_on(module)
        shown = 'BLOCKED ⏸' if waiting else module.get('status', 'pending').upper()
        kind = ' · SUBPROGRAM' if module.get('kind') == 'subprogram' else ''
        label = f"{module_id.upper()}{kind} · {shown} · {module.get('tests_passed', 0)}/{module.get('tests_total', 0)} matches"
        with st.expander(label, expanded=module.get('status') == 'failed' and not waiting):
            badges = ''
            if module.get('kind') == 'subprogram':
                badges += '<span class="badge sub">subprogram · tested through a generated driver</span>'
            if waiting:
                badges += f'<span class="badge blocked">BLOCKED · waiting on {waiting}</span>'
            if badges:
                st.markdown(badges, unsafe_allow_html=True)
            if waiting:
                st.caption(f'Not attempted: {waiting} must be verified first, so no model calls were made.')
            elif module.get('error'):
                st.error(module['error'])
            source = cobol_source(directory, module, module_id)
            calls_out = [Path(p).stem.upper() for p in module.get('link') or []]
            used = copybooks(source)
            if calls_out or used or module.get('depends_on'):
                st.caption(f"Calls / links: {', '.join(calls_out) or '—'}  ·  "
                           f"Copybooks: {', '.join(used) or '—'}  ·  "
                           f"Depends on: {', '.join(d.upper() for d in module.get('depends_on') or []) or '—'}")
            if module.get('unit_tests_status') == 'needs_review':
                st.warning('Golden equivalence passed. Supplementary generated unit tests need review; no failing assertions were silently removed.')
            st.write(f"Attempts: {module.get('attempts', 0)}")
            tabs = st.tabs(['Spec', 'Source comparison', 'Mismatches'])
            with tabs[0]:
                if module.get('spec'):
                    st.json(module['spec'], expanded=False)
                else:
                    st.caption('Waiting for the spec agent…')
            with tabs[1]:
                left, right = st.columns(2)
                with left:
                    st.caption('Original COBOL')
                    st.code(source, language='cobol')
                with right:
                    st.caption('Generated Python')
                    st.code(artifact(directory, 'modern', module_id, '.py'), language='python')
            with tabs[2]:
                failures = module.get('last_failures') or module.get('divergences') or []
                if not failures:
                    st.caption('No current mismatches.' if module.get('status') == 'done' else 'No verification results yet.')
                for failure in failures[:10]:
                    st.code(json.dumps(failure, indent=2), language='json')
                    st.code('\n'.join(difflib.ndiff([failure.get('expected', '')], [failure.get('actual', '')])), language='diff')
    if trace:
        with st.expander('NVIDIA call evidence'):
            st.dataframe(trace, width='stretch', hide_index=True)
    with st.expander('Phase timeline'):
        st.dataframe(state.get('events', []), width='stretch', hide_index=True)
    st.caption('Verified means exact matches on the recorded cases; it does not prove equivalence for all possible inputs.')


live_view()
