"""Source-specific, survey-scale Three.js road-plane and camera reconstruction.

This is deliberately NOT a complete monocular digital twin. Four genuinely
surveyed points establish ONE flat metric patch; scene texture contains the
source frame; no invented lanes, signals, buildings or hidden surfaces.
"""
from __future__ import annotations
import json
from html import escape
import streamlit as st
from reconstruction import build_scene
from video_comparison import prepare_source_video

HTML=r'''<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f9fc;color:#172e48;font:13px system-ui,-apple-system,sans-serif}
.bar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin:3px 0 12px}
h3{margin:0;font-size:16px;letter-spacing:-.03em}.muted{font-size:11px;color:#71849b;line-height:1.6}
button{background:white;border:1px solid #d3e0ec;color:#1b5488;border-radius:9px;padding:9px 13px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}
.card{background:#fff;border:1px solid #dce7f0;border-radius:13px;overflow:hidden}
.heading{padding:10px 12px;font-size:12px;font-weight:700}
.viewport{height:330px;position:relative;background:#dbe6ef;overflow:hidden}
video,canvas{display:block;width:100%;height:100%;object-fit:contain}
.viewport video{background:#142437}
.footer{min-height:49px;font-size:11px;color:#657994;line-height:1.5;padding:10px}
.loader{position:absolute;inset:0;display:grid;place-content:center;text-align:center;background:#edf4fc;color:#376b9b;z-index:2}
.loader[hidden]{display:none}
.status{margin:10px 0;padding:12px;background:#fff;border-radius:10px;border:1px solid #dce7f0;color:#425c72;line-height:1.6}
.tools{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
@media(max-width:720px){.grid{grid-template-columns:1fr}.viewport{height:290px}}
</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}</script>
</head><body>
<div class="bar"><div><h3>Surveyed road — source-aligned reconstruction</h3>
<div class="muted">Observed trajectories · Surveyed flat road patch · Approximate camera intrinsics</div></div>
<div class="tools"><select id="mode" aria-label="Observed versus hypothetical" style="padding:9px;border-radius:9px;border:1px solid #d3e0ec"><option value="observed">Observed tracked movement</option><option value="signal">Hypothetical signal + pedestrian crossing</option></select><button id="pause">Play / Pause</button><button id="reset">Restart</button><button id="sourceview">Source view</button><button id="focus">Focus on road</button><button id="top">Top view</button></div></div>
<div class="grid">
<div class="card"><div class="heading">01 · Unmodified real recording</div>
<div class="viewport"><video controls playsinline preload="metadata" id="source" src="__VIDEO__"></video></div>
<div class="footer">Original camera footage controls the replay clock.</div></div>
<div class="card"><div class="heading">02 · Surveyed patch, true-size road surface and observed tracked positions</div>
<div class="viewport" id="view"><div id="loading" class="loader">Building the surveyed 3D road model…</div></div>
<div class="footer">Observed mode replays tracked camera footpoints. Signal concept adds functional hypothetical traffic controls on the surveyed road patch; it is NOT a site-approved design or an accident prediction.</div></div>
</div>
<div class="status" id="stats">Camera-calibration measurements are estimates, not certified road survey or vehicle-speed enforcement data.</div>
<script type="application/json" id="payload">__DATA__</script>
<script type="module">
const data=JSON.parse(document.getElementById("payload").textContent);
const video=document.getElementById("source");
if(!video.getAttribute("src")){
 const parent=video.parentElement;
 parent.innerHTML='<div style="padding:30px;line-height:2">For long videos, use the original source player on the main results page. This 3D replay uses the same recorded timestamps.</div>';
}
try{
 const T=await import("three");
 const {OrbitControls}=await import("three/addons/controls/OrbitControls.js");
 const metric=data.metric_scene;
 if(!metric)throw Error("Surveyed camera plane unavailable.");
 const view=document.getElementById("view");
 const renderer=new T.WebGLRenderer({antialias:true,powerPreference:"low-power"});
 renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.6));
 renderer.outputColorSpace=T.SRGBColorSpace;
 renderer.setClearColor(0xe6f0f5);
 view.appendChild(renderer.domElement);
 const scene=new T.Scene();scene.background=new T.Color(0xe6f0f5);
 scene.add(new T.HemisphereLight(0xffffff,0x7e91a3,2.3));
 const sun=new T.DirectionalLight(0xffe9ce,1.1);
 sun.position.set(-12,27,16);scene.add(sun);
 const imageAspect=data.height/data.width;
 const camera=new T.PerspectiveCamera(2*Math.atan(imageAspect*Math.tan(metric.fov_deg*Math.PI/360))*180/Math.PI,1,.02,1000);
 const R=metric.rotation_cv,t=metric.translation_cv;
 const basis=new T.Matrix4().set(
  R[0][0],R[0][2],-R[0][1], t[0],
  -R[1][0],-R[1][2],R[1][1],-t[1],
  -R[2][0],-R[2][2],R[2][1],-t[2],
  0,0,0,1
 );
 basis.invert().decompose(camera.position,camera.quaternion,new T.Vector3());
 const homePosition=camera.position.clone(),homeQuaternion=camera.quaternion.clone();
 // OrbitControls defaults to upright camera and would strip source camera ROLL,
 // shifting road landmarks despite mathematically correct PnP extrinsics.
 const homeUp=new T.Vector3(0,1,0).applyQuaternion(homeQuaternion);
 camera.up.copy(homeUp);
 // A dedicated, NEVER orbit-controlled source camera preserves solvePnP
 // extrinsics exactly. Free orbit operates on a separate camera instance.
 const sourceCamera=new T.PerspectiveCamera(camera.fov,camera.aspect,.02,1000);
 sourceCamera.position.copy(homePosition);
 sourceCamera.quaternion.copy(homeQuaternion);
 sourceCamera.up.copy(homeUp);
 sourceCamera.updateMatrixWorld(true);
 let useOrbit=false;
 const controls=new OrbitControls(camera,renderer.domElement);
 controls.enabled=false;
 controls.enableDamping=true;
 const center=new T.Vector3(metric.width_m/2,0,-metric.length_m/2);
 // Preserve calibrated camera orientation in SOURCE mode. Re-aiming Orbit
 // controls at the road centre would destroy source-image reprojection.
 const sourceForward=new T.Vector3(0,0,-1).applyQuaternion(homeQuaternion);
 const sourceTarget=homePosition.clone().addScaledVector(sourceForward,30);
 controls.target.copy(sourceTarget);controls.update();
 // The actual road appearance is warped from the original source pixels.
 const texture=new T.TextureLoader().load(metric.texture);
 texture.colorSpace=T.SRGBColorSpace;
 const road=new T.Mesh(new T.PlaneGeometry(metric.width_m,metric.length_m),
   new T.MeshBasicMaterial({map:texture,side:T.DoubleSide}));
 road.rotation.x=Math.PI/2;road.position.set(metric.width_m/2,0,-metric.length_m/2);
 scene.add(road);
 const border=new T.LineLoop(new T.BufferGeometry().setFromPoints([
   new T.Vector3(0,.05,0),new T.Vector3(metric.width_m,.05,0),
   new T.Vector3(metric.width_m,.05,-metric.length_m),new T.Vector3(0,.05,-metric.length_m)
 ]),new T.LineBasicMaterial({color:0x318ce0}));scene.add(border);
 const colors={car:0x3c80c5,truck:0x98abb7,bus:0xe2bd78,motorcycle:0x688d9c,person:0xe1a174,bicycle:0x669a7e};
 const modelTypes={
   car:[1.8,1.5,4.5],truck:[2.45,3.1,8.8],bus:[2.5,3,10],
   motorcycle:[.8,1.2,2.1],person:[.55,1.7,.6],bicycle:[.55,1.5,1.5]
 };
 const models=[];
 for(const track of data.tracks){
    const pts=(track.points||[]).filter(p=>p.length>=7 && p.slice(0,7).every(Number.isFinite));
    if(pts.length<3)continue;
    const dims=modelTypes[track.class]||[1.8,1.5,4.3];
    const group=new T.Group();
    const material=new T.MeshStandardMaterial({color:colors[track.class]||0x5080b5,roughness:.6});
    const hull=new T.Mesh(new T.BoxGeometry(...dims),material);hull.position.y=dims[1]/2;group.add(hull);
    if(track.class!=="person"){
      const cabin=new T.Mesh(new T.BoxGeometry(dims[0]*.7,dims[1]*.28,dims[2]*.62),
        new T.MeshStandardMaterial({color:0xb7d8e8,roughness:.4}));
      cabin.position.y=dims[1]*.92;group.add(cabin);
    }
    group.visible=false;scene.add(group);
    models.push({track,pts,group,lastAngle:null});
 }
 // The proposed signal experiment uses the SAME surveyed road-plane geometry
 // but independent modeled demand/time. It is never labeled real observation.
 const simData=data.control_scenario||null;
 const intervention=new T.Group();scene.add(intervention);
 const laneCount=simData?.inputs?.lanes||2;
 const guide=new T.MeshBasicMaterial({color:0xf8faf6,transparent:true,opacity:.85});
 if(simData){
   for(let boundary=1;boundary<laneCount;boundary++){
     const marking=new T.Mesh(new T.BoxGeometry(.08,.04,metric.length_m*.82),guide);
     marking.position.set(boundary*metric.width_m/laneCount,.06,-metric.length_m/2);
     intervention.add(marking);
   }
   // Stop line 10 metres upstream of the hypothetical crossing.
   const stop=new T.Mesh(new T.BoxGeometry(metric.width_m*.94,.06,.23),guide);
   stop.position.set(metric.width_m/2,.11,-metric.length_m/2+10);
   intervention.add(stop);
   for(let shift=-1.6;shift<=1.6;shift+=.7){
     const stripe=new T.Mesh(new T.BoxGeometry(metric.width_m*.9,.055,.36),guide);
     stripe.position.set(metric.width_m/2,.12,-metric.length_m/2+shift);
     intervention.add(stripe);
   }
   const pole=new T.Mesh(new T.CylinderGeometry(.09,.11,4,10),
     new T.MeshStandardMaterial({color:0x536474}));
   pole.position.set(-.55,2,-metric.length_m/2+9.6);intervention.add(pole);
   const signal=new T.Mesh(new T.BoxGeometry(.48,1.4,.44),
     new T.MeshStandardMaterial({color:0x243847}));
   signal.position.set(-.55,4.35,-metric.length_m/2+9.6);intervention.add(signal);
 }
 const simCars=new Map(),simPeople=new Map();
 function createBody(id,kind){
    const width=kind==="person"?.45:1.7;
    const height=kind==="person"?1.7:1.4;
    const length=kind==="person"?.45:4.3;
    const group=new T.Group();
    const hull=new T.Mesh(new T.BoxGeometry(width,height,length),
      new T.MeshStandardMaterial({color:kind==="person"?0xd89d62:
       [0x4b91c1,0xd68f7b,0x8fa8b0][id%3],roughness:.65}));
    hull.position.y=height/2;group.add(hull);intervention.add(group);
    return group;
 }
 function setScenarioFrame(frame){
   if(!simData||!frame)return 0;
   const visibleCars=new Set(),visiblePeople=new Set();
   for(const [id,roadX,lane,v] of frame.cars){
     // Preserve true metres, clipping the 140 m simulation to the surveyed
     // segment instead of stretching all traffic into a 25 m patch.
     const z=-metric.length_m/2-roadX;
     if(z>0||z< -metric.length_m)continue;
     let body=simCars.get(id);
     if(!body){body=createBody(id,"car");simCars.set(id,body)}
     body.position.set((lane+.5)*metric.width_m/laneCount,.06,z);
     body.visible=true;visibleCars.add(id);
   }
   for(const [id,walkY,status] of frame.people){
     if(status!=="crossing")continue;
     let body=simPeople.get(id);
     if(!body){body=createBody(id,"person");simPeople.set(id,body)}
     body.position.set(metric.width_m/2+walkY,.06,-metric.length_m/2);
     body.visible=true;visiblePeople.add(id);
   }
   for(const [id,obj] of simCars)if(!visibleCars.has(id))obj.visible=false;
   for(const [id,obj] of simPeople)if(!visiblePeople.has(id))obj.visible=false;
   signalState(frame.phase);
   return visibleCars.size;
 }
 let signalIndicator=null;
 if(simData){
   signalIndicator=new T.Mesh(new T.SphereGeometry(.18,12,8),
     new T.MeshBasicMaterial({color:0x28c975}));
   signalIndicator.position.set(-.55,4.45,-metric.length_m/2+9.33);
   intervention.add(signalIndicator);
 }
 function signalState(phase){
   if(!signalIndicator)return;
   const allowed=phase==="vehicle_green";
   signalIndicator.material.color.setHex(allowed?0x29df67:phase==="vehicle_yellow"?0xf4be31:0xe8473d);
 }
 let simulatedClock=0;
 const simFrames=simData?.managed?.frames||[];
 document.getElementById("mode").disabled=!simData;
 if(!simData)document.getElementById("mode").options[1].textContent=
   "Signal concept requires a surveyed patch >= 24 m long and >= 5 m wide";
 intervention.visible=false;
 function positionAt(points,seconds){
   if(seconds<points[0][0]||seconds>points[points.length-1][0])return null;
   let lo=0,hi=points.length-1;
   while(lo<hi){const m=(lo+hi)>>1;if(points[m][0]<seconds)lo=m+1;else hi=m}
   const next=points[lo],prev=points[Math.max(0,lo-1)];
   if(next===prev)return [next[5],next[6]];
   if(next[0]-prev[0]>1.35)return null; // no teleport over tracker gaps
   const q=(seconds-prev[0])/(next[0]-prev[0]);
   return [prev[5]+q*(next[5]-prev[5]),prev[6]+q*(next[6]-prev[6])];
 }
 let time=0,playing=true,last=performance.now(),nativeVideo=!!video.getAttribute("src");
 function update(now){
   const chosen=document.getElementById("mode").value;
   const dt=Math.max(0,Math.min(.10,(now-last)/1000));
   if(chosen==="signal"&&simData){
     if(playing)simulatedClock+=dt;
     if(simulatedClock>=simData.inputs.seconds)simulatedClock=0;
   } else {
     if(nativeVideo)time=video.currentTime||0;
     else if(playing)time+=dt;
     if(time>data.duration)time=0;
   }
   last=now;
   let count=0;
   for(const m of models){
     const pos=positionAt(m.pts,time);
     if(!pos||chosen==="signal"){m.group.visible=false;continue}
     m.group.visible=true;count++;
     m.group.position.set(pos[0],.06,-pos[1]);
     const old=positionAt(m.pts,Math.max(0,time-.35));
     if(old){
       const dx=pos[0]-old[0],dz=-(pos[1]-old[1]);
       if(Math.hypot(dx,dz)>.04){
         const angle=Math.atan2(dx,dz);
         m.group.rotation.y=angle;
       }
     }
   }
   const scenario=chosen==="signal"&&simData;
   intervention.visible=Boolean(scenario);
   let extra="";
   if(scenario){
     const index=Math.min(simFrames.length-1,Math.floor(simulatedClock*2));
     const frame=simFrames[Math.max(0,index)];
     const n=setScenarioFrame(frame);
     extra=" · HYPOTHETICAL "+(frame?.phase||"no phase").replaceAll("_"," ")+
       " · "+n+" simulated vehicles on surveyed patch · independent "+simulatedClock.toFixed(1)+"s clock";
   }
   if(useOrbit)controls.update();
   renderer.render(scene,useOrbit?camera:sourceCamera);
   document.getElementById("stats").textContent=
     "Surveyed flat patch "+metric.width_m.toFixed(1)+" m × "+metric.length_m.toFixed(1)+
     " m · Camera fit RMSE "+metric.reprojection_rmse_px.toFixed(1)+
     " px · "+(scenario?"Concept only":count+" observed tracked meshes at "+time.toFixed(1)+"s")+
     extra+" · Object meshes/FOV and interventions are estimates, NOT surveyed design.";
   requestAnimationFrame(update);
 }
 // Only a PROPER right-handed rigid transform can be decomposed into
 // Three.js camera quaternions. Use (x,height,-road_distance) in world.
 // Match ORIGINAL aspect in a centered viewport, not the responsive card ratio.
 const projectionNote=document.createElement("div");
 projectionNote.style.cssText="position:absolute;right:10px;bottom:8px;padding:5px 8px;border-radius:6px;background:#183750d9;color:white;font-size:10px;pointer-events:none;z-index:3";
 projectionNote.id="projectionStatus";
 view.appendChild(projectionNote);
 const corners3D=[
    new T.Vector3(0,0,0),new T.Vector3(metric.width_m,0,0),
    new T.Vector3(metric.width_m,0,-metric.length_m),
    new T.Vector3(0,0,-metric.length_m)
 ];
 const validateProjection=()=>{
   // project() reads the camera's cached inverse matrix. Geometry is only
   // trustworthy after synchronizing the current pose into matrixWorld.
   sourceCamera.updateMatrixWorld(true);
   const reproject=corners3D.map(p=>p.clone().project(sourceCamera));
   const pixels=reproject.map(v=>[(v.x+1)*data.width/2,(1-v.y)*data.height/2]);
   const squared=pixels.map((p,i)=>
      Math.pow(p[0]-data.calibration.points[i][0]*data.width,2)+
      Math.pow(p[1]-data.calibration.points[i][1]*data.height,2));
   const rmse=Math.sqrt(squared.reduce((a,b)=>a+b,0)/squared.length);
   projectionNote.textContent="Three.js source reprojection: "+rmse.toFixed(1)+" px RMSE";
   projectionNote.style.background=rmse>18?"#96362ed9":"#183750d9";
   return rmse;
 };
 const resize=()=>{
   const w=Math.max(1,view.clientWidth),h=Math.max(1,view.clientHeight);
   renderer.setSize(w,h,false);
   const ratio=data.width/data.height;
   const vwidth=Math.min(w,h*ratio),vheight=vwidth/ratio;
   renderer.setViewport((w-vwidth)/2,(h-vheight)/2,vwidth,vheight);
   camera.aspect=ratio;camera.updateProjectionMatrix();
   sourceCamera.aspect=ratio;sourceCamera.updateProjectionMatrix();
   validateProjection();
 };
 new ResizeObserver(resize).observe(view);resize();
 document.getElementById("sourceview").onclick=()=>{
   useOrbit=false;controls.enabled=false;
   camera.position.copy(homePosition);camera.quaternion.copy(homeQuaternion);
   camera.up.copy(homeUp);
   controls.target.copy(sourceTarget);controls.update();
   sourceCamera.position.copy(homePosition);
   sourceCamera.quaternion.copy(homeQuaternion);
   sourceCamera.updateMatrixWorld(true);
   validateProjection();
 };
 document.getElementById("focus").onclick=()=>{
   useOrbit=true;controls.enabled=true;
   camera.up.set(0,1,0);
   camera.position.set(metric.width_m*1.6,Math.max(16,metric.length_m*.78),
                       -metric.length_m/2+metric.length_m*.85);
   controls.target.copy(center);controls.update();
 };
 document.getElementById("top").onclick=()=>{
   useOrbit=true;controls.enabled=true;
   camera.up.set(0,0,-1);
   camera.position.set(metric.width_m/2,Math.max(45,metric.length_m*1.75),-metric.length_m/2+.01);
   controls.target.copy(center);controls.update();
 };
 document.getElementById("pause").onclick=()=>{
   if(document.getElementById("mode").value==="signal"){playing=!playing;return}
   if(nativeVideo){if(video.paused)video.play().catch(()=>{});else video.pause()}
   else playing=!playing;
 };
 document.getElementById("mode").onchange=e=>{
   playing=true;simulatedClock=0;time=0;last=performance.now();
   if(e.target.value==="signal"&&nativeVideo)video.pause();
 };
 document.getElementById("reset").onclick=()=>{
   time=0;simulatedClock=0;if(nativeVideo)video.currentTime=0;last=performance.now()
 };
 document.getElementById("loading").hidden=true;
 requestAnimationFrame(update);
}catch(error){
 document.getElementById("loading").textContent="Cannot render surveyed scene: "+String(error).slice(0,220);
 console.error(error);
}
</script></body></html>'''


