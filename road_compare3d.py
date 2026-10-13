"""Actual original video on the left; one modified Three.js road model on the right.

Observed footpoint pixels back-project to a *hypothetical flat ground plane*
using the same perspective camera that renders the 3D model. This preserves
the pixel alignment of the footpoint in SOURCE VIEW, but road depth,
building geometry, and unseen 3D surfaces are *not* observed from video.
The original HTML5 video is the ONLY clock. No separate simulated 'before'.
"""
from __future__ import annotations
import json
from html import escape

import streamlit as st

from reconstruction import build_scene
from road_advice import road_report
from video_comparison import prepare_source_video

VIEWER = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
html,body{margin:0;background:#f7f9fc;color:#24374d;font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.title{font-size:15px;font-weight:750;letter-spacing:-.025em}
.sub{color:#7c90a6;line-height:1.6;font-size:11px}
.tools{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
button,select{border-radius:10px;border:1px solid #dbe5f0;background:#fff;color:#2b4b6b;padding:8px 11px;cursor:pointer}
button:hover{background:#e9f2ff}
.shell{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
.panel{border-radius:17px;border:1px solid #dce6f2;overflow:hidden;background:#fff;min-width:0}
.panelhead{padding:12px 15px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.panelhead strong{font-size:13px}
.panelhead span{color:#7a90a6;font-size:10px}
.viewport{aspect-ratio:16/9;position:relative;overflow:hidden;background:#d2e3eb}
.viewport video,.viewport canvas,.viewport .matched-background{height:100%;width:100%;display:block;object-fit:contain}
.viewport .matched-background{position:absolute;inset:0;z-index:0;pointer-events:none}
.viewport canvas{position:absolute;inset:0;z-index:1;cursor:grab}
.viewport canvas{cursor:grab}
.panelnote{padding:11px 15px;border-top:1px solid #e8edf3;color:#8290a2;min-height:54px;line-height:1.5;font-size:11px}
.model-loading{position:absolute;inset:0;z-index:7;display:flex;flex-direction:column;gap:11px;align-items:center;justify-content:center;background:#e9f1f7;color:#405b77;font-size:13px;text-align:center;padding:24px;transition:opacity .25s ease}
.model-loading[hidden]{display:none}
.model-loading .spinner{width:30px;height:30px;border:3px solid #c7d9ea;border-top-color:#2878ce;border-radius:50%;animation:road-spin .9s linear infinite}
@keyframes road-spin{to{transform:rotate(360deg)}}
.model-loading .loading-sub{font-size:11px;color:#7890a4;max-width:260px;line-height:1.5}
.video-fallback{display:none;position:absolute;inset:0;align-items:center;justify-content:center;padding:25px;background:#f0f5fa;color:#46617a;text-align:center;flex-direction:column;gap:12px}
.video-fallback input{max-width:100%;font-size:11px}
.playback{display:flex;align-items:center;gap:10px;margin:13px 0;flex-wrap:wrap}
.playback input[type=range]{flex:1;min-width:120px;accent-color:#307fe0}
.settings{display:flex;align-items:center;gap:15px;flex-wrap:wrap;border:1px solid #e2e9f2;border-radius:14px;padding:14px;background:#fff}
.settings label{font-size:11px;color:#627a90}
.settings input{accent-color:#307fe0}
.settings input[type=range]{width:135px}
.hint{padding:11px 2px;font-size:11px;color:#7c8da3;line-height:1.6}
.warning{font-size:11px;color:#886d2e;background:#fff8e7;padding:11px 13px;border-radius:12px;line-height:1.6;margin-top:6px}
.error{display:none;padding:14px;color:#b54737;background:#fff1ee;border-radius:12px}
@media(max-width:710px){.shell{grid-template-columns:repeat(2,minmax(310px,1fr));overflow-x:auto;scroll-snap-type:x mandatory}.panel{scroll-snap-align:start}.viewport{aspect-ratio:16/9}}
</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}</script>
</head><body>
<div class="top"><div><div class="title">Original video vs improved 3D</div><div class="sub">One source-video timeline · Matched ground-contact pixels in Source View · Editable what-if scene</div></div>
<div class="tools"><button id="play" aria-label="Play or pause original footage">Play</button><button id="restart">Restart</button>
<select id="camera" aria-label="Simulation camera"><option value="source">Source view</option><option value="orbit">Orbit 3D</option><option value="top">Top view</option></select>
<strong id="clock">00:00</strong></div></div>
<div class="shell">
  <section class="panel">
    <div class="panelhead"><strong>01 · Original recorded video</strong><span>Real footage · Not a simulation</span></div>
    <div class="viewport">
      <video id="sourceVideo" controls playsinline preload="metadata" src="__VIDEO_URL__"></video>
      <div class="video-fallback" id="videoFallback"><strong>Original video needed for synchronization</strong>
        <span id="videoMessage">Load the original recording from your computer; it never leaves the browser.</span>
        <input id="localVideo" type="file" accept="video/mp4,video/webm,video/quicktime,video/*" aria-label="Load original local video">
      </div>
    </div>
    <div class="panelnote">The original recording is the master timeline. Play, pause or seek here to control the 3D scenario.</div>
  </section>
  <section class="panel">
    <div class="panelhead"><strong>02 · Camera-matched modified 3D</strong><span id="scenarioName">Scenario</span></div>
    <div class="viewport" id="simulation"><img class="matched-background" id="matchedBackground" alt="Background extracted from the actual road video" />
<div class="model-loading" id="modelLoading" role="status" aria-live="polite"><div class="spinner" aria-hidden="true"></div><strong id="loadingStage">Building your 3D road…</strong><span class="loading-sub">Loading the road image, vehicles and camera view. Please wait.</span></div></div>
    <div class="panelnote">Source View: actual road image with 3D tracked vehicles and visual interventions. Orbit / Top: approximate 3D geometry.</div>
  </section>
</div>
<div class="playback"><label for="seek">Timeline</label><input id="seek" type="range" min="0" max="1000" value="0">
<span id="timeText">00:00 / 00:00</span></div>
<div class="settings">
 <label for="intervention">Proposed change</label><select id="intervention"></select>
 <label for="ratio">Vehicle movement ratio</label><input id="ratio" type="range" min="50" max="125" step="5" value="100">
 <strong id="ratioText">100%</strong><button id="reset">Reset scenario</button>
</div>
<div class="hint" id="comparisonDetail"></div>
<div class="warning">Source View aligns observed ground-contact IMAGE coordinates using a perspective camera and an assumed flat road plane. This does not recover real depth, road widths, occluded geometry, or calibrated physical speeds. An intervention is an illustrative counterfactual, not a demonstrated safety improvement.</div>
<div class="error" id="error"></div>
<script id="sceneData" type="application/json">__SCENE__</script>
<script type="module">
try {
 const loadingStage=document.getElementById("loadingStage");
 if(loadingStage)loadingStage.textContent="Loading 3D graphics…";
 const THREE=await import("three");
 const {OrbitControls}=await import("three/addons/controls/OrbitControls.js");
 const data=JSON.parse(document.getElementById("sceneData").textContent);
 if(loadingStage)loadingStage.textContent="Matching road camera…";
 const video=document.getElementById("sourceVideo");
 const frameWidth=Number(data.originalDimensions?.[0])||960;
 const frameHeight=Number(data.originalDimensions?.[1])||540;
 for(const element of document.querySelectorAll(".viewport")){
     element.style.aspectRatio=String(frameWidth)+"/"+String(frameHeight);
 }
 const fallback=document.getElementById("videoFallback");
 const local=document.getElementById("localVideo");
 let localUrl=null,intervention=data.initialOption||"none",speedRatio=1,lastFrame=-1;
 const opts=[{id:"none",title:"No proposed intervention"},...data.options];
 for(const choice of [{id:"markings",title:"Review enhanced lane markings (unverified)"},
                      {id:"lighting",title:"Review additional lighting (unverified)"},
                      {id:"speed_review",title:"Review warning sign (unverified)"}]){
    if(!opts.some(o=>o.id===choice.id))opts.push(choice);
 }
 const selector=document.getElementById("intervention");
 for(const option of opts){const el=document.createElement("option");el.value=option.id;el.textContent=option.title;selector.append(el)}
 selector.value=intervention;
 document.getElementById("comparisonDetail").textContent=data.videoStatus+
   " Tracks are time-sampled and may be lost/reassigned during occlusion. Road shape uses source-image boundary anchors as an *approximate* scene model.";
 function fallbackState(message){
   fallback.style.display="flex";
   document.getElementById("videoMessage").textContent=message||"Select the original recording from this computer.";
 }
 if(!video.getAttribute("src"))fallbackState(data.videoStatus);
 video.addEventListener("error",()=>fallbackState("The original video cannot be decoded in this browser. Select an MP4/WebM version locally."));
 local.addEventListener("change",()=>{
    if(localUrl)URL.revokeObjectURL(localUrl);
    const file=local.files&&local.files[0];
    if(!file)return;
    localUrl=URL.createObjectURL(file);
    video.src=localUrl;video.load();video.currentTime=0;
    fallback.style.display="none";
 });
 const S={w:960,h:540};
 // Perspective camera whose ray/ground intersection is used to construct BOTH
 // road surfaces and vehicle footpoints. Reprojection keeps each sampled
 // ground-contact pixel aligned in Source View without inventing depth.
 const viewport=document.getElementById("simulation");
 const matchedBackground=document.getElementById("matchedBackground");
 matchedBackground.src=data.backgroundImage;
 const backgroundReady=matchedBackground.decode?
    matchedBackground.decode().then(()=>true).catch(()=>false):
    Promise.resolve(true);
 const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:"low-power",alpha:true});
 renderer.setClearColor(0xcadce7,0);
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.6));
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.shadowMap.enabled=true;
 renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 viewport.appendChild(renderer.domElement);
 const scene=new THREE.Scene();scene.background=null;
 const environment=new THREE.Group();scene.add(environment);
 const sourceTexture=new THREE.TextureLoader().load(data.backgroundImage);
 sourceTexture.colorSpace=THREE.SRGBColorSpace;
 const photoRoad=new THREE.MeshStandardMaterial({map:sourceTexture,roughness:.98,side:THREE.DoubleSide});
 scene.fog=new THREE.Fog(0xc8dfe9,180,680);
 scene.add(new THREE.HemisphereLight(0xffffff,0x7d9187,2.0));
 const sun=new THREE.DirectionalLight(0xffecd7,2.0);
 sun.position.set(-25,70,-30);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);
 sun.shadow.camera.left=-120;sun.shadow.camera.right=120;
 sun.shadow.camera.top=170;sun.shadow.camera.bottom=-130;scene.add(sun);
 const camera=new THREE.PerspectiveCamera(57,16/9,.1,1600);
 const controls=new OrbitControls(camera,renderer.domElement);
 controls.enableDamping=true;controls.enablePan=false;
 controls.minDistance=8;controls.maxDistance=900;controls.maxPolarAngle=Math.PI*.49;
 const sourceCamera=new THREE.PerspectiveCamera(57,frameWidth/frameHeight,.1,1600);
 sourceCamera.position.set(0,29,-38);
 sourceCamera.lookAt(-7,0,52);
 sourceCamera.updateProjectionMatrix();
 // Raycaster.setFromCamera reads camera.matrixWorld. lookAt() changes the
 // quaternion but DOES NOT refresh matrixWorld until an update/render.
 // This camera is never rendered directly, so the explicit refresh is vital.
 sourceCamera.updateMatrixWorld(true);
 camera.position.copy(sourceCamera.position);
 camera.quaternion.copy(sourceCamera.quaternion);
 controls.target.set(-7,0,52);controls.update();
 const raycaster=new THREE.Raycaster();
 const groundPlane=new THREE.Plane(new THREE.Vector3(0,1,0),0);
 function imageToGround(x,y) {
   const uv=new THREE.Vector2((x-.5)*2,(.5-y)*2);
   raycaster.setFromCamera(uv,sourceCamera);
   const intersection=new THREE.Vector3();
   if(!raycaster.ray.intersectPlane(groundPlane,intersection))return null;
   if(!Number.isFinite(intersection.x)||!Number.isFinite(intersection.z))return null;
   if(intersection.z>900||intersection.z< -100||Math.abs(intersection.x)>600)return null;
   return intersection;
 }
 // Normalized source-visible road boundaries; points are PHOTO estimates,
 // not LiDAR or a known road survey. They can be replaced by calibrated
 // surveyed anchors in future versions without changing the playback clock.
 const anchors=[
  {v:.29,left:.36,innerLeft:.525,innerRight:.548,right:.78},
  {v:.36,left:.25,innerLeft:.485,innerRight:.53,right:.80},
  {v:.48,left:.14,innerLeft:.43,innerRight:.495,right:.87},
  {v:.64,left:.04,innerLeft:.365,innerRight:.445,right:.98},
  {v:.82,left:-.12,innerLeft:.295,innerRight:.388,right:1.11},
  {v:1.10,left:-.32,innerLeft:.20,innerRight:.31,right:1.29},
 ];
 function sampleEdge(edge,v){
   for(let i=1;i<anchors.length;i++){
      if(v<=anchors[i].v){
          const a=anchors[i-1],b=anchors[i];
          const t=Math.max(0,Math.min(1,(v-a.v)/(b.v-a.v)));
          return a[edge]+t*(b[edge]-a[edge]);
      }
   }
   const a=anchors[anchors.length-2],b=anchors[anchors.length-1];
   return b[edge]+(v-b.v)/(b.v-a.v)*(b[edge]-a[edge]);
 }
 const mat=(color,metal=0)=>new THREE.MeshStandardMaterial({color,roughness:.78,metalness:metal,side:THREE.DoubleSide});
 const asphalt=mat(0x383f4b),shoulder=mat(0x78828e),median=mat(0x72976a),green=mat(0x88b58a),white=mat(0xeef0e8),metal=mat(0x9baebc,.24);
 const geometryHealth={roadSections:0,vertexCount:0,groundWidth:0,groundDepth:0};
 const ground=new THREE.Mesh(new THREE.PlaneGeometry(1200,1600),green);
 ground.rotation.x=-Math.PI/2;ground.position.z=160;ground.position.y=-.13;ground.receiveShadow=true;environment.add(ground);
 function addMesh(geo,material,x=0,y=0,z=0,group=environment){
   const m=new THREE.Mesh(geo,material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;
 }
 function strip(edgeA,edgeB,material,elev=.03){
    const points=[],uvs=[],indices=[],steps=45;
    for(let i=0;i<=steps;i++){
        const v=.295+i/steps*.78;
        const a=imageToGround(sampleEdge(edgeA,v),v);
        const b=imageToGround(sampleEdge(edgeB,v),v);
        if(!a||!b)continue;
        points.push(a.x,elev,a.z,b.x,elev,b.z);
         uvs.push(sampleEdge(edgeA,v),1-v,sampleEdge(edgeB,v),1-v);
    }
    const count=points.length/6;
    if(count<2)return;
    let minX=Infinity,maxX=-Infinity,minZ=Infinity,maxZ=-Infinity;
    for(let k=0;k<points.length;k+=3){
      minX=Math.min(minX,points[k]);maxX=Math.max(maxX,points[k]);
      minZ=Math.min(minZ,points[k+2]);maxZ=Math.max(maxZ,points[k+2]);
    }
    // A stale matrixWorld can back-project all pixels to the SAME point:
    // the renderer then silently draws degenerate, invisible triangles.
    if(maxX-minX<.4 || maxZ-minZ<1){
      throw new Error("3D road projection collapsed to a point. Check camera world matrix and ground rays.");
    }
    geometryHealth.roadSections++;
    geometryHealth.vertexCount+=count*2;
    geometryHealth.groundWidth=Math.max(geometryHealth.groundWidth,maxX-minX);
    geometryHealth.groundDepth=Math.max(geometryHealth.groundDepth,maxZ-minZ);
    for(let i=0;i<count-1;i++){const k=2*i;indices.push(k,k+1,k+2,k+1,k+3,k+2)}
    const geo=new THREE.BufferGeometry();
    geo.setAttribute("position",new THREE.Float32BufferAttribute(points,3));
    geo.setIndex(indices);
    geo.setAttribute("uv",new THREE.Float32BufferAttribute(uvs,2));
    geo.computeVertexNormals();
    const mesh=new THREE.Mesh(geo,photoRoad);mesh.receiveShadow=true;environment.add(mesh);
 }
 strip("left","innerLeft",asphalt);
 strip("innerRight","right",asphalt);
 strip("innerLeft","innerRight",median,.06);
 if(geometryHealth.roadSections!==3 || geometryHealth.vertexCount<60){
   throw new Error("The reconstructed 3D road is incomplete: "+JSON.stringify(geometryHealth));
 }
 document.getElementById("scenarioName").title=
   "Road mesh verified: "+geometryHealth.vertexCount+" vertices · "+geometryHealth.roadSections+" surfaces";
 function inLaneImage(v,left,right,t){return sampleEdge(left,v)*(1-t)+sampleEdge(right,v)*t}
 const markingGroup=new THREE.Group();environment.add(markingGroup);
 function dashLane(left,right,fraction,group,continuous=false){
    let last=null;
    for(let i=0;i<=58;i++){
      const v=.33+i/58*.70;
      const pt=imageToGround(inLaneImage(v,left,right,fraction),v);
      if(!pt)continue;
      if(last && (continuous||i%5!==0)){
        const delta=pt.clone().sub(last),dist=delta.length();
        if(dist>0.01 && dist<95){
         const mark=addMesh(new THREE.BoxGeometry(.18,.035,dist),white,
              (pt.x+last.x)/2,.14,(pt.z+last.z)/2,group);
         mark.rotation.y=Math.atan2(-delta.x,-delta.z);mark.castShadow=false;
        }
      }
      last=pt;
    }
 }
 dashLane("left","innerLeft",.50,markingGroup);
 dashLane("innerRight","right",.46,markingGroup);
 const enhanced=new THREE.Group();scene.add(enhanced);
 dashLane("left","innerLeft",.50,enhanced,true);
 dashLane("innerRight","right",.46,enhanced,true);
 enhanced.visible=false;
 // Roadside geometry: roadside rail posts, vegetation and streetlamps.
 const wood=mat(0x685e4e);
 for(let v=.35;v<1.02;v+=.036){
   for(const edge of ["innerLeft","innerRight","left","right"]){
       const foot=imageToGround(sampleEdge(edge,v),v);
       if(!foot)continue;
       const post=addMesh(new THREE.BoxGeometry(.17,.95,.19),metal,foot.x,.50,foot.z);
       post.castShadow=false;
   }
 }
 const treeColors=[0x477c57,0x5d9665,0x689d6c,0x527c59];
 for(let v=.37,k=0;v<.99;v+=.077,k++){
   for(const edge of ["left","right"]){
      const u=sampleEdge(edge,v)+(edge==="left"?-.072:.085);
      const foot=imageToGround(u,v);
      if(!foot)continue;
      addMesh(new THREE.CylinderGeometry(.14,.28,3,6),wood,foot.x,1.5,foot.z);
      addMesh(new THREE.DodecahedronGeometry(2.8,0),mat(treeColors[k%treeColors.length]),foot.x,5,foot.z);
   }
 }
 const lampMat=mat(0x7d8b9b,.2);
 for(let v=.37;v<.90;v+=.17){
    const foot=imageToGround((sampleEdge("innerLeft",v)+sampleEdge("innerRight",v))/2,v);
    if(!foot)continue;
    addMesh(new THREE.CylinderGeometry(.08,.11,7,7),lampMat,foot.x,3.5,foot.z);
    addMesh(new THREE.BoxGeometry(2.3,.12,.17),lampMat,foot.x+1,6.95,foot.z);
 }
 function vehicleModel(type,color){
    const g=new THREE.Group(),heavy=(type==="truck"||type==="bus"),bike=(type==="motorcycle"||type==="bicycle");
    const length=heavy?8.4:bike?2.2:4.4,width=heavy?2.5:bike?.8:1.95,bodyHeight=heavy?2.7:bike?.7:1.4;
    const body=mat(color,.10),glass=mat(0xa6cfe0,.05),rubber=mat(0x262c36),lamp=mat(0xf6edbf);
    addMesh(new THREE.BoxGeometry(width,bodyHeight*.54,length),body,0,.55+bodyHeight*.27,0,g);
    if(!bike){
      addMesh(new THREE.BoxGeometry(width*.77,bodyHeight*.51,length*.54),heavy?mat(0xd2dce5):body,0,1.12+bodyHeight*.21,-length*.03,g);
      addMesh(new THREE.BoxGeometry(width*.72,.40,.12),glass,0,1.32+bodyHeight*.21,-length*.32,g);
    }else{
      addMesh(new THREE.BoxGeometry(.28,.55,.40),mat(0x39414c),0,1.04,0,g);
    }
    for(const sign of [-1,1]){
      for(const z of [-length*.31,length*.31]){
        const wheel=addMesh(new THREE.CylinderGeometry(bike?.30:.46,bike?.30:.46,.20,9),rubber,sign*(width/2),bike?.35:.48,z,g);
        wheel.rotation.z=Math.PI/2;
      }
      addMesh(new THREE.BoxGeometry(.25,.14,.08),lamp,sign*width*.32,1,-length*.5,g);
    }
    return g
 }
 const models=[];
 const palettes={car:[0x477fb9,0xb97d71,0x6d9c94,0x7791ac],truck:[0xcececa,0x92a3b4],bus:[0xd6b477],motorcycle:[0xb07d54],bicycle:[0x8ca78c]};
 let index=0;
 for(const track of data.tracks){
    if(!(track.class in palettes)||!track.points?.length)continue;
    const segments=prepareMotion(track.points);
    if(!segments.length)continue; // Ignore single-frame ID noise instead of teleporting an entire vehicle.
    const colors=palettes[track.class],color=colors[index++%colors.length];
    const obj=vehicleModel(track.class,color);
    const materials=[];
    obj.traverse(child=>{
      if(!child.isMesh)return;
      child.material=child.material.clone(); // Each vehicle fades independently.
      child.material.transparent=true;
      child.material.opacity=0;
      materials.push(child.material);
    });
    obj.visible=false;scene.add(obj);
    models.push({obj,track,segments,materials,previousTime:null,heading:null});
 }
 const lighting=new THREE.Group();scene.add(lighting);
 for(let v=.4;v<.95;v+=.15){
    const spot=imageToGround(sampleEdge("right",v)+.03,v);
    if(!spot)continue;
    addMesh(new THREE.CylinderGeometry(.07,.09,7,6),lampMat,spot.x,3.5,spot.z,lighting);
    addMesh(new THREE.BoxGeometry(1.5,.2,.5),mat(0xffe9a2),spot.x-.7,7,spot.z,lighting);
 }
 const signGroup=new THREE.Group();scene.add(signGroup);
 const sg=imageToGround(sampleEdge("right",.64),.64);
 if(sg){
    addMesh(new THREE.CylinderGeometry(.06,.1,4,6),lampMat,sg.x+.8,2,sg.z,signGroup);
    addMesh(new THREE.BoxGeometry(1.8,1.5,.13),mat(0xe7eff8),sg.x+.8,4.2,sg.z,signGroup);
 }
 function chooseCamera(view){
   const aligned=view==="source";
    controls.enabled=!aligned;
    environment.visible=!aligned;
    matchedBackground.style.display=aligned?"block":"none";
    scene.background=aligned?null:new THREE.Color(0xc8dfe9);
    renderer.setClearColor(0xc8dfe9,aligned?0:1);
   if(view==="source"){
      camera.position.copy(sourceCamera.position);
      camera.quaternion.copy(sourceCamera.quaternion);
      controls.target.set(-7,0,52);
      controls.update();
   }else if(view==="orbit"){
      camera.position.set(35,66,-45);controls.target.set(0,0,100);controls.update();
   }else{
      camera.position.set(0,170,90);controls.target.set(0,0,85);controls.update();
   }
 }
 // Remove isolated box jitter and split reappearing/disconnected IDs.
 // A tracker ID is not proof that one physical vehicle remained continuous.
 function prepareMotion(points){
   const raw=points.filter(p=>p.length>=5 && p.slice(0,5).every(Number.isFinite))
                    .slice().sort((a,b)=>a[0]-b[0]);
   if(raw.length<3)return [];
   const smooth=raw.map((p,i)=>{
     const out=p.slice(0,5);
     if(i===0||i===raw.length-1)return out;
     const prev=raw[i-1],next=raw[i+1],dt=next[0]-prev[0];
     if(dt<=0||dt>1.35)return out;
     const mx=(prev[1]+next[1])/2,my=(prev[2]+next[2])/2;
     const residual=Math.hypot(p[1]-mx,p[2]-my);
     const neighbors=Math.hypot(prev[1]-next[1],prev[2]-next[2]);
     if(residual>Math.max(.055,p[4]*1.35) && neighbors<.13){
        out[1]=mx;out[2]=my; // isolated tracker glitch
     } else if(neighbors<.16){
        out[1]=.18*prev[1]+.64*p[1]+.18*next[1];
        out[2]=.18*prev[2]+.64*p[2]+.18*next[2];
     }
     return out;
   });
   const segments=[];let current=[];
   function finish(){
     if(current.length>=3 && current[current.length-1][0]-current[0][0]>=.18)
       segments.push(current);
     current=[];
   }
   for(const p of smooth){
      if(current.length){
        const prev=current[current.length-1],dt=p[0]-prev[0];
        const jump=Math.hypot(p[1]-prev[1],p[2]-prev[2]);
        const cap=Math.max(.075,.12*dt,2.5*Math.max(p[4],prev[4]));
        if(dt<=0||dt>1.45||jump>cap)finish();
      }
      current.push(p);
   }
   finish();
   return segments;
 }
 function interpolateMotion(segments,t){
   for(const points of segments){
     const first=points[0],last=points[points.length-1];
     if(t<first[0]||t>last[0])continue;
     let lo=0,hi=points.length-1;
     while(lo<hi){const mid=(lo+hi)>>1;if(points[mid][0]<t)lo=mid+1;else hi=mid}
     const a=points[Math.max(0,lo-1)],b=points[lo];
     const fraction=a===b||b[0]===a[0]?0:(t-a[0])/(b[0]-a[0]);
     const p=a===b?a:[t,...[1,2,3,4].map(i=>a[i]+(b[i]-a[i])*fraction)];
     const fade=Math.max(0,Math.min(1,(t-first[0])/.38,(last[0]-t)/.38));
     return {p,alpha:fade,direction:last[2]-first[2]};
   }
   return null;
 }
 // Derive heading from the persistent lane's curve, not from the
 // noisy per-frame image-box delta that twists cars 90 degrees sideways.
 function roadHeading(p,screenDirection){
    const v=Math.max(.36,Math.min(.97,p[2]));
    const left=(sampleEdge("left",v)+sampleEdge("innerLeft",v))/2;
    const right=(sampleEdge("innerRight",v)+sampleEdge("right",v))/2;
    const onLeft=Math.abs(p[1]-left)<Math.abs(p[1]-right);
    const center=y=>{
      const a=onLeft?"left":"innerRight",b=onLeft?"innerLeft":"right";
      return (sampleEdge(a,y)+sampleEdge(b,y))/2;
    };
    // Traffic on opposite separated carriageways travels in opposite directions.
    const sign=Math.abs(screenDirection)>.03?Math.sign(screenDirection):(onLeft?1:-1);
    const v2=Math.max(.34,Math.min(.99,v+sign*.045));
    const here=imageToGround(center(v),v);
    const ahead=imageToGround(center(v2),v2);
    if(!here||!ahead)return null;
    const dx=ahead.x-here.x,dz=ahead.z-here.z;
    if(Math.hypot(dx,dz)<.02)return null;
    return Math.atan2(-dx,-dz);
 }
 function update3D(currentTime){
    for(const entry of models){
      const first=entry.segments[0][0][0];
      const change=speedRatio;
      const trackTime=first+(currentTime-first)*change;
      const measured=interpolateMotion(entry.segments,trackTime);
      if(!measured||measured.alpha<.01){
        entry.obj.visible=false;
        entry.previousTime=null;
        continue;
      }
      const p=measured.p;
      const position=imageToGround(p[1],p[2]);
      if(!position){entry.obj.visible=false;entry.previousTime=null;continue;}
      entry.obj.visible=true;
      entry.obj.position.copy(position);
      for(const material of entry.materials)material.opacity=measured.alpha;
      if(document.getElementById("camera").value==="source"){
        const low=position.clone().project(sourceCamera);
        const high=position.clone().add(new THREE.Vector3(0,2.15,0)).project(sourceCamera);
        const projectedHeight=Math.abs((high.y-low.y)/2);
        if(projectedHeight>.0001 && p[4]>0){
          const desired=Math.max(.2,Math.min(3.2,p[4]/projectedHeight));
          entry.obj.scale.setScalar(desired);
        }
      }else entry.obj.scale.setScalar(1);
      const yaw=roadHeading(p,measured.direction);
      if(yaw!==null){
        const jump=entry.previousTime===null||Math.abs(currentTime-entry.previousTime)>.35;
        if(jump||entry.heading===null)entry.heading=yaw;
        else{
          const delta=Math.atan2(Math.sin(yaw-entry.heading),Math.cos(yaw-entry.heading));
          entry.heading+=delta*.11;
        }
        entry.obj.rotation.y=entry.heading;
      }
      entry.previousTime=currentTime;
    }
 }
 function applyIntervention(){
   const name=selector.value;
   enhanced.visible=name==="markings";
   lighting.visible=name==="lighting";
   signGroup.visible=name==="speed_review";
   document.getElementById("scenarioName").textContent=selector.selectedOptions[0]?.textContent||"Proposed";
 }
 function resize(){
    const rect=viewport.getBoundingClientRect();
    if(rect.width<1||rect.height<1)return;
    renderer.setSize(rect.width,rect.height,false);
    const aspect=rect.width/rect.height;
    // SOURCE coordinates keep 16:9 with the exact same film-frame aspect.
    // A mismatch is handled by the video player's object-fit:contain.
    camera.aspect=aspect;camera.updateProjectionMatrix();
    // Keep the source camera's calibrated film aspect fixed; do not skew its rays on resize.
 }
 new ResizeObserver(resize).observe(viewport);
 resize();chooseCamera("source");
 const seek=document.getElementById("seek");
 const play=document.getElementById("play");
 const clock=document.getElementById("clock");
 function labelTime(t){return String(Math.floor(t/60)).padStart(2,"0")+":"+String(Math.floor(t%60)).padStart(2,"0")}
 function duration(){return (Number.isFinite(video.duration)&&video.duration>0)?video.duration:0}
 video.addEventListener("loadedmetadata",()=>{seek.value=0;clock.textContent="00:00";document.getElementById("timeText").textContent="00:00 / "+labelTime(duration())});
 video.addEventListener("play",()=>play.textContent="Pause");
 video.addEventListener("pause",()=>play.textContent="Play");
 video.addEventListener("ended",()=>play.textContent="Play");
 play.onclick=()=>{if(!duration())return; if(video.paused)video.play().catch(()=>{});else video.pause()};
 document.getElementById("restart").onclick=()=>{video.pause();if(duration())video.currentTime=0};
 seek.oninput=e=>{if(duration())video.currentTime=Number(e.target.value)/1000*duration()};
 selector.onchange=applyIntervention;
 document.getElementById("ratio").oninput=e=>{speedRatio=Number(e.target.value)/100;document.getElementById("ratioText").textContent=e.target.value+"%"};
 document.getElementById("camera").onchange=e=>chooseCamera(e.target.value);
 document.getElementById("reset").onclick=()=>{
    selector.value="none";selector.dispatchEvent(new Event("change"));
    speedRatio=1;document.getElementById("ratio").value=100;document.getElementById("ratioText").textContent="100%";
    document.getElementById("camera").value="source";chooseCamera("source");
 };
 applyIntervention();
 let readyNotified=false;
 function animate(){
    // Absolutely no independent simulation clock. When the source is paused,
    // the modified 3D agents freeze at the same original timestamp.
    const t=duration()?video.currentTime:0;
    const d=duration()||Math.max(.1,data.duration||1);
    seek.value=duration()?Math.round(1000*t/d):0;
    clock.textContent=labelTime(t);
    document.getElementById("timeText").textContent=labelTime(t)+" / "+labelTime(d);
    update3D(t);controls.update();renderer.render(scene,camera);
    if(!readyNotified){
      readyNotified=true;
      const panel=document.getElementById("modelLoading");
      if(loadingStage)loadingStage.textContent="Finishing scene…";
      backgroundReady.then(ok=>{
        if(panel)panel.hidden=true;
        if(!ok){
          const hint=document.getElementById("comparisonDetail");
          if(hint)hint.textContent+=" Camera background did not decode; some road details might not appear.";
        }
      });
    }
    requestAnimationFrame(animate);
 }
 requestAnimationFrame(animate);
} catch(error){
 const message="3D scene unavailable: "+String(error).slice(0,220);
 const el=document.getElementById("error");el.style.display="block";
 el.textContent=message;
 const panel=document.getElementById("simulation");
 if(panel){
   const loader=document.getElementById("modelLoading");
   if(loader)loader.hidden=true;
   const overlay=document.createElement("div");
   overlay.setAttribute("role","alert");
   overlay.style.cssText="position:absolute;inset:0;z-index:10;display:flex;align-items:center;justify-content:center;padding:22px;background:#fff1ee;color:#9f302c;font-size:14px;text-align:center;line-height:1.6";
   overlay.textContent=message;
   panel.appendChild(overlay);
 }
 console.error(error);
}
</script></body></html>'''


def _simulation_options(report):
    names = {
        "markings": "Enhance lane guidance",
        "lighting": "Add roadside lighting (concept)",
        "speed_review": "Review warning signage (concept)",
    }
    options = []
    for rec in report["recommendations"]:
        category = rec.get("simulation_option")
        if category in ("flow", "path"):
            category = "markings"
        if category in names and category not in [opt["id"] for opt in options]:
            options.append({"id":category, "title": names[category]})
    return options


def render_reconstruction(job, snapshot):
    try:
        scene = build_scene(job, snapshot, max_points=20000, max_tracks=180, include_annotated_video=False)
    except (OSError, ValueError) as exc:
        st.info("The comparison needs tracked observations: "+str(exc))
        return
    if not scene["tracks"]:
        st.warning("No stable vehicle tracks were recorded. A synchronized 3D vehicle animation cannot be reconstructed from empty tracking data.")
        return
    report = road_report(snapshot.get("evidence",{}),snapshot.get("label","video"),
                         getattr(job,"objects_file",None))
    with st.spinner("Preparing the ORIGINAL video for synchronized comparison..."):
        video_uri, video_status = prepare_source_video(job)
    options = _simulation_options(report)
    from scene_background import background_photo
    with st.spinner("Matching the source camera and removing many moving vehicles from the reference..."):
        background_uri, background_origin = background_photo(job, scene["image"])
    data = {
        "tracks": scene["tracks"], "options": options,
        "initialOption": options[0]["id"] if options else "none",
        "duration": float(snapshot.get("duration_seconds") or scene["duration"]),
        "videoStatus": video_status,
        "originalDimensions": [scene["width"],scene["height"]],
        "backgroundImage": background_uri,
        "backgroundOrigin": background_origin,
    }
    html = VIEWER.replace("__VIDEO_URL__",escape(video_uri or "",quote=True)).replace(
        "__SCENE__",json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("</","<\\/"))
    st.iframe(html,height="content",alt="Original recorded video versus modified low-poly 3D highway simulation with synchronized playback and source-camera image reprojection")
    if not video_uri:
        st.info("Large or unavailable original recording: select the same video from your device inside the comparison. This allows local synchronized playback without exposing the upload publicly.")
    st.caption("Source View uses the actual road camera background ("+background_origin+") with source-aligned 3D vehicles and editable changes. Orbit and Top View use estimated volumetric geometry; exact road depth and unseen surfaces remain unknown.")
