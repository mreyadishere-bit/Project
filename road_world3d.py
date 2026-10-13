"""Procedural low-poly Blender-style road world, replayed from observed track times.

The source video is a single camera: world road width, mesh geometry, depths
and vehicle dimensions are illustrative until independent survey/calibration.
No predicted crash reductions or photogrammetric digital-twin claim.
"""
from __future__ import annotations
import json

import streamlit as st

from road_advice import road_report
from reconstruction import build_scene

VIEWER = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:#283c55}
*{box-sizing:border-box}body{margin:0;background:#f6f9fd;font-size:12px}
.toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:8px 2px 13px}
.heading{font-size:15px;font-weight:750;letter-spacing:-.025em}
.subtle{font-size:11px;color:#7890a6}
.controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
button,select{background:white;border:1px solid #d8e4ef;border-radius:11px;padding:9px 12px;color:#264769;cursor:pointer;font-size:12px}
button.active{background:#e9f3ff;color:#146bc0;border-color:#abd0f1}
button:hover{background:#eef5ff}
#timeline{width:100%;accent-color:#3185de;margin:5px 0 13px}
.layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
.panel{border-radius:17px;border:1px solid #dce7f2;overflow:hidden;background:white}
.panel-head{display:flex;align-items:center;justify-content:space-between;padding:13px 15px}
.panel-head strong{font-size:13px}
.panel-head span{font-size:10px;color:#7f90a7}
.viewport{height:340px;background:linear-gradient(#b2d7e7,#eef5f7);position:relative}
.viewport canvas{width:100%;height:100%;display:block;cursor:grab}
.panel-foot{padding:12px 15px;color:#72889c;font-size:11px;border-top:1px solid #edf2f6;line-height:1.5}
.control-panel{display:flex;gap:12px;flex-wrap:wrap;align-items:center;background:#fff;border:1px solid #dfe9f3;border-radius:13px;padding:12px;margin-top:12px}
.control-panel label{font-size:11px;color:#596f87}
#rate{width:150px;accent-color:#287fce}
.explainer{font-size:11px;color:#7e8b9a;line-height:1.55;margin:12px 3px}
#error{display:none;background:#fee;border:1px solid #f3c9c4;border-radius:12px;padding:15px;color:#a33}
@media(max-width:690px){.layout{grid-template-columns:repeat(2,minmax(300px,1fr));overflow-x:auto;scroll-snap-type:x mandatory}.panel{scroll-snap-align:start}.viewport{height:275px}}
</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}</script>
</head><body>
<div class="toolbar">
<div><div class="heading">Road Studio · 3D scenario</div><div class="subtle">Curved roadway · Low-poly vehicles · Video-timed motion · Experimental reconstruction</div></div>
<div class="controls"><button id="play">Pause</button><button id="resetTime">Restart</button><span id="time">00:00</span>
<select id="camera" aria-label="Camera view"><option value="source">Source-inspired</option><option value="orbit">Orbit 3D</option><option value="top">Top view</option></select></div></div>
<input id="timeline" type="range" min="0" max="1000" value="0" aria-label="Video time scrubber">
<div class="layout">
<div class="panel"><div class="panel-head"><strong>01 · Observed trajectories</strong><span>Recorded timestamps</span></div><div class="viewport" id="before"></div><div class="panel-foot">Modeled 3D environment; moving agents follow recorded image-space tracks approximately.</div></div>
<div class="panel"><div class="panel-head"><strong>02 · Proposed scenario</strong><span id="scenarioTitle">Baseline</span></div><div class="viewport" id="after"></div><div class="panel-foot">Same road and camera. Intervention changes are visual hypotheses, not predicted safety outcomes.</div></div>
</div>
<div class="control-panel">
<label for="intervention">Explore proposed change</label><select id="intervention"></select>
<label for="rate">What-if speed multiplier</label><input id="rate" type="range" min="45" max="125" step="5" value="100">
<strong id="rateText">100%</strong><button id="reset">Reset scenario</button>
</div>
<div class="explainer" id="limitations"></div>
<div id="error"></div>
<script type="application/json" id="sceneData">__SCENE__</script>
<script type="module">
try {
const THREE=await import("three");
const {OrbitControls}=await import("three/addons/controls/OrbitControls.js");
const data=JSON.parse(document.getElementById("sceneData").textContent);
const opts=[{id:"none",title:"Original road · no intervention"},...data.options];
const selector=document.getElementById("intervention");
for (const o of opts){const el=document.createElement("option");el.value=o.id;el.textContent=o.title;selector.append(el);}
selector.value=data.initialOption||"none";
let intervention=selector.value,speedRatio=1,playing=true,clock=0,last=performance.now();
const pal={road:0x343b49,shoulder:0x727d89,grass:0x8eb189,barrier:0xb2c7c9,
 car:[0x3b7fc6,0x4b9d97,0xb68666,0x6c77a9,0xc87b86],truck:[0xe9e9de,0xb9c6d2],bus:[0xf5d39e],
 motorcycle:[0xc58f56],bicycle:[0x658f9e],person:[0xcc7285]};
const vehicleNames=new Set(["car","bus","truck","motorcycle","bicycle"]);
const worlds=[];
const material=(col,metalness=0)=>new THREE.MeshStandardMaterial({color:col,roughness:.79,metalness});
const asphalt=material(pal.road),median=material(0x72877a),white=material(0xe9eef0),
 grass=material(pal.grass),barrier=material(pal.barrier,.15),treeGreen=[0x56825e,0x63996b,0x497a5b,0x74a278],
 lights=material(0xffefc3),signBlue=material(0x3a84bb);
function roadX(z){return 5.4*Math.sin(z/67)+.023*z}
function mesh(parent,geo,mat,x=0,y=0,z=0){const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m}
function roadRibbon(scene,from,to,mat,height=0.015,width=1){
  const vertices=[],idx=[],n=90;
  for(let j=0;j<=n;j++){let z=j/n*155,x=roadX(z);vertices.push(x+from,height,z,x+to,height,z)}
  for(let i=0;i<n;i++){let k=2*i;idx.push(k,k+1,k+2,k+1,k+3,k+2)}
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(vertices,3));g.setIndex(idx);g.computeVertexNormals();
  const m=new THREE.Mesh(g,mat);m.receiveShadow=true;scene.add(m);return m
}
function roadMark(scene,offset,start,end,col=white){
 const steps=18;
 for(let i=0;i<steps;i++){
    const z=i*9+start;
    if(z>end)break;
    const mark=mesh(scene,new THREE.BoxGeometry(.13,.036,4.5),col,roadX(z)+offset,.067,z+2);
    mark.castShadow=false
 }
}
function lowPolyCar(type,color){
 const group=new THREE.Group();
 const heavy=type==="truck"||type==="bus";
 const bike=type==="motorcycle"||type==="bicycle";
 const len=heavy?9:bike?2.8:4.8;
 const wid=heavy?2.45:bike?.9:2.05;
 const h=heavy?3:bike?.75:1.35;
 const base=material(color,.18);
 const tinted=material(0x9bc2db,.12);
 if(bike){
   mesh(group,new THREE.BoxGeometry(wid,.38,len*.55),base,0,.9,0);
   mesh(group,new THREE.BoxGeometry(.28,.65,.34),material(0x343c47),0,1.2,0);
 }else{
   mesh(group,new THREE.BoxGeometry(wid,h*.57,len),base,0,.49+h*.28,0);
   if(heavy){
     mesh(group,new THREE.BoxGeometry(wid*.98,h*.68,len*.72),material(type==="bus"?0xf1d5a1:0xc4d4df),0,1.2+h*.3,len*.12);
     mesh(group,new THREE.BoxGeometry(wid*.78,.65,.08),tinted,0,2.25,-len*.31);
   }else{
     mesh(group,new THREE.BoxGeometry(wid*.78,h*.52,len*.50),base,0,1.05+h*.3,-len*.04);
     mesh(group,new THREE.BoxGeometry(wid*.75,.45,.1),tinted,0,1.5,-len*.30);
     mesh(group,new THREE.BoxGeometry(wid*.75,.38,.1),tinted,0,1.4,len*.23);
   }
 }
 const wheel=material(0x212630);
 for(const side of [-1,1]){
   for(const zz of [-len*.31,len*.31]){
      const w=mesh(group,new THREE.CylinderGeometry(bike?.31:.48,bike?.31:.48,bike?.15:.23,8),wheel,side*(wid/2+.06),bike?.38:.48,zz);
      w.rotation.z=Math.PI/2;
   }
 }
 const headlights=material(0xeef1bf);
 for(const xx of [-wid*.33,wid*.33]){
    mesh(group,new THREE.BoxGeometry(.3,.22,.08),headlights,xx,.85,-len*.5-.03);
 }
 return group
}
function trees(scene){
 for(let z=6;z<158;z+=11){
   for(const side of [-1,1]){
     let x=roadX(z)+side*(14.5+(z%5)*.8);
     mesh(scene,new THREE.CylinderGeometry(.21,.37,3.4,6),material(0x6c6555),x,1.7,z);
     const green=material(treeGreen[Math.floor(z/11)%treeGreen.length]);
     mesh(scene,new THREE.DodecahedronGeometry(2.65,0),green,x,4.65,z);
     mesh(scene,new THREE.DodecahedronGeometry(1.85,0),green,x+.8,6.2,z+.3);
   }
 }
}
function rails(scene){
 for(const offset of [-12.7,-1.5,1.5,12.7]){
  for(let z=0;z<=155;z+=3.5){
    mesh(scene,new THREE.BoxGeometry(.2,1.4,.18),barrier,roadX(z)+offset,.75,z);
  }
  const pts=[];
  for(let z=0;z<=155;z+=2)pts.push(new THREE.Vector3(roadX(z)+offset,1.38,z));
  const rail=mesh(scene,new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),Math.ceil(155/2),.09,6,false),barrier);
 }
}
function streetlight(scene){
 const grey=material(0x80969e,.22);
 for(let z=15;z<155;z+=28){
  const x=roadX(z);
  mesh(scene,new THREE.CylinderGeometry(.09,.13,8.5,8),grey,x,4.25,z);
  const arm=mesh(scene,new THREE.BoxGeometry(3.5,.13,.16),grey,x+1.75,8.48,z);
  mesh(scene,new THREE.BoxGeometry(.85,.22,.5),lights,x+3.3,8.36,z);
 }
}
function recommendationElements(scene){
 const group=new THREE.Group();scene.add(group);
 const title=selector.value;
 if(title==="markings"||title==="flow"||title==="path"){
   // Enhanced continuity of marking around curve; same geometry as before.
   for(const side of [-1,1]){
     for(let z=26;z<140;z+=6){
       mesh(group,new THREE.BoxGeometry(.17,.042,4.5),white,roadX(z)+side*6.4,.08,z);
     }
   }
 }
 if(title==="lighting"){
   for(let z=14;z<150;z+=27){
      const x=roadX(z)+7;
      mesh(group,new THREE.CylinderGeometry(.075,.1,9,6),barrier,x,4.5,z);
      mesh(group,new THREE.BoxGeometry(1.2,.2,.45),lights,x+1,8.9,z);
   }
 }
 if(title==="speed_review"){
   const post=material(0x6a7988);const face=material(0xeeeeee);
   mesh(group,new THREE.CylinderGeometry(.08,.10,5,8),post,roadX(55)+13.5,2.5,55);
   const plate=mesh(group,new THREE.BoxGeometry(1.8,1.45,.18),face,roadX(55)+13.5,5.6,55);
   // Sign deliberately has no numeric speed: posted limit is unknown.
 }
 return group
}
function setCamera(world,mode){
 const {camera,orbit}=world;
 if(mode==="top"){camera.position.set(0,155,65);orbit.target.set(0,0,69)}
 else if(mode==="orbit"){camera.position.set(90,66,-28);orbit.target.set(2,0,66)}
 else{camera.position.set(-31,31,-42);orbit.target.set(1,0,74)}
 camera.up.set(0,1,0);orbit.update();
}
function viewport(side){
 const target=document.getElementById(side===0?"before":"after");
 const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:"low-power"});
 renderer.setClearColor(0xd8e6ed,1);renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 target.appendChild(renderer.domElement);
 const scene=new THREE.Scene();scene.background=new THREE.Color(0xc4dce6);
 scene.fog=new THREE.Fog(0xc4dce6,155,285);
 scene.add(new THREE.HemisphereLight(0xf7fbff,0x64776e,2.1));
 const sun=new THREE.DirectionalLight(0xffedd2,2.1);sun.position.set(-34,70,-18);
 sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);
 sun.shadow.camera.left=-100;sun.shadow.camera.right=100;
 sun.shadow.camera.top=150;sun.shadow.camera.bottom=-130;scene.add(sun);
 mesh(scene,new THREE.PlaneGeometry(300,440),grass,0,-.10,75).rotation.x=-Math.PI/2;
 roadRibbon(scene,-12.5,-1.65,asphalt);roadRibbon(scene,1.65,12.5,asphalt);
 roadRibbon(scene,-1.62,1.62,median,.02);
 for(const off of [-12.25,-1.85,1.85,12.25])roadMark(scene,off,0,155);
 for(const off of [-7.1,7.1])roadMark(scene,off,0,155);
 trees(scene);rails(scene);streetlight(scene);
 const cam=new THREE.PerspectiveCamera(52,1,.1,400);
 const ctl=new OrbitControls(cam,renderer.domElement);
 ctl.enableDamping=true;ctl.enablePan=false;ctl.minDistance=8;ctl.maxDistance=245;
 ctl.maxPolarAngle=Math.PI*.495;
 const cars=[];
 let idx=0;
 for (const track of data.tracks){
   if(!vehicleNames.has(track.class)||!track.points?.length)continue;
   const types=pal[track.class]||pal.car;
   const colors=Array.isArray(types)?types:[types];
   const obj=lowPolyCar(track.class,colors[idx++%colors.length]);
   obj.visible=false;obj.scale.setScalar(.85);scene.add(obj);
   cars.push({track,obj});
 }
 const extras=recommendationElements(scene);extras.visible=side===1;
 const world={scene,renderer,camera:cam,orbit:ctl,cars,extras,target};
 setCamera(world,document.getElementById("camera").value);
 return world;
}
worlds.push(viewport(0),viewport(1));
// Keep comparison cameras synchronized when orbiting either panel.
let syncingViews=false;
worlds.forEach((w,i)=>w.orbit.addEventListener("change",()=>{
 if(syncingViews)return;
 syncingViews=true;
 const counterpart=worlds[1-i];
 counterpart.camera.position.copy(w.camera.position);
 counterpart.camera.quaternion.copy(w.camera.quaternion);
 counterpart.orbit.target.copy(w.orbit.target);
 counterpart.orbit.update();
 syncingViews=false;
}));
function interpolate(p,t){
 if(!p.length||t<p[0][0]||t>p[p.length-1][0])return null;
 let lo=0,hi=p.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(p[mid][0]<t)lo=mid+1;else hi=mid}
 const a=p[Math.max(0,lo-1)],b=p[lo];if(b===a||b[0]===a[0])return b;
 if(b[0]-a[0]>2.5)return null;
 const f=(t-a[0])/(b[0]-a[0]);
 return [t,...[1,2].map(i=>a[i]+(b[i]-a[i])*f)];
}
function projectedGround(p){
 // Approximate monocular 2D-to-ground mapping. This is not metric calibration.
 const x=Math.min(1,Math.max(0,p[1])),y=Math.min(1,Math.max(0,p[2]));
 const depth=Math.min(1,Math.max(0,(y-.12)/.87));
 const z=8+144*Math.pow(1-depth,1.25);
 const divider=.52-.145*depth;
 let offset;
 if(x<divider){
    const leftEdge=.12-.09*depth;
    offset=-1.8-10.5*Math.min(1,Math.max(0,(divider-x)/Math.max(.05,divider-leftEdge)));
 }else{
    const rightEdge=.85+.13*depth;
    offset=1.8+10.5*Math.min(1,Math.max(0,(x-divider)/Math.max(.05,rightEdge-divider)));
 }
 return new THREE.Vector3(roadX(z)+offset,0,z);
}
function sync(world,side){
 world.extras.visible=side===1 && intervention!=="none";
 // Rebuild only on intervention selection, not every rendered frame.
 const selected=selector.value;
 for(const item of world.cars){
  const {track,obj}=item;
  const points=track.points;
  const ratio=side===1?speedRatio:1;
  const ts=side===1?points[0][0]+(clock-points[0][0])*ratio:clock;
  const p=interpolate(points,ts);
  if(!p){obj.visible=false;continue}
  const pos=projectedGround(p);
  // Hide model predictions clearly outside the mapped road region.
  const off=pos.x-roadX(pos.z);
  if(Math.abs(off)>13){obj.visible=false;continue}
  obj.visible=true;obj.position.copy(pos);
  const bef=interpolate(points,Math.max(points[0][0],ts-.22));
  const aft=interpolate(points,Math.min(points[points.length-1][0],ts+.22));
  if(bef&&aft){
     const a=projectedGround(bef),b=projectedGround(aft);
     const dx=b.x-a.x,dz=b.z-a.z;
     if(Math.hypot(dx,dz)>.02)obj.rotation.y=Math.atan2(-dx,-dz);
  }
 }
}
function size(){
 for(const world of worlds){
  const rect=world.target.getBoundingClientRect();
  if(rect.width===0||rect.height===0)continue;
  world.renderer.setSize(rect.width,rect.height,false);
  world.camera.aspect=rect.width/rect.height;world.camera.updateProjectionMatrix();
 }
}
new ResizeObserver(size).observe(document.body);size();
function animate(now){
 if(playing)clock+=(now-last)/1000;last=now;
 const duration=Math.max(1,data.duration||1);
 if(clock>duration)clock=0;
 document.getElementById("timeline").value=Math.round(1000*clock/duration);
 document.getElementById("time").textContent=String(Math.floor(clock/60)).padStart(2,"0")+":"+String(Math.floor(clock%60)).padStart(2,"0");
 worlds.forEach((w,j)=>{sync(w,j);w.orbit.update();w.renderer.render(w.scene,w.camera)});
 requestAnimationFrame(animate);
}
document.getElementById("limitations").textContent=data.disclaimer+
  " Trajectories map image points approximately onto a stylized 3D road; dimensions, lanes, buildings and depth are not reconstructed from the video.";
document.getElementById("play").onclick=()=>{playing=!playing;last=performance.now();document.getElementById("play").textContent=playing?"Pause":"Play"};
document.getElementById("resetTime").onclick=()=>{clock=0;last=performance.now()};
document.getElementById("timeline").oninput=e=>{clock=Number(e.target.value)*data.duration/1000;last=performance.now()};
document.getElementById("camera").onchange=e=>worlds.forEach(w=>setCamera(w,e.target.value));
document.getElementById("intervention").onchange=e=>{
 intervention=e.target.value;
 document.getElementById("scenarioTitle").textContent=selector.selectedOptions[0]?.textContent||"No changes";
 const w=worlds[1];w.scene.remove(w.extras);w.extras=recommendationElements(w.scene);
 if(intervention==="none"){speedRatio=1;document.getElementById("rate").value=100;document.getElementById("rateText").textContent="100%"}
};
document.getElementById("rate").oninput=e=>{speedRatio=Number(e.target.value)/100;document.getElementById("rateText").textContent=e.target.value+"%"};
document.getElementById("reset").onclick=()=>{selector.value="none";selector.dispatchEvent(new Event("change"));worlds.forEach(w=>setCamera(w,"source"));document.getElementById("camera").value="source"};
selector.dispatchEvent(new Event("change"));requestAnimationFrame(animate);
} catch(error){
 const el=document.getElementById("error");el.style.display="block";el.textContent="The 3D renderer could not start: "+String(error).slice(0,200);
}
</script></body></html>'''


def _suggested_options(report):
    names = {
        "markings": "Enhance lane marking visibility",
        "lighting": "Install improved road lighting (illustrative)",
        "speed_review": "Review speed-management signage (no assumed limit)",
    }
    options = []
    seen = set()
    for rec in report["recommendations"]:
        change = rec.get("simulation_option")
        if change in ("flow", "path"):
            change = "markings"
        if change in names and change not in seen:
            options.append({"id":change,"title":names[change]})
            seen.add(change)
    return options


def render_reconstruction(job, snapshot):
    """Only show actual 3D meshes with video-derived time-indexed agent paths."""
    try:
        scene = build_scene(job, snapshot)
    except (ValueError, OSError) as exc:
        st.info("The 3D scene needs recorded video tracks: " + str(exc))
        return
    if not scene["tracks"]:
        st.warning("No reliable tracks were recorded, so it would be misleading to fabricate an observed vehicle animation.")
        return
    report = road_report(snapshot.get("evidence",{}), snapshot.get("label","video"),
                         getattr(job,"objects_file",None))
    options = _suggested_options(report)
    # Source frame and old photo-plane renderer are deliberately not passed
    # as the 3D floor. Scene architecture consists of REAL 3D meshes.
    data = {
        "tracks": scene["tracks"],
        "duration": scene["duration"],
        "options": options,
        "initialOption": options[0]["id"] if options else "none",
        "disclaimer": report["limitations"],
    }
    html = VIEWER.replace("__SCENE__",json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("</","<\\/"))
    st.iframe(html,height="content",alt="Interactive low-poly 3D roadway with curved carriageways, true 3D vehicles, orbit and top camera views")
    if not options:
        st.caption("No site-specific physical improvement was justified by this footage, so the default 3D model does not pretend one was proven.")
    else:
        st.caption("Available modeled changes come from video-review recommendations. They are illustrative, with no verified crash or travel-time improvement.")
