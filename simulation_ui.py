"""Self-contained 2.5D road animation for scenario teaching, no paid API/CDN."""
from __future__ import annotations

import json
import streamlit as st
from simulation_engine import Scenario, run_simulation

SIM_HTML = r"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;color:#233650;background:#f9fbfd;font:13px -apple-system,BlinkMacSystemFont,Arial,sans-serif}
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
.pill{border:1px solid #dbe5f1;padding:6px 10px;border-radius:30px;font-size:11px;color:#53708e;background:white}
.controls{display:flex;gap:8px;align-items:center}
button{padding:9px 13px;border:1px solid #d8e4f1;border-radius:11px;background:#fff;color:#234364;font-weight:600;cursor:pointer}
button:hover{background:#eaf2ff}
.wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.scene{background:linear-gradient(150deg,#eff5fc,#fff);border:1px solid #e4ebf3;border-radius:18px;overflow:hidden}
.label{padding:16px 18px 0;display:flex;align-items:center;justify-content:space-between}
.label strong{font-size:15px}.subtitle{color:#8493a5;font-size:11px}.after{color:#2b8769}.before{color:#ba8239}
canvas{width:100%;height:auto;display:block}
.foot{padding:11px 18px 17px;border-top:1px solid #e6ecf3;color:#8493a3;font-size:11px;line-height:1.5}
@media(max-width:680px){.wrap{grid-template-columns:repeat(2,minmax(300px,1fr));overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:8px}.scene{scroll-snap-align:start}.scene canvas{height:auto}.top{flex-wrap:wrap}}
</style></head><body>
<div class="top"><span class="pill">ILLUSTRATIVE 2.5D MODEL · NOT THE ACTUAL ROAD</span>
<div class="controls"><span class="pill" id="clock">00:00</span><button id="pause">Pause simulation</button><button id="restart">Restart</button></div></div>
<div class="wrap">
<section class="scene"><div class="label"><strong class="before">Before · current assumptions</strong><span class="subtitle">Unmanaged crossing</span></div><canvas id="before" width="690" height="330"></canvas><div class="foot">Illustration of assumed approach speed and independent road users.</div></section>
<section class="scene"><div class="label"><strong class="after">After · explored intervention</strong><span class="subtitle" id="afterlabel"></span></div><canvas id="after" width="690" height="330"></canvas><div class="foot">Model assumptions only, not a forecast for the recorded road.</div></section>
</div>
<script>
const scenario=__STATE__;
const before=scenario.before, after=scenario.after, params=scenario.parameters;
document.getElementById('afterlabel').textContent=(params.crossing?'Managed crossing':'Original crossing')+' · '+(params.speed_calming?'Speed calming':'Original speed');
const canvases={before:document.getElementById('before'),after:document.getElementById('after')};
let running=true, epoch=performance.now(), hold=0;
const speedFactor=4;
function point(x,z,h=0){return {x:40+5.65*x+1.65*z, y:105+0.36*x+7.45*z-14.5*h}}
function polygon(ctx,arr,fill,stroke){ctx.beginPath();arr.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.stroke()}}
function rect(ctx,x1,z1,x2,z2,h,fill){polygon(ctx,[point(x1,z1,h),point(x2,z1,h),point(x2,z2,h),point(x1,z2,h)],fill)}
function prism(ctx,x,z,len=4,wd=1.9,ht=1.15,colour='#3288bb'){
 const x0=x-len/2,x1=x+len/2,z0=z-wd/2,z1=z+wd/2;
 let p0=point(x0,z0),p1=point(x1,z0),p2=point(x1,z1),p3=point(x0,z1);
 let t0=point(x0,z0,ht),t1=point(x1,z0,ht),t2=point(x1,z1,ht),t3=point(x0,z1,ht);
 polygon(ctx,[p0,p1,t1,t0],'#183b58');polygon(ctx,[p3,p2,t2,t3],colour);
 polygon(ctx,[t0,t1,t2,t3],colour,'#ffffff77');
 rect(ctx,x0+.55,z0+.1,x1-.55,z1-.1,ht+.018,'#bcdff1');
 }
function road(ctx,withCrossing){
 ctx.fillStyle='#f4f8f5';ctx.fillRect(0,0,690,330);
 // Landscape
 for(let i=0;i<11;i++){
    let g=point(i*12,-7);ctx.fillStyle=i%2?'#c7dec3':'#d4e6d1';ctx.beginPath();ctx.arc(g.x,g.y,7+(i%3)*3,0,Math.PI*2);ctx.fill()
 }
 rect(ctx,0,-.9,100,11.4,0,'#b7c3c9');
 rect(ctx,0,0,100,10,0,'#3c4b5b');
 rect(ctx,0,.15,100,.32,.07,'#f4f6fa');
 rect(ctx,0,9.68,100,9.85,.07,'#f4f6fa');
 for(let i=2;i<100;i+=9)rect(ctx,i,4.93,i+4,5.06,.06,'#e6eef6');
 if(withCrossing)for(let z=.8;z<9.4;z+=1.15)rect(ctx,49.3,z,52.8,z+.64,.09,'#f3f8fe');
 // Sign on the sidewalk
 if(withCrossing){
   const base=point(46,-2);ctx.strokeStyle='#60798a';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(base.x,base.y);ctx.lineTo(base.x,base.y-32);ctx.stroke();
   ctx.fillStyle='#2173c7';ctx.fillRect(base.x-9,base.y-44,18,14);ctx.fillStyle='#fff';ctx.font='bold 13px Arial';ctx.fillText('P',base.x-4,base.y-32)
 }
 }
function drawPeople(ctx,data,t,isAfter){
 let people=data.pedestrian_crossings;
 for(let i=0;i<people.length;i++){
   const [start,end]=people[i];if(t<start||t>end)continue;
   let q=(t-start)/Math.max(.1,end-start);
   const pt=point(51.4,-.8+q*11.3);
   ctx.beginPath();ctx.ellipse(pt.x,pt.y-8,2.8,5,0,0,Math.PI*2);
   ctx.fillStyle='#db8150';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=2;
   ctx.beginPath();ctx.moveTo(pt.x,pt.y-5);ctx.lineTo(pt.x,pt.y+4);ctx.stroke();
 }
 }
function paint(name,data,t){
 const canvas=canvases[name],ctx=canvas.getContext('2d');
 ctx.clearRect(0,0,canvas.width,canvas.height);road(ctx,name==='after'&&params.crossing);
 let mps=data.vehicle_speed_kmh_assumed/3.6, cars=data.vehicle_entries;
 for(let i=0;i<cars.length;i++){
   let x=(t-cars[i])*mps-5;
   if(x<0||x>108)continue;
   let lane=(i%2===0)?2.7:7.3;
   const colours=['#4f87c4','#eeab6d','#6bb3ae','#56667e','#bd7483'];
   prism(ctx,x,lane,4.25,1.95,1.05,colours[i%colours.length]);
 }
 drawPeople(ctx,data,t,name==='after');
 ctx.fillStyle='#fff';ctx.font='bold 12px Arial';ctx.fillText('MODELED SPEED  '+data.vehicle_speed_kmh_assumed+' km/h',19,20);
 ctx.fillStyle='#7e8c9d';ctx.font='12px Arial';ctx.fillText('Schematic 100 m road — not georeferenced',19,314);
}
function time(){
 if(running)hold=(performance.now()-epoch)/1000*speedFactor;
 const t=hold%params.duration_seconds;
 document.getElementById('clock').textContent=String(Math.floor(t/60)).padStart(2,'0')+':'+String(Math.floor(t%60)).padStart(2,'0');
 paint('before',before,t);paint('after',after,t);
 requestAnimationFrame(time);
}
document.getElementById('pause').onclick=()=>{
 running=!running;if(running)epoch=performance.now()-hold/speedFactor;
 document.getElementById('pause').textContent=running?'Pause simulation':'Resume simulation';
};
document.getElementById('restart').onclick=()=>{hold=0;epoch=performance.now()};
requestAnimationFrame(time);
</script></body></html>
"""


def simulation_panel():
    st.markdown("### Model improvements · Explore a road scenario")
    st.caption("An interactive simplified 2.5D traffic model. Change the controls to see what *could* happen under stated assumptions. This is not a reconstruction from your footage.")
    a,b,c=st.columns(3)
    with a:
        speed=st.slider("Assumed approach speed (km/h)",20,90,45,5,key="sim_speed")
        cars=st.slider("Assumed vehicles/hour",100,1800,650,50,key="sim_cars")
    with b:
        people=st.slider("Assumed pedestrians/hour",0,700,180,20,key="sim_peds")
        calm=st.checkbox("Apply speed calming",value=True,key="sim_calm")
    with c:
        crossing=st.checkbox("Provide managed pedestrian crossing",value=True,key="sim_crossing")
        target=st.slider("Intervention speed target (km/h)",15,60,28,1,key="sim_target",disabled=not calm)
    result=run_simulation(Scenario(approach_speed_kmh=speed,cars_per_hour=cars,
                 pedestrians_per_hour=people,crossing=crossing,speed_calming=calm,target_speed_kmh=target))
    before,after=result["before"],result["after"]
    w,x,y=st.columns(3)
    w.metric("Modeled interaction windows",f"{before['modeled_interaction_windows']} → {after['modeled_interaction_windows']}",
             help="Possible temporal crossing overlaps in a toy model; not verified near misses.")
    x.metric("Pedestrian waiting (mean)",f"{before['mean_pedestrian_wait_s']:.0f} → {after['mean_pedestrian_wait_s']:.0f} s",
             help="Crossing control can increase time spent waiting; not a prediction of a particular site.")
    y.metric("100 m travel time",f"{before['road_segment_travel_time_s']:.1f} → {after['road_segment_travel_time_s']:.1f} s",
             help="Modeled movement on a 100 m link at constant assumed speed.")
    html=SIM_HTML.replace("__STATE__",json.dumps(result,separators=(",",":")).replace("</","<\\/"))
    st.iframe(html, height="content", alt="Animated before-and-after isometric traffic scenario; all figures are illustrative")
    with st.expander("Exactly how the illustrative simulation works"):
        st.write(result["methodology"])
        st.caption("The results are controlled by manually selected inputs, not fitted to the uploaded video. Similar-looking results can occur under very different real-world conditions.")
    st.download_button("Download modeled scenario inputs and results (JSON) ↓",
                       json.dumps(result,indent=2), "illustrative-traffic-simulation.json",
                       "application/json",key="sim_download")
