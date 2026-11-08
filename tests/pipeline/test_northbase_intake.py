"""The intake comet follows the galaxy's left-to-right path and reduced-motion preference."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_intake_shooting_star_moves_left_to_right_and_respects_reduced_motion():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend animation check')
    result = subprocess.run([node, '-e', r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const source=fs.readFileSync('web/galaxy.js','utf8'), heads=[];
const context=vm.createContext({W:1000,H:520,reducedMotion:{matches:false},
  x:{createLinearGradient:()=>({addColorStop(){}}),beginPath(){},moveTo(){},lineTo(){},stroke(){}},
  star:(x,y)=>heads.push([x,y])});
const start=source.indexOf('  function drawIntakeComet(t)'), end=source.indexOf('  // ---------- live:', start);
assert.ok(start>=0 && end>start);
vm.runInContext(source.slice(start,end),context);
vm.runInContext('drawIntakeComet(.5); drawIntakeComet(1.5)',context);
assert.equal(heads.length,2); assert.ok(heads[1][0]>heads[0][0]);
vm.runInContext('drawIntakeComet(3)',context); assert.equal(heads.length,2);
vm.runInContext('reducedMotion.matches=true; drawIntakeComet(.5)',context);
assert.equal(heads.length,2);
'''], cwd=ROOT, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
