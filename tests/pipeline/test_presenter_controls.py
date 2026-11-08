"""Exercise actual replay navigation through the bank's modules and retry beats."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_recording_waits_for_presenter_and_preserves_every_retry_stop():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend navigation check')
    result = subprocess.run([node, '-e', r'''
const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('web/galaxy.js', 'utf8');
const elements = new Map(), listeners = {};
const context = vm.createContext({
  document: {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {textContent:'',dataset:{},setAttribute(){}});
    return elements.get(id);
  }}, performance:{now:()=>0}, window:{},
  addEventListener:(name,fn)=>listeners[name]=fn,
  closePanel(){},closeCaption(){},intakeOpen:()=>false,
  STATIONS:['Discover','Read','Probe','Record','Rewrite','Verify','Verified'].map((s,i)=>[i,s]),
});
const block = (start,end) => source.slice(source.indexOf(start),source.indexOf(end));
vm.runInContext(block('  // ---------- replay → timeline ----------', '  // ---------- module text for the scene ----------'),context);
vm.runInContext(`R = ${fs.readFileSync('web/replays/bank.json','utf8')}; TL = buildTimeline(R); restart();`,context);
const read = expression => vm.runInContext(expression,context);
assert.equal(read('playing'), false);
assert.equal(read('stopIndex(stops())'),0);
assert.equal(elements.get('previous-step').disabled,true);
const count = read('stops().length');
assert.equal(count,39);
const visited=[];
for(let i=1;i<count;i++) {
  elements.get('next-step').onclick();
  assert.equal(read('playing'),false);
  assert.equal(read('stopIndex(stops())'),i);
  visited.push(read('JSON.stringify(stops()[stopIndex(stops())])'));
}
assert.equal(elements.get('next-step').disabled,true);
const end = read('clock');
elements.get('next-step').onclick();
assert.equal(read('clock'),end);
assert.equal(visited.map(JSON.parse).filter(b=>b.h>0&&b.at===4).length,1);
assert.equal(visited.map(JSON.parse).filter(b=>b.h>0&&b.at===5).length,1);
elements.get('play').onclick(); assert.equal(read('playing'),true);
elements.get('previous-step').onclick(); assert.equal(read('playing'),false);
assert.equal(read('resumeAfter'),false);
listeners.keydown({target:{tagName:'BODY'},key:'ArrowLeft',repeat:false,preventDefault(){}});
assert.equal(read('stopIndex(stops())'),count-3);
elements.get('restart').onclick();
assert.equal(read('playing'),false); assert.equal(read('stopIndex(stops())'),0);
const before=read('clock');
listeners.keydown({target:{tagName:'BODY'},key:'ArrowRight',repeat:true,preventDefault(){}});
assert.equal(read('clock'),before);
'''], cwd=ROOT, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
