"""A dropped codebase replays its recorded real run the way it happened: step by step."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_js(script):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend replay check')
    result = subprocess.run([node, '-'], input=script, cwd=ROOT, text=True,
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_recording_runs_through_every_real_event_like_a_live_run():
    run_js(r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const source=fs.readFileSync('web/galaxy.js','utf8'), elements=new Map();
const context=vm.createContext({W:1000,H:520,CY:252,innerWidth:1000,innerHeight:520,
  intake:{classList:{add(){},remove(){},contains:()=>false},setAttribute(){}},reducedMotion:{matches:true},
  document:{getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',dataset:{},setAttribute(){}});return elements.get(id)}},
  performance:{now:()=>0},window:{},addEventListener(){},closePanel(){},closeCaption(){},intakeOpen:()=>false,
  panel:{classList:{contains:()=>false}},workSince:new Map(),STATIONS:['Discover','Read','Probe','Record','Rewrite','Verify','Verified'].map((s,i)=>[i,s])});
const block=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b));
vm.runInContext(block('  // ---------- helpers ----------','  // ---------- static layers ----------'),context);
vm.runInContext(block('  // ---------- replay → timeline ----------','  // ---------- module text for the scene ----------'),context);
vm.runInContext(block('  // ---------- live: the timeline so far','  function draw(t) {'),context);
const read=s=>vm.runInContext(s,context);
const full=JSON.parse(fs.readFileSync('web/replays/bank.json','utf8'));
read(`FULL=${JSON.stringify(full)}; normalize=r=>r; startSim(FULL)`);

// It starts working at Read (Discover needs no model), already playing, past the title.
let w=read('TL.beats.find(b=>b.working)');
assert.equal(read('SIM.n'),0); assert.equal(w.at,1); assert.equal(read('playing'),true); assert.equal(read('clock'),3.4);

// Details only know what has happened: nothing yet, then the spec, then the answer key.
assert.equal(read('R.modules[0].spec'),null); assert.equal(read('R.modules[0].golden.length'),0);
assert.equal(read('R.modules[0].history.length'),0); assert.equal(read('R.modules[0].status'),'pending');
read('SIM.n=1; simApply()'); assert.ok(read('R.modules[0].spec')); assert.equal(read('R.modules[0].golden.length'),0);
read('SIM.n=2; simApply()'); assert.ok(read('R.modules[0].golden.length')>0); assert.equal(read('R.modules[0].status'),'running');
// ALERTS mid-run shows only its first, failed attempt until the retry has happened.
const alertsFirstVerify=full.events.findIndex(e=>e.module==='alerts'&&e.node==='verify')+1;
read(`SIM.n=${alertsFirstVerify}; simApply()`);
const alerts=read("R.modules.find(m=>m.id==='alerts')");
assert.equal(alerts.history.length,1); assert.ok(alerts.history[0].passed<alerts.history[0].total); assert.equal(alerts.status,'running');
read('startSim(FULL)');

// Play it: every working step waits a compressed real duration, then its real event lands.
const waits=[]; let guard=0, failSeen=false;
while(read('SIM.n')<full.events.length && guard++<200000){
  w=read('TL.beats.find(b=>b.working)'); if(w) waits.push(w.workDur);
  read('clock+=.05; simTick()');
  if(read('TL.beats.some(b=>b.fail)')) failSeen=true;
}
assert.equal(read('SIM.n'),full.events.length);
assert.ok(waits.every(d=>d>=1.4 && d<=3.6), 'each step works 1.4-3.6s');
assert.ok(failSeen, 'ALERTS failure is replayed');
assert.equal(read('R.finished'),true);
// The finished run has exactly the recording's stops (38 for the bank), retry included.
read('FULLTL=buildTimeline(FULL)');
assert.equal(read('stops().length'), read("FULLTL.beats.filter(b=>['dwell','outro'].includes(b.k)).length"));

// Next lands the real result of a working step at once.
read('startSim(FULL)'); assert.equal(read('SIM.n'),0);
read('clock=TL.beats.find(b=>b.working).t0+.1; step(1)');
assert.equal(read('SIM.n'),1);
// Restart replays it from the beginning; a normal recording link is never a simulation.
read('restart()'); assert.equal(read('SIM.n'),0); assert.equal(read('playing'),true);
read('SIM=null; R=FULL; TL=buildTimeline(R); restart()'); assert.equal(read('playing'),false);
''')


def test_settle_asks_a_person_and_the_hint_is_replayed_before_the_retry():
    run_js(r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const source=fs.readFileSync('web/galaxy.js','utf8'), elements=new Map();
const context=vm.createContext({W:1000,H:520,CY:252,innerWidth:1000,innerHeight:520,
  intake:{classList:{add(){},remove(){},contains:()=>false},setAttribute(){}},reducedMotion:{matches:true},
  document:{getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',dataset:{},setAttribute(){}});return elements.get(id)}},
  performance:{now:()=>0},window:{},addEventListener(){},closePanel(){},closeCaption(){},intakeOpen:()=>false,
  panel:{classList:{contains:()=>false}},workSince:new Map(),STATIONS:['Discover','Read','Probe','Record','Rewrite','Verify','Verified'].map((s,i)=>[i,s])});
const block=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b));
vm.runInContext(block('  // ---------- helpers ----------','  // ---------- static layers ----------'),context);
vm.runInContext(block('  // ---------- replay → timeline ----------','  // ---------- module text for the scene ----------'),context);
vm.runInContext(block('  // ---------- live: the timeline so far','  function draw(t) {'),context);
const read=s=>vm.runInContext(s,context);
const full=JSON.parse(fs.readFileSync('web/replays/retail.json','utf8'));
assert.deepEqual(full.modules.map(m=>m.id),['accrue','feerate','alerts','loanpay','statemnt','settle']);
const settle=full.modules[5];
assert.equal(settle.human_hints.length,1); assert.ok(settle.run_note.includes('human hint'));
read(`FULL=${JSON.stringify(full)}; normalize=r=>r; startSim(FULL)`);

let asked=false, reviewWait=0, hintsBeforeAnswer=null, backAfterReview=false, sawReview=false, guard=0;
while(read('SIM.n')<full.events.length && guard++<400000){
  const w=read('TL.beats.find(b=>b.working)');
  if(w && w.review){ sawReview=true; reviewWait=read('TL.beats.find(b=>b.working).workDur');
    const m=read("R.modules.find(m=>m.id==='settle')"); asked=m.status==='needs_review'; hintsBeforeAnswer=m.human_hints.length;
    // the replay waits for the presenter: nothing moves on until a hint is sent
    if(!read('SIM.hintSent')){ const n=read('SIM.n'); read('clock+=30; simTick()'); assert.equal(read('SIM.n'),n,'waits for the hint');
      read('sendHint("The amount has no implied decimal")'); assert.equal(read('SIM.typedHint'),'The amount has no implied decimal'); } }
  if(sawReview && read("TL.beats.some(b=>b.k==='move'&&b.back&&b.mi===5)")) backAfterReview=true;
  read('clock+=.05; simTick()');
}
assert.ok(sawReview,'the replay stops at Verify while SETTLE asks a person');
assert.ok(asked,'Details show SETTLE as needs_review while it asks');
assert.equal(hintsBeforeAnswer,0,'the hint is not shown as sent before the person sent it');
assert.equal(reviewWait,8.5,'long enough to read the case and type the hint');
assert.ok(backAfterReview,'after the hint the star goes back to Rewrite');
assert.equal(read('R.finished'),true);
// the finished recording keeps the same stop, so Back returns to the ask
assert.ok(read('buildTimeline(FULL).beats.some(b=>b.review && b.mi===5)'));
assert.equal(read("R.modules.find(m=>m.id==='settle').status"),'done');
''')
