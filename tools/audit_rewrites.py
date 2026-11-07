"""Compare generated session modules with actual COBOL on fresh held-out inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import legacy
from agents._sandbox import run_main


def cases(module_id):
    def cents(value):
        return f'{value // 100}.{value % 100:02d}'
    randomizer = random.Random(70112026 + len(module_id))
    base = json.loads((ROOT / f'legacy/inputs/{module_id}.json').read_text())
    examples = list(base)
    for _ in range(128):
        if module_id == 'interest':
            principal, rate, years = randomizer.randrange(10000000), randomizer.randrange(10001), randomizer.randrange(100)
            examples.append(f'{cents(principal)}|{cents(rate)}|{years}')
        elif module_id == 'payroll':
            hours, rate = randomizer.randrange(100000), randomizer.randrange(100000)
            examples.append(f'{cents(hours)}|{cents(rate)}')
        else:
            quantity, price, discount = randomizer.randrange(1000), randomizer.randrange(10000000), randomizer.randrange(10001)
            examples.append(f'{quantity}|{cents(price)}|{cents(discount)}')
    for _ in range(200):
        line = randomizer.choice(base)
        index = randomizer.randrange(len(line) + 1)
        examples.append(line[:index] + randomizer.choice('09.+-| e') + line[index:] if randomizer.randrange(2)
                        else line[:index] + line[index + 1:])
    examples += {'interest': ['00001|000.01|01', ' 001 | 050 | 01 ', '1.|2|3', '1\t|2|3'],
                 'invoice': ['2|99980.00|49.99', ' 001 | 00012.35 | 000.01 ', '1|1.|0', '1\t|2|3'],
                 'payroll': ['0.01|4.95', ' 040.00 | 020.00 ', '1.|2', '1\t|2']}[module_id]
    return list(dict.fromkeys(examples))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'mode': 'held_out_inputs_against_actual_cobol', 'modules': {}}
    for module_id in ('interest', 'invoice', 'payroll'):
        inputs = cases(module_id)
        binary = legacy.compile_cobol(ROOT / f'legacy/{module_id}.cbl')
        expected = [legacy.run_cobol(binary, line) for line in inputs]
        result = run_main((args.session / f'modern/{module_id}.py').read_text(), inputs)
        failures = []
        actual = result.get('results', [])
        for i, (line, output) in enumerate(zip(inputs, expected)):
            observed = actual[i].get('output') if i < len(actual) and actual[i].get('ok') and actual[i].get('type_ok') else repr(actual[i] if i < len(actual) else result)
            if observed != output:
                failures.append({'input': line, 'expected': output, 'actual': observed})
        report['modules'][module_id] = {'passed': len(inputs) - len(failures), 'total': len(inputs), 'failures': failures}
        print(module_id, report['modules'][module_id]['passed'], '/', len(inputs), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    return 0 if all(not m['failures'] for m in report['modules'].values()) else 2


if __name__ == '__main__':
    sys.exit(main())
