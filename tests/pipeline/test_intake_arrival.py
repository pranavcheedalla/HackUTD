"""The zip-star entrance docks at Discover without starting replay playback."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_js(script):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the frontend animation check')
    result = subprocess.run([node, '-'], input=script, cwd=ROOT, text=True,
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_upload_star_docks_paused_and_can_be_cancelled_or_reduced():
    run_js(r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const source=fs.readFileSync('web/galaxy.js','utf8'), elements=new Map(), classes=new Set(['open']);
const intake={inert:false,classList:{add:c=>classes.add(c),remove:c=>classes.delete(c)},setAttribute(){}};
const context=vm.createContext({W:1000,H:520,CY:252,innerWidth:1000,innerHeight:520,intake,
  reducedMotion:{matches:false},drop:{querySelector:()=>({getBoundingClientRect:()=>({left:480,top:350,width:40,height:40})})},
  document:{getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',dataset:{},setAttribute(){}});return elements.get(id)}},
  performance:{now:()=>0},window:{},addEventListener(){},closePanel(){},closeCaption(){},intakeOpen:()=>false,
  STATIONS:['Discover','Read','Probe','Record','Rewrite','Verify','Verified'].map((s,i)=>[i,s])});
const block=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b));
vm.runInContext(block('  // ---------- helpers ----------','  // ---------- static layers ----------'),context);
vm.runInContext(block('  // ---------- replay → timeline ----------','  // ---------- module text for the scene ----------'),context);
const read=s=>vm.runInContext(s,context);
read(`R=${fs.readFileSync('web/replays/bank.json','utf8')}; TL=buildTimeline(R); restart()`);
(async()=>{
  const dockedAt=read('clock'), pending=read('startEntrance()');
  assert.equal(intake.inert,true); assert.equal(classes.has('entering'),true);
  assert.equal(elements.get('next-step').disabled,true);
  const initial=read('entrancePose(entrance)');
  assert.equal(initial.x,500); assert.equal(initial.y,370); assert.equal(initial.zoom,1);
  read('step(1)'); elements.get('play').onclick(); assert.equal(read('playing'),false);
  assert.equal(read('clock'),dockedAt);
  read('advanceEntrance(.75)');
  const middle=read('entrancePose(entrance)');
  assert.ok(middle.zoom>initial.zoom); assert.ok(middle.power>initial.power);
  read('advanceEntrance(10)');
  const end=read('entrancePose(entrance)');
  assert.equal(end.x,read('sceneAnchor().x')); assert.equal(end.y,252); assert.equal(end.power,1);
  // A resize still docks at the exact anchor used by the pipeline's star.
  read('W=400'); assert.equal(read('entrancePose(entrance).x'),200); read('W=1000');
  read('finishEntrance(true); syncPlayback()'); assert.equal(await pending,true);
  assert.equal(read('entrance'),null); assert.equal(intake.inert,false); assert.equal(classes.has('entering'),false);
  assert.equal(read('clock'),dockedAt); assert.equal(read('playing'),false);
  read('advanceEntrance(10)'); assert.equal(read('clock'),dockedAt);
  const cancelled=read('startEntrance()'); read('cancelEntrance()'); assert.equal(await cancelled,false);
  assert.equal(intake.inert,false); assert.equal(classes.has('entering'),false);
  const old=read('startEntrance()'), replacement=read('startEntrance()'); assert.equal(await old,false);
  read('cancelEntrance()'); assert.equal(await replacement,false);
  read('reducedMotion.matches=true'); assert.equal(await read('startEntrance()'),true);
  assert.equal(read('entrance'),null); assert.equal(read('playing'),false);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_mint_aurora_is_reserved_for_accepted_output():
    run_js(r'''
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/galaxy.js','utf8'), colors=[];
const context=vm.createContext({W:200,H:520,aur:{width:200,height:100},
 x:{save(){},drawImage(){},restore(){}},
 ax:{setTransform(){},clearRect(){},fillRect(){},createLinearGradient:()=>({addColorStop:(p,c)=>{if(p===.25)colors.push(c)}})}});
vm.runInContext(source.slice(source.indexOf('  // ---------- helpers ----------'),source.indexOf('  // ---------- static layers ----------')),context);
vm.runInContext(source.slice(source.indexOf('  function drawAurora('),source.indexOf('  const pathY')),context);
const greenDominates=c=>{const rgb=c.match(/rgba\((\d+),(\d+),(\d+)/);return +rgb[2]>+rgb[3]};
vm.runInContext('drawAurora(0,1,false)',context);
assert.ok(colors.length>0); assert.equal(colors.some(greenDominates),false);
colors.length=0; vm.runInContext('drawAurora(0,1,true)',context);
assert.equal(colors.some(greenDominates),true);
''')
