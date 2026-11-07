"""Private pytest plugin. Writes case data, never parses pytest terminal text."""
import json
from pathlib import Path
import pytest


def pytest_addoption(parser):
    parser.addoption('--equivalence-report', required=True)


def pytest_configure(config):
    config._equivalence_results = {}
    config._equivalence_snapshots = {}


def pytest_collection_modifyitems(session, config, items):
    # Freeze reference values before any rewrite fixture is imported. A rewrite
    # must not turn a wrong result into a pass by modifying a mutable case dict.
    for item in items:
        case = getattr(getattr(item, 'callspec', None), 'params', {}).get('case')
        if case is not None:
            config._equivalence_snapshots[item.nodeid] = (case['input'], case['output'])


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    snapshot = item.config._equivalence_snapshots.get(item.nodeid)
    if snapshot is None:
        return
    input_line, expected = snapshot
    results = item.config._equivalence_results
    actual = dict(item.user_properties).get('actual')
    if report.when == 'call' and report.passed and (type(actual) is not str or actual != expected):
        report.outcome = 'failed'
        report.longrepr = 'Actual output disagrees with the original golden snapshot'
    if report.failed:
        if actual is None or report.when != 'call' or call.excinfo and call.excinfo.typename != 'AssertionError':
            actual = '<exception> ' + report.longreprtext
        results[item.nodeid] = {'input': input_line, 'expected': expected, 'actual': actual}
    elif report.when == 'call' and report.passed:
        results[item.nodeid] = None


def pytest_sessionfinish(session, exitstatus):
    results = session.config._equivalence_results
    failures = [failure for failure in results.values() if failure is not None]
    data = {'passed': sum(value is None for value in results.values()),
            'total': len(results), 'failures': failures,
            'collection_errors': session.testsfailed if exitstatus not in (0, 1) else 0}
    path = Path(session.config.getoption('--equivalence-report'))
    path.write_text(json.dumps(data, ensure_ascii=True), encoding='utf-8')
