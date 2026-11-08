"""Home navigation takes priority over delayed live-run responses."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_home_routes_buttons_and_stale_live_responses():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend navigation check')
    result = subprocess.run([node, '-'], input=r'''
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/galaxy.js','utf8'), elements=new Map();
function element() {
  const classes=new Set();
  return {classes,scrollTop:120,style:{},textContent:'',hidden:false,
    classList:{add:c=>classes.add(c),remove:c=>classes.delete(c),contains:c=>classes.has(c),
      toggle(c,on){if(on)classes.add(c);else classes.delete(c)}},
    setAttribute(k,v){this[k]=v},focus(){this.focused=true}};
}
function get(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)}
const intake=element(), routes=[], loads=[], attached=[], timers=[];
const context=vm.createContext({intake,document:{body:element(),getElementById:get},
  location:{pathname:'/demo/',search:'?present=1',hash:''},
  history:{replaceState:(a,b,url)=>routes.push(url)},
  uploadVersion:0,travel:{},resumeAfter:true,playing:true,clock:6.95,playBtn:get('play'),
  cancelEntrance(){},closePanel(){},closeCaption(){},renderIntake(){},syncPlayback(){},
  runLiveBtn:get('run-live-instead'),API:null,recordings:[],sel:get('replay'),esc:s=>s,
  fetch:async url=>({ok:true,json:async()=>url==='api/status'?{live:true}:[{name:'bank',title:'Retail bank'}]}),
  load:async name=>loads.push(name),attach:s=>attached.push(s),
  showError:error=>{throw error},setTimeout:fn=>timers.push(fn),console});
const block=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end));
vm.runInContext(block('  const caseFile =','  function normalize('),context);
vm.runInContext(block('  // the intake:','  function renderIntake('),context);
vm.runInContext(block('  async function startLive(','  // follow a run'),context);
const read=s=>vm.runInContext(s,context);
const boot=source.slice(source.lastIndexOf('  (async () => {'),source.lastIndexOf('  requestAnimationFrame(frame);'));
function atHome(){
  assert.equal(intake.classes.has('open'),true);
  assert.equal(get('case').classes.has('open'),false);
  assert.equal(routes.at(-1),'/demo/?present=1');
  assert.equal(intake.scrollTop,0);
  assert.equal(read('playing'),false);assert.equal(read('travel'),null);
  assert.equal(read('clock'),6.95);
  assert.equal(get('loading').style.display,'none');
  assert.equal(get('northbase-title').focused,true);
}
(async()=>{
  await read(boot);atHome(); // A fresh root opens the landing, even without a loaded replay.
  context.location.hash='#codebases';await read(boot);atHome();
  context.location.hash='#case';await read(boot);
  assert.equal(get('case').classes.has('open'),true);
  assert.equal(intake['aria-hidden'],'true');assert.equal(routes.at(-1),'#case');
  get('case-home').onclick();atHome();
  get('in-back').onclick();assert.equal(get('case').classes.has('open'),true);
  get('case-go').onclick();atHome();
  read('playing=true; travel={target:99}');get('intake-btn').onclick();atHome();
  get('panel-home').onclick();atHome();
  context.location.hash='#bank';await read(boot);assert.deepEqual(loads,['bank']);
  context.location.hash='#live=session-123';await read(boot);assert.deepEqual(attached,['session-123']);
  loads.length=0;attached.length=0;

  let resolveLive;
  context.fetch=()=>new Promise(resolve=>{resolveLive=resolve});
  const pending=read('startLive("samples/bank","bank")');
  get('intake-btn').onclick();atHome();
  resolveLive({ok:true,json:async()=>({session:'late-session'})});await pending;
  assert.deepEqual(attached,[]);atHome();assert.equal(get('in-note').textContent,'');

  context.fetch=async()=>({ok:false,json:async()=>({error:'Needs NVIDIA_API_KEY'})});
  await read('startLive("samples/bank","bank")');assert.equal(timers.length,1);
  get('intake-btn').onclick();timers.pop()();assert.deepEqual(loads,[]);atHome();

  context.fetch=async()=>({ok:true,json:async()=>({session:'current-session'})});
  await read('startLive("samples/bank","bank")');assert.deepEqual(attached,['current-session']);
})().catch(error=>{console.error(error);process.exitCode=1});
''', cwd=ROOT, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
