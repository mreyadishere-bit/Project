"""Recorded source video next to a genuinely animated traffic-signal 3D concept.

The traffic simulation has its OWN clock because adding a crossing changes
the trajectories. The left video remains untouched, serving as observational
evidence, not a counterfactual baseline. All modeled inputs are labeled.
"""
from __future__ import annotations

from dataclasses import replace
from html import escape
import json
import streamlit as st
import streamlit.components.v1 as components
from traffic_control_sim import ControlInputs, simulate
from video_comparison import prepare_source_video

VIEW_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
*{box-sizing:border-box}body{font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f7f9fc;color:#142a42;margin:0}
.top{display:flex;justify-content:space-between;align-items:center;gap:9px;padding:8px 0 12px;flex-wrap:wrap}
.top strong{font-size:15px;letter-spacing:-.03em}.muted{color:#71859d;font-size:11px;line-height:1.6}
button{border:1px solid #dae4ef;border-radius:10px;padding:9px 15px;background:#fff;cursor:pointer;color:#20598f;font-weight:600}
button:hover{background:#ecf5ff}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.card{background:white;border:1px solid #dce6f1;border-radius:18px;overflow:hidden}
.head{padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.head strong{font-size:13px}.head small{font-size:10px;color:#748ba1}
.screen{height:355px;background:#d0e6ef;position:relative;overflow:hidden}
video,canvas{display:block;height:100%;width:100%;object-fit:contain}
.screen video{background:#162332}
.screen canvas{cursor:grab}
.foot{padding:10px 14px;line-height:1.55;font-size:11px;color:#6c8099;min-height:56px}
.loading{position:absolute;inset:0;background:#e8f1fa;display:grid;place-content:center;text-align:center;color:#36628a;z-index:4;padding:20px}
.loading[hidden]{display:none}.spinner{border:3px solid #cddceb;border-top-color:#2579cc;width:30px;height:30px;border-radius:50%;animation:turn .9s linear infinite;margin:0 auto 12px}
@keyframes turn{to{transform:rotate(360deg)}}
.status{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:10px 13px;background:#f0f6fd;flex-wrap:wrap}
.phase{font-weight:700;color:#194b78}.phase.red{color:#bd4c3a}.phase.green{color:#158062}
.timeline{display:flex;gap:9px;align-items:center;padding:12px 0;flex-wrap:wrap}
.timeline input{flex:1;min-width:130px;accent-color:#2778d0}
.note{background:#fff8ea;border:1px solid #f1e6ca;padding:12px 14px;border-radius:12px;color:#705d3d;font-size:11px;line-height:1.6}
.fallback{display:none;position:absolute;inset:0;background:#f1f5fa;z-index:3;padding:30px;text-align:center;align-items:center;justify-content:center;flex-direction:column;gap:12px}
.fallback input{font-size:11px;max-width:100%}
@media(max-width:680px){.grid{grid-template-columns:1fr}.screen{height:300px}}
</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}</script>
</head><body>
<div class="top"><div><strong>From observation to an engineered concept</strong><div class="muted">Real footage on the left · Independent hypothetical traffic-control simulation on the right</div></div>
<div><button id="toggle">Pause simulation</button> <button id="restart">Restart</button> <button id="topview">Top view</button></div></div>
<div class="grid">
<div class="card"><div class="head"><strong>01 · Original road footage</strong><small>Actual recording</small></div>
<div class="screen"><video id="source" controls playsinline preload="metadata" src="__SOURCE__"></video>
<div id="fallback" class="fallback"><strong>Open your original recording locally</strong><span class="muted">This long recording isn't embedded in the page. Select the same video; it stays on your device.</span><input id="file" type="file" accept="video/*"/></div></div>
<div class="foot">Observe the real problem at the indicated timestamps. The video has not been altered.</div></div>
<div class="card"><div class="head"><strong>02 · 3D intervention concept</strong><small>Modeled road, signals, cars & pedestrians</small></div>
<div class="screen" id="simulation"><div class="loading" id="loading"><div class="spinner"></div><strong>Building the 3D environment…</strong><div class="muted">Loading vehicles, traffic controls and the simulation</div></div></div>
<div class="status"><span id="phase" class="phase"></span><span id="control" class="muted"></span><span id="agents" class="muted" aria-live="off"></span></div>
<div class="foot">Notice the crosswalk, stop line and changing traffic signals. The vehicles queue for WALK, pedestrians cross, and driving resumes after clearance. This is an illustrative road design — not reconstructed footage.</div></div>
</div>
<div class="timeline"><button id="play">Pause</button><span id="time">00:00</span>
<input id="seek" type="range" min="0" max="1000" value="0" aria-label="Simulation timeline"/><span class="muted" id="duration"></span>
<select id="rate" aria-label="Simulation playback speed"><option value="1">1×</option><option value="2">2×</option><option value="4">4×</option></select></div>
<div class="note">This is a <strong>hypothetical intervention</strong>, not an automatically approved crossing, a measured reduction in crashes, or a reconstruction of this particular road's geometry. Signal phases and travel behavior use clearly stated assumptions. The simulated video clock is intentionally independent of the original after changing traffic rules.</div>
<script id="scene" type="application/json">__DATA__</script>
<script type="module">
const D=JSON.parse(document.getElementById("scene").textContent);
const original=document.getElementById("source");
const fallback=document.getElementById("fallback");
if(!original.getAttribute("src"))fallback.style.display="flex";
original.addEventListener("error",()=>fallback.style.display="flex");
// Match iframe height to responsive content instead of clipping mobile scene.
const reportHeight=()=>window.parent.postMessage({
 isStreamlitMessage:true,type:"streamlit:setFrameHeight",
 height:Math.ceil(document.body.scrollHeight+8)
},"*");
new ResizeObserver(reportHeight).observe(document.body);
reportHeight();
document.getElementById("file").onchange=e=>{
 const file=e.target.files?.[0];if(!file)return;
 original.src=URL.createObjectURL(file);fallback.style.display="none";
 original.load();
};
try{
 const THREE=await import("three");
 const {OrbitControls}=await import("three/addons/controls/OrbitControls.js");
 const screen=document.getElementById("simulation");
 const render=new THREE.WebGLRenderer({antialias:true,powerPreference:"low-power"});
 render.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
 render.shadowMap.enabled=true;render.shadowMap.type=THREE.PCFSoftShadowMap;
 render.setClearColor(0xdbe9f0);
 screen.appendChild(render.domElement);
 const scene=new THREE.Scene();scene.background=new THREE.Color(0xc8dfeb);scene.fog=new THREE.Fog(0xc8dfeb,130,310);
 scene.add(new THREE.HemisphereLight(0xffffff,0x7a867e,2.1));
 const sun=new THREE.DirectionalLight(0xfff4d9,2.2);sun.position.set(-25,60,-25);
 sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-110;sun.shadow.camera.right=110;
 sun.shadow.camera.top=110;sun.shadow.camera.bottom=-110;scene.add(sun);
 const cam=new THREE.PerspectiveCamera(49,1,.1,350);
 cam.position.set(18,20,32);
 const orbit=new OrbitControls(cam,render.domElement);
 orbit.target.set(-1,0,0);orbit.enableDamping=true;orbit.maxPolarAngle=Math.PI/2.05;
 orbit.minDistance=13;orbit.maxDistance=145;orbit.update();
 const material=(color)=>new THREE.MeshStandardMaterial({color,roughness:.7,metalness:.02});
 const gray=material(0x394657),sidewalk=material(0xb2bec5),grass=material(0x8db18c),
 white=material(0xf6f7eb),dark=material(0x28323b),blue=material(0x4188c1),skin=material(0xd8ac80);
 const red=material(0xb94b4b),amber=material(0xe0b153),green=material(0x35b879);
 function obj(g,m,x=0,y=0,z=0,parent=scene){
   const mesh=new THREE.Mesh(g,m);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;
   parent.add(mesh);return mesh;
 }
 const laneCenters=D.inputs.lanes===1?[0]:D.inputs.lanes===2?[-2.2,2.2]:[-4,0,4];
 const laneBoundaries=laneCenters.slice(1).map((v,i)=>(v+laneCenters[i])/2);
 const ground=obj(new THREE.BoxGeometry(220,.4,70),grass,0,-.35,0);
 obj(new THREE.BoxGeometry(155,.1,14),gray,0,.02,0);
 for(const z of [-9,9])obj(new THREE.BoxGeometry(155,.28,4),sidewalk,0,.1,z);
 for(const x of [-66,-56,-46,-36,-26,-16,14,24,34,44,54,64])
   for(const z of laneBoundaries)
     obj(new THREE.BoxGeometry(4,.04,.11),white,x,.10,z);
 // Zebra crossing perpendicular to the vehicle travel direction.
 for(let z=-5.75;z<=5.75;z+=1.15)
   obj(new THREE.BoxGeometry(5.2,.06,.66),white,0,.13,z);
 obj(new THREE.BoxGeometry(.23,.07,13),white,-10,.14,0);
 for(const x of [-67,67])for(const z of [-7,7]){
   obj(new THREE.CylinderGeometry(.10,.14,3,8),material(0x6d6452),x,1.7,z);
   obj(new THREE.DodecahedronGeometry(2.3,0),material(0x658e6b),x,5,z);
 }
 function createLight(x,z){
    const g=new THREE.Group();scene.add(g);
    obj(new THREE.CylinderGeometry(.10,.14,6,8),dark,x,3,z,g);
    obj(new THREE.BoxGeometry(.65,2.2,.68),dark,x,6.9,z,g);
    const bulbs=[red,amber,green].map((mat,i)=>obj(new THREE.SphereGeometry(.23,12,8),mat,x,7.55-i*.63,z+.36,g));
    return bulbs;
 }
 const bulbs=createLight(-10,-7);
 const pedestrianLights=[obj(new THREE.BoxGeometry(.85,1.1,.28),dark,0,3.1,8)];
 const pedIndicator=obj(new THREE.BoxGeometry(.5,.55,.08),red,0,3.15,8.2);
 function carMesh(id,lane){
   const group=new THREE.Group();scene.add(group);
   const hues=[0x4f86c5,0xc27b70,0x7c9f98,0xe4c895,0x9ca9b6];
   const paint=material(hues[id%hues.length]);
   obj(new THREE.BoxGeometry(4.6,1.1,1.9),paint,0,.9,0,group);
   obj(new THREE.BoxGeometry(2.65,.85,1.7),paint,-.35,1.8,0,group);
   obj(new THREE.BoxGeometry(.07,.47,1.50),material(0x9ed2e6),-1.6,1.81,0,group);
   for(const ax of [-1.5,1.5])for(const side of [-1,1]){
     const wheel=obj(new THREE.CylinderGeometry(.47,.47,.19,10),dark,ax,.45,side*1.,group);
     wheel.rotation.x=Math.PI/2;
   }
   return group;
 }
 function humanMesh(id){
   const group=new THREE.Group();scene.add(group);
   const shirt=material([0x367fa4,0x9576a4,0x699874,0xd49c62][id%4]);
   obj(new THREE.CylinderGeometry(.22,.31,1,7),shirt,0,1,0,group);
   obj(new THREE.SphereGeometry(.22,9,7),skin,0,1.68,0,group);
   for(const x of [-.12,.12])obj(new THREE.BoxGeometry(.12,.55,.12),dark,x,.30,0,group);
   return group;
 }
 const carObjects=new Map(),peopleObjects=new Map();
 let clock=0,playing=true,previous=performance.now(),top=false;
 const frames=D.managed.frames;
 // The first snapshot may precede the first randomly generated vehicle.
 // Start at the first moment with active traffic instead of presenting a blank road.
 const firstActive=frames.find(f=>f.cars.length>0&&f.t>0);
 if(firstActive)clock=firstActive.t;
 function renderFrame(f){
   const seenCars=new Set(),seenPeople=new Set();
   for(const [id,x,lane,speed] of f.cars){
     let body=carObjects.get(id);
     if(!body){body=carMesh(id,lane);carObjects.set(id,body)}
     body.visible=true;body.position.set(x,0,laneCenters[lane]??0);
     seenCars.add(id);
   }
   for(const [id,y,status] of f.people){
     let body=peopleObjects.get(id);
     if(!body){body=humanMesh(id);peopleObjects.set(id,body)}
     body.visible=true;body.position.set(-.5-(id%3)*.7,0,y);
     seenPeople.add(id);
   }
   for(const [id,body] of carObjects)if(!seenCars.has(id))body.visible=false;
   for(const [id,body] of peopleObjects)if(!seenPeople.has(id))body.visible=false;
   document.getElementById("agents").textContent=
     f.cars.length+" vehicles · "+
     f.people.filter(p=>p[2]==="crossing").length+" crossing · "+
     f.people.filter(p=>p[2]==="waiting").length+" waiting";
   const vehicleGo=f.phase==="vehicle_green";
   const vehicleWarn=f.phase==="vehicle_yellow";
   bulbs.forEach((bulb,i)=>{
     const on=i===(vehicleGo?2:vehicleWarn?1:0);
     bulb.material.emissive=new THREE.Color(on?(i===0?0xa42e29:i===1?0xa87925:0x2c933c):0x000000);
     bulb.material.emissiveIntensity=on?1.8:0;
   });
   const walking=f.phase==="pedestrian_walk";
   const clearing=f.phase==="pedestrian_clearance";
   pedIndicator.material=walking?green:clearing?amber:red;
   document.getElementById("phase").textContent=f.phase.replaceAll("_"," ").toUpperCase();
   document.getElementById("phase").className="phase "+(walking||clearing?"red":"green");
   document.getElementById("control").textContent=vehicleGo?"Vehicles GO · Pedestrians WAIT":
      vehicleWarn?"Vehicles YELLOW / STOP · Pedestrians WAIT":
      walking?"Vehicles STOP · Pedestrians may START crossing":
      clearing?"Vehicles STOP · Pedestrians already crossing CLEAR; no new WALK":
      "All-red transition · everyone waits";
 }
 function fit(){
   const box=screen.getBoundingClientRect();
   render.setSize(Math.max(1,box.width),Math.max(1,box.height),false);
   cam.aspect=Math.max(1,box.width)/Math.max(1,box.height);cam.updateProjectionMatrix();
 }
 new ResizeObserver(fit).observe(screen);fit();
 const loading=document.getElementById("loading");
 let drawn=false;
 function draw(now){
   if(playing)clock+=(now-previous)/1000*Number(document.getElementById("rate").value);
   previous=now;
   if(clock>=D.inputs.seconds)clock=0;
   const index=Math.min(frames.length-1,Math.floor(clock*2));
   renderFrame(frames[Math.max(0,index)]);
   orbit.update();render.render(scene,cam);
   if(!drawn){drawn=true;loading.hidden=true}
   document.getElementById("seek").value=Math.floor(clock/D.inputs.seconds*1000);
   document.getElementById("time").textContent=String(Math.floor(clock/60)).padStart(2,"0")+":"+
      String(Math.floor(clock%60)).padStart(2,"0");
   requestAnimationFrame(draw);
 }
 document.getElementById("duration").textContent=Math.floor(D.inputs.seconds/60)+" minute scenario";
 function toggle(){playing=!playing;previous=performance.now();
   document.getElementById("toggle").textContent=playing?"Pause simulation":"Play simulation";
   document.getElementById("play").textContent=playing?"Pause":"Play";
 }
 document.getElementById("toggle").onclick=toggle;
 document.getElementById("play").onclick=toggle;
 document.getElementById("restart").onclick=()=>{clock=firstActive?.t||0;previous=performance.now()};
 document.getElementById("seek").oninput=e=>{clock=Number(e.target.value)/1000*D.inputs.seconds;previous=performance.now()};
 document.getElementById("topview").onclick=()=>{
   top=!top;cam.position.set(top?1:18,top?95:20,top?1:32);
   orbit.target.set(-1,0,0);orbit.update();
   document.getElementById("topview").textContent=top?"Perspective":"Top view";
 };
 requestAnimationFrame(draw);
}catch(error){
 document.getElementById("loading").innerHTML=
 '<strong>3D viewer unavailable.</strong><p>Try a browser with WebGL enabled. Simulation results are still available below.</p>';
 console.error(error);
}
</script></body></html>'''


@st.cache_data(show_spinner=False, max_entries=12)
def cached_simulation(inputs: ControlInputs):
    return simulate(inputs)


@st.cache_data(show_spinner=False, max_entries=12)
def cached_robustness(inputs: ControlInputs):
    from traffic_robustness import assess_robustness
    return assess_robustness(inputs,runs=5)


def show_concept(job, snapshot, interaction_candidates, *, key="traffic_control"):
    observed = bool(interaction_candidates)
    st.markdown("### 3D road intervention — working traffic controls")
    if observed:
        st.info(f"{len(interaction_candidates)} provisional pedestrian–vehicle image-interaction review candidate(s) detected. This supports a site review, NOT an automatic signal design.")
    else:
        st.info("No sustained interaction could be established from tracks. The signal-controlled crossing below is an optional HYPOTHETICAL engineering experiment, not an AI-confirmed necessity.")
    st.write(
        "Explore a simple road environment where cars stop for a red signal, "
        "pedestrians wait for WALK, finish crossing in a clearance phase, "
        "and cars resume. The layout, arrival rates, and timings are assumptions."
    )
    with st.expander("Customize the hypothetical simulation (optional)"):
        c1,c2,c3=st.columns(3)
        speed=c1.slider("Approach speed assumption (km/h)",10,70,36,key=key+"_speed")
        cars=c2.slider("Vehicle arrivals / hour",0,1200,600,step=60,key=key+"_cars")
        peds=c3.slider("Pedestrian arrivals / hour",0,600,240,step=30,key=key+"_peds")
        lanes=st.slider("Illustrative approach lanes (same one-way direction)",1,3,2,key=key+"_lanes")
        a,b,c=st.columns(3)
        green=a.slider("Vehicle green (seconds)",20,70,36,key=key+"_green")
        walk=b.slider("Pedestrian WALK (seconds)",12,30,16,key=key+"_walk")
        clear=c.slider("Pedestrian clearance (seconds)",10,30,12,key=key+"_clear")
    inputs=ControlInputs(speed_kmh=speed,vehicles_per_hour=cars,pedestrians_per_hour=peds,
                         lanes=lanes,green_s=green,walk_s=walk,clearance_s=clear)
    model=cached_simulation(inputs)
    st.session_state[key+"_results"]=model
    with st.spinner("Preparing real source video for 3D comparison…"):
        uri,source_status=prepare_source_video(job)
    html=VIEW_HTML.replace("__SOURCE__",escape(uri or "",quote=True)).replace(
        "__DATA__",json.dumps(model,separators=(",",":")).replace("</","<\\/"))
    components.html(html,height=675,scrolling=False)
    if not uri:
        st.caption(source_status+" Choose the video in the left-hand panel.")
    st.markdown("#### Before vs signal-controlled concept — modeled tradeoffs")
    st.caption("These are results of the simplified simulation under the SAME modeled vehicle/pedestrian demand, not measured improvements at the recorded road.")
    baseline=model["baseline"]["metrics"];managed=model["managed"]["metrics"]
    columns=st.columns(4)
    def value(x):
        return "N/A" if x is None else f"{x:g}" if isinstance(x,(int,float)) else str(x)
    for col,label,key_name in zip(columns,
        ["Average pedestrian wait","Vehicle travel time","Longest vehicle queue","Vehicles completed"],
        ["mean_pedestrian_wait_s","mean_vehicle_travel_s","max_waiting_vehicles","vehicles_completed"]):
        col.metric(label,value(managed[key_name]),help="Modeled value. Baseline: "+value(baseline[key_name]))
        col.caption("Unmanaged model: "+value(baseline[key_name])+
                    (" s" if "time" in key_name or "wait" in key_name else ""))
    st.caption("Other modeled outcomes: "+f"{baseline['pedestrians_completed']} → {managed['pedestrians_completed']} completed crossings; "+
               f"{baseline['vehicle_stopped_seconds']} → {managed['vehicle_stopped_seconds']} total vehicle stopped-seconds.")
    robustness=cached_robustness(inputs)
    st.markdown("#### Does the result persist across different traffic arrival patterns?")
    st.caption("Five paired simulations with distinct random arrival sequences. Each pair has the same modeled demand before and after; ranges are sensitivity checks, NOT measured real-world confidence intervals.")
    fields=[
        ("Pedestrian waiting time (seconds)","mean_pedestrian_wait_s"),
        ("Vehicle travel time (seconds)","mean_vehicle_travel_s"),
        ("Peak vehicle queue (vehicles)","max_waiting_vehicles"),
        ("Vehicles completing modeled road","vehicles_completed"),
    ]
    rows=[]
    for title,identifier in fields:
        result=robustness["metrics"][identifier]
        rows.append({"Modeled quantity":title,
                     "Before (median)":result["baseline_median"],
                     "After (median)":result["managed_median"],
                     "Paired change (median)":result["paired_change_median"],
                     "Change range across trials":str(result["paired_changes_range"]),
                     "Valid comparisons":result["n"]})
    st.dataframe(rows,use_container_width=True,hide_index=True)
    from traffic_robustness import explain_tradeoffs
    st.markdown("**What these model experiments suggest**")
    for sentence in explain_tradeoffs(robustness):
        st.write("• "+sentence)
    st.caption(robustness["disclaimer"])
    st.download_button("Download sensitivity trials (JSON)",
                       json.dumps(robustness,indent=2),
                       file_name="traffic-control-sensitivity.json",
                       mime="application/json",key=key+"_robustness")
    st.download_button("Download reproducible simulation (JSON)",json.dumps(model,indent=2),
        file_name="traffic-control-simulation.json",mime="application/json",
        key=key+"_download")
    st.caption(model["methodology"])
