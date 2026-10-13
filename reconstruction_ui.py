"""Actual tracked image position & timestamps replayed as inspectable 3D proxies.
The image background and geometry are not a complete metric reconstruction.
"""
import json
import streamlit as st
from reconstruction import build_scene

HTML=r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;color:#183150;background:#f7f9fc;font:13px -apple-system,Segoe UI,Arial,sans-serif}
.header{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:11px 13px;background:white;border:1px solid #e4ebf3;border-radius:12px}
button{border:1px solid #d5e1ee;border-radius:9px;padding:8px 11px;background:white;cursor:pointer}
.scene-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}
.scene{min-width:0;background:white;border:1px solid #e5ebf2;border-radius:15px;overflow:hidden}
.scene p{margin:0;padding:12px;font-weight:750}
.scene small{font-weight:400;color:#8394a8}
canvas{width:100%;height:auto;display:block;background:#e5ecf4}
.controls{display:flex;align-items:center;gap:12px;margin:12px 0;flex-wrap:wrap}
.controls input[type=range]{flex:1;accent-color:#2978d9;min-width:140px}
.options{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:14px;border:1px solid #e6eaf1;background:white;border-radius:12px}
.options label{display:block;color:#718096;font-size:11px;margin-bottom:7px}
.options input[type=range]{width:100%;accent-color:#2978d9}
.status{padding:10px;color:#87692b;background:#fff8e8;border-radius:12px;font-size:11px;line-height:1.5}
.error{display:none;padding:12px;color:#b04936}
@media(max-width:600px){.scene-grid{grid-template-columns:repeat(2,minmax(290px,1fr));overflow:auto}.options{grid-template-columns:1fr 1fr}}
</style><script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}</script></head><body>
<div class="header"><strong>Road Vision · Camera-registered 3D</strong><span><button id="reset">Reset camera</button> <button id="pause">Pause</button> <button id="restart">Restart</button></span></div>
<div class="controls">Original timeline <input type="range" id="seek" min="0" max="1000" value="0"><strong id="clock">00:00</strong>
<select id="rate"><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></div>
<div class="scene-grid"><div class="scene"><p>Observed <small>Video tracks + reference photo</small></p><div id="left"></div></div>
<div class="scene"><p>After <small>Editable counterfactual</small></p><div id="right"></div></div></div>
<div class="options">
<div><label>Proposed vehicle speed ratio</label><input id="speed" type="range" min="30" max="130" value="70" step="5"><output id="speedtext">70%</output></div>
<div><label>Illustrative road widening</label><input id="width" type="range" min="0" max="50" value="0" step="5"><output id="widthtext">0% visual shift</output></div>
<div><label>Crosswalk suggestion</label><input id="crossing" type="checkbox" checked> <span>Show crossing</span></div>
<div><label>Original video reference photo</label><input id="photo" type="checkbox" checked> <span>Static frame</span></div>
</div>
<div class="status" id="detail">Camera-aligned projection uses the exact recorded 2D positions and times, with generic approximate 3D bodies. Rotating reveals guessed depth, not recovered hidden surfaces. Model changes are hypothetical; no accident reduction is proved.</div>
<div id="error" class="error"></div>
<script id="payload" type="application/json">__DATA__</script>
<script type="module">
try{
const T=await import('three'),mod=await import('three/addons/controls/OrbitControls.js');
const data=JSON.parse(document.getElementById('payload').textContent);
const W=960,H=Math.max(240,Math.min(640,960*data.height/data.width));
const metric=data.metric_scene;
let playing=true,t=0,rate=1,last=performance.now(),mult=.7,widen=0,cross=true,photo=true;
const specs=metric?
 {car:[1.8,1.5,4.4],truck:[2.5,3.2,9],bus:[2.5,3.2,11],motorcycle:[.9,1.2,2.2],bicycle:[.7,1.5,1.8],person:[.55,1.8,.5]}:
 {car:[42,24,22],truck:[65,32,38],bus:[68,35,38],motorcycle:[22,17,14],bicycle:[19,15,10],person:[11,25,11]};
const palette={car:0x317ed1,truck:0x5b7b9c,bus:0x4a9f9b,motorcycle:0xc4894b,bicycle:0xad8950,person:0xda8b53};
const image=new T.TextureLoader().load(data.image);image.colorSpace=T.SRGBColorSpace;
const groups=[];
for(let j=0;j<2;j++){
const container=document.getElementById(j?'right':'left');
const renderer=new T.WebGLRenderer({antialias:true,powerPreference:'low-power'});
renderer.setPixelRatio(Math.min(1.6,window.devicePixelRatio||1));
renderer.setSize(container.clientWidth,Math.round(container.clientWidth*H/W));
renderer.outputColorSpace=T.SRGBColorSpace;container.appendChild(renderer.domElement);
const scene=new T.Scene();scene.background=new T.Color(0xe7edf6);
scene.add(new T.HemisphereLight(0xffffff,0x61738d,2));
const camera=metric?
 new T.PerspectiveCamera(2*Math.atan(H/W*Math.tan(metric.fov_deg*Math.PI/360))*180/Math.PI,W/H,.05,2000):
 new T.OrthographicCamera(-W/2,W/2,H/2,-H/2,1,2000);
if(metric){
 const R=metric.rotation_cv,t=metric.translation_cv;
 // OpenCV world (x,z,y) -> scene world (x,y,z).
 // OpenCV camera frame (x right,y down,z forward) -> Three frame (x right,y up,z back).
 const A=[[R[0][0],R[0][2],R[0][1]],[-R[1][0],-R[1][2],-R[1][1]],[-R[2][0],-R[2][2],-R[2][1]]];
 const worldToCamera=new T.Matrix4().set(
 A[0][0],A[0][1],A[0][2],t[0],
 A[1][0],A[1][1],A[1][2],-t[1],
 A[2][0],A[2][1],A[2][2],-t[2],
 0,0,0,1);
 worldToCamera.clone().invert().decompose(camera.position,camera.quaternion,new T.Vector3());
} else {camera.position.set(0,0,900);camera.lookAt(0,0,0);}
const ctl=new mod.OrbitControls(camera,renderer.domElement);ctl.enableDamping=true;
if(metric){
 const facing=new T.Vector3(0,0,-1).applyQuaternion(camera.quaternion);
 ctl.target.copy(camera.position).addScaledVector(facing,40);
 ctl.update();
}
const material=metric?new T.MeshStandardMaterial({map:new T.TextureLoader().load(metric.texture),side:T.DoubleSide,roughness:.95}):
new T.MeshBasicMaterial({map:image,transparent:true,opacity:.8,side:T.DoubleSide});
const background=metric?new T.Mesh(new T.PlaneGeometry(metric.width_m,metric.length_m),material):
new T.Mesh(new T.PlaneGeometry(W,H),material);
if(metric){
 background.rotation.x=-Math.PI/2;
 background.position.set(metric.width_m/2,-.035,metric.length_m/2);
}else background.position.z=-90;
scene.add(background);
const coords=metric?[new T.Vector3(0,.13,metric.length_m*.5),new T.Vector3(metric.width_m,.13,metric.length_m*.5)]:
 [new T.Vector3(-W/2,H*(.5-data.line),4),new T.Vector3(W/2,H*(.5-data.line),4)];
const cnt=new T.Line(new T.BufferGeometry().setFromPoints(coords),new T.LineBasicMaterial({color:0xffce70}));scene.add(cnt);
const crosswalk=new T.Group();
for(let k=0;k<9;k++){
 const stripmat=new T.MeshBasicMaterial({color:0xfff0d1,side:T.DoubleSide,transparent:true,opacity:.85});
 const stripe=metric?new T.Mesh(new T.PlaneGeometry(metric.width_m*.11,.4),stripmat):
 new T.Mesh(new T.PlaneGeometry(W*.04,H*.019),stripmat);
 if(metric){stripe.rotation.x=-Math.PI/2;stripe.position.set((k+.5)*metric.width_m/9,.12,metric.length_m*.5);}
 else stripe.position.set(0,(k-4)*H*.035,10);
 crosswalk.add(stripe);
}
scene.add(crosswalk);
const models=data.tracks.map(track=>{
 const spec=specs[track.class]||[30,18,17];
 const mesh=new T.Mesh(new T.BoxGeometry(...spec),new T.MeshStandardMaterial({color:palette[track.class]||0x507dab,roughness:.6,transparent:true,opacity:.9}));
 scene.add(mesh);mesh.visible=false;
 if(track.class!=='person'){
 const roof=new T.Mesh(new T.BoxGeometry(spec[0]*.55,spec[1]*.25,spec[2]*.75),new T.MeshStandardMaterial({color:0xe1f0fc}));
 roof.position.y=spec[1]*.55;mesh.add(roof);
 }
 return {track,mesh,spec};
});
groups.push({scene,renderer,camera,ctl,container,background,crosswalk,models,
 initialPosition:camera.position.clone(),initialQuaternion:camera.quaternion.clone(),initialTarget:ctl.target.clone()});
}
function nearest(points,sec){
 if(!points.length||sec<points[0][0]||sec>points[points.length-1][0])return null;
 let lo=0,hi=points.length-1;
 while(lo<hi){let m=(lo+hi)>>1;if(points[m][0]<sec)lo=m+1;else hi=m;}
 const b=points[lo],a=points[Math.max(0,lo-1)];
 if(a===b||b[0]===a[0])return b;
 if(b[0]-a[0]>3.5)return null;
 const v=(sec-a[0])/(b[0]-a[0]);
 return [sec,...[1,2,3,4].map(i=>a[i]+(b[i]-a[i])*v)];
}
function render(now){
 if(playing)t+=(now-last)/1000*rate;
 if(t>data.duration)t=0;last=now;
 document.getElementById('clock').textContent=String(Math.floor(t/60)).padStart(2,'0')+':'+String(Math.floor(t%60)).padStart(2,'0');
 document.getElementById('seek').value=Math.round(t/Math.max(1,data.duration)*1000);
 for(let j=0;j<2;j++){
 const s=groups[j];s.background.visible=photo;s.crosswalk.visible=!!j&&cross;
 for(const {track,mesh,spec} of s.models){
 const start=track.points[0][0];
 const time=(j&&track.class!=='person')?start+(t-start)*mult:t;
 const p=nearest(track.points,time);
 if(!p){mesh.visible=false;continue;}
 mesh.visible=true;
 if(metric){
    if(p.length<7){mesh.visible=false;continue;}
    mesh.position.set(p[5]+(j?widen*.01*metric.width_m:0),spec[1]*.5,p[6]);
    mesh.scale.set(1,1,1);
    const prev=nearest(track.points,time-.3);
    if(prev&&prev.length>=7)mesh.rotation.y=Math.atan2(p[5]-prev[5],p[6]-prev[6]);
 } else {
    mesh.position.set((p[1]-.5+(j?widen*.005:0))*W,(.5-p[2])*H+spec[1]*.45,20);
    mesh.scale.set(Math.min(2.5,Math.max(.2,p[3]*W/spec[0])),
                   Math.min(2.5,Math.max(.2,p[4]*H/spec[1])),1);
    const prev=nearest(track.points,time-.3);
    mesh.rotation.z=prev?-Math.atan2((p[2]-prev[2])*H,(p[1]-prev[1])*W):0;
 }
 }
 s.ctl.update();s.renderer.render(s.scene,s.camera);
 }
 requestAnimationFrame(render);
}
document.getElementById('pause').onclick=()=>{playing=!playing;document.getElementById('pause').textContent=playing?'Pause':'Play';last=performance.now()};
document.getElementById('restart').onclick=()=>{t=0;last=performance.now()};
document.getElementById('seek').oninput=e=>{t=+e.target.value/1000*data.duration;last=performance.now()};
document.getElementById('rate').onchange=e=>rate=+e.target.value;
document.getElementById('speed').oninput=e=>{mult=+e.target.value/100;document.getElementById('speedtext').textContent=e.target.value+'%'};
document.getElementById('width').oninput=e=>{widen=+e.target.value;document.getElementById('widthtext').textContent=e.target.value+'% visual shift'};
document.getElementById('crossing').onchange=e=>cross=e.target.checked;
document.getElementById('photo').onchange=e=>photo=e.target.checked;
document.getElementById('reset').onclick=()=>{for(const s of groups){
s.camera.position.copy(s.initialPosition);s.camera.quaternion.copy(s.initialQuaternion);
s.camera.zoom=1;s.camera.updateProjectionMatrix();s.ctl.target.copy(s.initialTarget);s.ctl.update()}};
new ResizeObserver(()=>{for(const s of groups){const w=Math.max(300,s.container.clientWidth);s.renderer.setSize(w,Math.round(w*H/W));if(metric){s.camera.aspect=W/H;s.camera.updateProjectionMatrix()}}}).observe(document.body);
document.getElementById('detail').textContent+=(metric?
 ' Metric road-plane texture and approximate camera pose enabled. Reprojection RMSE: '+metric.reprojection_rmse_px+' pixels.':
 ' Image-space alignment only; no surveyed ground geometry.')+
 ' Source tracked agents: '+data.tracks.length+', sampled points: '+data.preview_observations+'. '+data.note;
requestAnimationFrame(render);
}catch(e){const div=document.getElementById('error');div.style.display='block';div.textContent='Unable to open WebGL 3D viewer: '+String(e)+'. Check browser WebGL or library CDN.';console.error(e)}
</script></body></html>'''


def render_reconstruction(job,snapshot):
    st.markdown("### Reconstructed positions · 3D video replay")
    st.caption("Uncalibrated: photo-aligned approximate 3D objects. Calibrated: surveyed real-size flat road surface, video-derived road texture, and estimated matching camera pose. Orbit / zoom and edit the what-if scenario. Neither reconstructs hidden geometry.")
    try: scene=build_scene(job,snapshot)
    except (ValueError,OSError) as exc:
        st.info("3D scene data unavailable: "+str(exc))
        return
    if not scene["tracks"]:
        st.warning("No stable track IDs were present; cannot replay an observed trajectory.")
        return
    html=HTML.replace("__DATA__",json.dumps(scene,separators=(",",":")).replace("</","<\\/"))
    st.iframe(html,height=720,scrolling=False,alt="Interactive camera-aligned 3D vehicle trajectories with before and after sliders")
    with st.expander("What is measured versus inferred?"):
        st.write("Measured: sampled tracked image coordinates, time, classes. Approximate: heights/shapes and hidden 3D surfaces. Manually calibrated when available: planar road distances. The road-widening option is a visual hypothesis, not real-world road engineering.")
        st.caption("This is not yet a photogrammetrically accurate digital twin. A single camera cannot recover hidden geometry.")