def show_surveyed_scene(job,snapshot,calibration,fov_deg):
    from pathlib import Path
    from html import escape
    selected={**snapshot,
              "calibration":{"points":calibration.points,
                             "width_m":calibration.width_m,
                             "length_m":calibration.length_m},
              "camera_fov_deg":fov_deg}
    try:
        scene=build_scene(job,selected,max_points=20000,include_annotated_video=False)
        if scene["metric_scene"] is None:
            st.warning("Calibration cannot produce a valid metric road-plane projection; check your surveyed corners.")
            return
        source_uri,status=prepare_source_video(job,max_inline_bytes=14*1024*1024)
    except (ValueError,OSError,RuntimeError) as exc:
        st.error("Could not build surveyed 3D scene: "+str(exc))
        return
    st.caption("Real-world dimensions are used only for your surveyed flat road patch. "
               "Other objects remain approximate. Orbit/Top shows a measured planar patch, not hidden 3D terrain.")
    html=HTML.replace("__VIDEO__",escape(source_uri or "",quote=True)).replace(
      "__DATA__",json.dumps(scene,separators=(",",":")).replace("</","<\\/"))
    st.components.v1.html(html,height=535,scrolling=False)
    if scene["control_scenario"]:
        st.markdown("**What changes in the hypothetical intervention?**")
        st.write("A marked pedestrian crossing and phased traffic control are overlaid on "
                 "your surveyed road patch. Vehicles stop for the pedestrian WALK interval, "
                 "people cross, and vehicles resume when the controller returns to green. "
                 "This is a design EXPERIMENT, not a verified requirement at the filmed location.")
        before=sim["baseline"]["metrics"]
        after=sim["managed"]["metrics"]
        cols=st.columns(3)
        for col,label,key,unit in (
            (cols[0],"Pedestrian wait","mean_pedestrian_wait_s","s"),
            (cols[1],"Vehicle travel time","mean_vehicle_travel_s","s"),
            (cols[2],"Peak stopped queue","max_waiting_vehicles","cars"),
        ):
            previous=before.get(key)
            current=after.get(key)
            def display(value):
                return "N/A" if value is None else f"{value:g} {unit}"
            col.metric(label,display(current),help="Model-only outcome, NOT measured road performance.")
            col.caption("Uncontrolled concept: "+display(previous))
        st.caption("Both scenarios use equal SEEDED ASSUMED demand and simplified two-dimensional "
                   "traffic rules. The 3D camera/road surface comes from your survey; "
                   "model traffic demand, signal timing and safety outcomes are not reconstructed "
                   "from the original video or validated for construction.")
    if not source_uri:
        st.caption(status+" The full original video is available in the analyzed-video results above.")
