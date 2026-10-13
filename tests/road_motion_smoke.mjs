/* Test browser animation logic from the deployed renderer, not a copied helper. */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const src=readFileSync("road_compare3d.py","utf8");
const start=src.indexOf(" function prepareMotion(points){");
const end=src.indexOf(" function update3D(currentTime){",start);
assert.ok(start>0&&end>start,"Motion code missing from browser renderer");
const source=src.slice(start,end);
const {prepareMotion,interpolateMotion,roadHeading}=new Function(source+
    "\nreturn {prepareMotion,interpolateMotion,roadHeading};")();
const p=(t,x=.4,y=.7)=>[t,x,y,.055,.075];

const observations=[
 p(0,.35,.80),p(.2,.36,.78),p(.4,.37,.76),
 p(.6,.99,.08), // isolated wrong tracker coordinate: corrected from neighbors
 p(.8,.39,.72),p(1,.4,.70),p(1.2,.41,.68),
 p(1.4,.86,.30),p(1.6,.87,.28),p(1.8,.88,.26),p(2,.89,.24)
];
const chunks=prepareMotion(observations);
assert.equal(chunks.length,2,"Sustained ID jumps must separate tracks, not teleport a car");
assert.ok(chunks[0].some(pt=>Math.abs(pt[0]-.6)<.0001&&pt[1]<.5),
          "Single isolated box jump should be smoothed");
assert.ok(interpolateMotion(chunks,1.3)===null,
          "Gap between distinct motion segments must contain no imagined car");
assert.equal(interpolateMotion(chunks,0).alpha,0,
            "A vehicle must not pop in fully opaque on its first detected frame");
assert.ok(interpolateMotion(chunks,.4).alpha>.9,
          "Vehicle should be fully visible after its fade-in interval");
assert.ok(interpolateMotion(chunks,1.18).alpha<.1,
          "Car should fade away as track finishes");
assert.ok(interpolateMotion(chunks,1.42).alpha<.1,
          "Reappearing car should fade in instead of teleporting");
assert.equal(interpolateMotion(chunks,3),null,
             "Cars outside observed time range must stay hidden");
assert.deepEqual(prepareMotion([p(0),p(.2)]),[],
                 "One or two noisy detections should not spawn 3D cars");
assert.ok(source.includes("sampleEdge"),"Car heading must follow lane centerline, not box jitter");
assert.ok(!src.includes('Math.atan2(-delta.x,-delta.z);entry.obj.rotation.y'),
          "Remove direct instantaneous per-frame noisy heading");
assert.ok(src.includes('id="modelLoading"') && src.includes("backgroundReady.then"),
          "Loading state must wait for a first rendered frame and the source road photo");
console.log("Motion regression passed: fade, stable segments, jitter filtering, lane heading and loading lifecycle");
