"""Fixed-camera, photo-aligned 3D replay; no rotating ground plane.

Actual observed 2D track locations and timestamps are retained. Vehicles
are generic 3D shapes; no hidden geometric reconstruction is claimed.
"""
from __future__ import annotations
import json
import streamlit as st
from reconstruction import build_scene
from insight_engine import suggestions

VIEWER = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;color:#213448;background:#f7f9fc;font-size:12px}
.heading{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:10px 0 14px;flex-wrap:wrap}
.mini{font-size:11px;color:#8190a2}
button{background:white;border:1px solid #dfe6ef;border-radius:10px;padding:8px 14px;color:#25466b;cursor:pointer}
.framegrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.card{border:1px solid #e2e9f2;border-radius:16px;overflow:hidden;background:white}
.cardtitle{font-size:13px;font-weight:650;padding:13px 16px}
.stage{aspect-ratio:16/9;position:relative;background:#e4eaf2;overflow:hidden}
.stage .backdrop{position:absolute;inset:0;background-repeat:no-repeat;background-position:center;background-size:100% 100%}
.stage canvas{position:absolute;inset:0;display:block;width:100%;height:100%}
.bottom{padding:11px 15px;color:#77879b;line-height:1.4}
.timeline{width:100%;accent-color:#2578d3}
details{background:#fff;border:1px solid #e3eaf3;border-radius:13px;padding:12px 14px;margin-top:10px}
details>summary{cursor:pointer;font-weight:550;color:#466486}
.warn{font-size:11px;color:#75869b;line-height:1.6;padding:10px 0}
#failure{display:none;background:#fff1ee;padding:12px;border-radius:12px;color:#a34434}
@media(max-width:640px){.framegrid{grid-template-columns:repeat(2,minmax(260px,1fr));overflow-x:auto;scroll-snap-type:x mandatory}.card{scroll-snap-align:start}}
</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"}}</script>
</head><body>
<div class="heading"><div><strong>Road scene · Before & after</strong><div class="mini" id="recommendation"></div></div>
<div><button id="pause">Pause</button> <button id="restart">Restart</button> <span id="clock">00:00</span></div></div>
<input type="range" id="seek" class="timeline" min="0" max="1000" value="0" aria-label="Video time"/>
<div class="framegrid">
<section class="card"><div class="cardtitle">Observed traffic</div><div class="stage" id="observed"><div class="backdrop"></div></div><div class="bottom">Original recorded image positions & timestamps</div></section>
<section class="card"><div class="cardtitle">Proposed improvement</div><div class="stage" id="improved"><div class="backdrop"></div></div><div class="bottom">What-if motion with the same fixed camera view</div></section>
</div>
<details><summary>Explore what-if parameters (optional)</summary>
<p class="mini">These changes are assumptions, not measured safety improvements.</p>
<label>Vehicle speed relative to observed image motion <output id="ratioLabel">100%</output></label>
<input style="width:100%;accent-color:#2478d5" id="speedRatio" type="range" min="30" max="130" value="100" step="5"/>
<label><input id="crossing" type="checkbox"/> Illustrative pedestrian crossing marking</label>
</details>
<div class="warn">A single road video does not contain hidden geometry. This is a camera-aligned 3D visual explanation, not a surveyed digital twin. Original photo contains some vehicles; generic 3D bodies are overlaid from tracked positions. Improvement scenarios are illustrative and unvalidated.</div>
<div id="failure"></div>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script type="module">
try {
 const T=await import('three');
 const data=JSON.parse(document.getElementById('scene-data').textContent);
 let current=0, playing=true, last=performance.now(), speedRatio=data.recommended.speed_pct/100,
     crossing=data.recommended.crossing;
 const stages=[document.getElementById('observed'),document.getElementById('improved')];
 const scenes=[];
 const palette={car:0x2c8dcf,bus:0x3c9a8b,truck:0xb78452,motorcycle:0xd78d45,bicycle:0xd9a55e,person:0xc86b80};
 const sizes={car:[36,19,25],bus:[52,26,30],truck:[53,27,31],motorcycle:[22,12,15],bicycle:[18,13,12],person:[10,25,8]};
 const photo=data.image;
 document.getElementById('recommendation').textContent=data.recommended.reason;
 document.getElementById('speedRatio').value=data.recommended.speed_pct;
 document.getElementById('ratioLabel').textContent=data.recommended.speed_pct+'%';
 document.getElementById('crossing').checked=crossing;
 for(let side=0;side<2;side++){
   const stage=stages[side];
   stage.querySelector('.backdrop').style.backgroundImage='url("'+photo+'")';
   const renderer=new T.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});
   renderer.setClearColor(0x000000,0);
   renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
   stage.appendChild(renderer.domElement);
   const scene=new T.Scene();
   scene.add(new T.HemisphereLight(0xffffff,0x8693b1,2));
   const camera=new T.OrthographicCamera(-480,480,270,-270,.1,2000);
   camera.position.set(0,0,1100);camera.lookAt(0,0,0);
   const pool=data.tracks.map(track=>{
      const spec=sizes[track.class]||sizes.car;
      const mat=new T.MeshStandardMaterial({color:palette[track.class]||0x5189b2,
                                            roughness:.55,transparent:true,opacity:.9});
      const mesh=new T.Mesh(new T.BoxGeometry(...spec),mat);
      mesh.visible=false;scene.add(mesh);
      // The sides of the prism remain genuinely 3D under camera rotation;
      // the default camera is locked to match the original photo.
      return {mesh,track,spec};
   });
   const marks=new T.Group();
   for(let i=0;i<9;i++){
      const m=new T.Mesh(new T.PlaneGeometry(35,9),
         new T.MeshBasicMaterial({color:0xfdf9ec,transparent:true,opacity:.8,side:T.DoubleSide}));
      m.position.set((i-4)*44,0,8);marks.add(m);
   }
   scene.add(marks);
   scenes.push({renderer,scene,camera,pool,marks,stage});
 }
 function pos(points,t){
    if(!points.length||t<points[0][0]||t>points[points.length-1][0])return null;
    let low=0,high=points.length-1;
    while(low<high){let m=(low+high)>>1;if(points[m][0]<t)low=m+1;else high=m;}
    let b=points[low],a=points[Math.max(0,low-1)];
    if(a===b)return b;
    if(b[0]-a[0]>2.5)return null; // don't fabricate tracks across major occlusion
    let q=(t-a[0])/(b[0]-a[0]);
    return [t,...[1,2,3,4].map(i=>a[i]+q*(b[i]-a[i]))];
 }
 function frame(now){
    if(playing) current+=(now-last)/1000;
    last=now;
    if(current>data.duration)current=0;
    document.getElementById('seek').value=Math.round(1000*current/Math.max(.1,data.duration));
    document.getElementById('clock').textContent=String(Math.floor(current/60)).padStart(2,'0')+':'+String(Math.floor(current%60)).padStart(2,'0');
    for(let side=0;side<2;side++){
      const s=scenes[side];
      s.marks.visible=side===1&&crossing;
      for(const o of s.pool){
        const points=o.track.points;
        const start=points[0][0];
        let t=side===1&&o.track.class!=='person'?start+(current-start)*speedRatio:current;
        const p=pos(points,t);
        if(!p){o.mesh.visible=false;continue;}
        o.mesh.visible=true;
        o.mesh.position.set((p[1]-.5)*960,(.5-p[2])*540+o.spec[1]*.48,45);
        o.mesh.scale.set(Math.max(.2,Math.min(3,p[3]*960/o.spec[0])),
                         Math.max(.2,Math.min(3,p[4]*540/o.spec[1])),1);
        const prev=pos(points,t-.2);
        o.mesh.rotation.z=prev?-Math.atan2((p[2]-prev[2])*540,(p[1]-prev[1])*960):0;
      }
      s.renderer.render(s.scene,s.camera);
    }
    requestAnimationFrame(frame);
 }
 function size(){
    for(const s of scenes){
        const rect=s.stage.getBoundingClientRect();
        const w=Math.max(1,rect.width),h=Math.max(1,rect.height);
        s.renderer.setSize(w,h,false);
        const ratio=w/h;
        s.camera.left=-270*ratio;
        s.camera.right=270*ratio;
        s.camera.top=270;s.camera.bottom=-270;
        s.camera.updateProjectionMatrix();
    }
 }
 new ResizeObserver(size).observe(document.body);size();
 document.getElementById('pause').onclick=()=>{
   playing=!playing;last=performance.now();
   document.getElementById('pause').textContent=playing?'Pause':'Play';
 };
 document.getElementById('restart').onclick=()=>{current=0;last=performance.now()};
 document.getElementById('seek').oninput=e=>{current=Number(e.target.value)/1000*data.duration;last=performance.now()};
 document.getElementById('speedRatio').oninput=e=>{speedRatio=Number(e.target.value)/100;
     document.getElementById('ratioLabel').textContent=e.target.value+'%'};
 document.getElementById('crossing').onchange=e=>crossing=e.target.checked;
 requestAnimationFrame(frame);
} catch(e){
    const target=document.getElementById('failure');target.style.display='block';
    target.textContent='3D unavailable in this browser: '+String(e).slice(0,200);
}
</script></body></html>'''


def render_reconstruction(job,snapshot):
    try:
        data=build_scene(job,snapshot)
    except (OSError,ValueError) as error:
        st.info("3D video replay needs detected object tracks: "+str(error))
        return
    if not data["tracks"]:
        st.warning("No reliable tracks were produced. A camera-aligned replay cannot be claimed without detections.")
        return
    ids={r["id"] for r in suggestions(snapshot.get("evidence",{}))}
    pct=75 if "speed_review" in ids else 100
    crossing="crossing_review" in ids
    data.pop("embedded_video",None) # avoid sending huge videos into an iframe
    data["recommended"]={
        "speed_pct":pct,"crossing":crossing,
        "reason":("Speed moderation suggested" if pct<100 else "Observed speed unchanged")+" · "+(
          "Crossing layout review suggested" if crossing else "No crossing intervention inferred")
    }
    html=VIEWER.replace("__SCENE_JSON__",json.dumps(data,separators=(",",":")).replace("</","<\\/"))
    st.iframe(html,height="content",alt="Stable camera-aligned 3D before and after road scene")
