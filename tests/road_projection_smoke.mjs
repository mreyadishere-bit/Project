/* Browser-engine mathematical regression test using real Three.js objects.
   The camera and imageToGround code are EXTRACTED from road_compare3d.py:
   this test would FAIL on the previous missing updateMatrixWorld bug. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const THREE = await import("file:///tmp/smart-road-three/node_modules/three/build/three.module.js");
const source = readFileSync("road_compare3d.py", "utf8");
const take = (a,b)=>{
    const start=source.indexOf(a),end=source.indexOf(b,start+a.length);
    assert.ok(start>=0&&end>start,"Missing current renderer snippet: "+a);
    return source.slice(start,end);
};
const cameraSource=take(
    " const sourceCamera=new THREE.PerspectiveCamera(",
    " camera.position.copy(sourceCamera.position);"
);
const projectorSource=take(
    " const raycaster=new THREE.Raycaster();",
    " // Normalized source-visible road boundaries;"
);
const boundariesSource=take(
    " const anchors=[",
    " const mat="
);
const factory = new Function("THREE","frameWidth","frameHeight",
    cameraSource+"\n"+projectorSource+"\n"+boundariesSource+
    "\nreturn {sourceCamera,imageToGround,sampleEdge};"
);
const {sourceCamera,imageToGround,sampleEdge}=factory(THREE,960,540);
assert.ok(sourceCamera.matrixWorld.elements[13]>20,"Camera world translation must contain the elevated camera height");
let tested=0;
for(const v of [.36,.42,.50,.60,.73,.86]){
    const positions=[];
    for(const edge of ["left","innerLeft","innerRight","right"]){
        const x=sampleEdge(edge,v),p=imageToGround(x,v);
        assert.ok(p&&Number.isFinite(p.x)&&Number.isFinite(p.z),
                  "No road ray/ground intersection at "+edge+" "+v);
        const ndc=p.clone().project(sourceCamera);
        assert.ok(Math.abs((ndc.x+1)/2-x)<1e-5,"Roadpoint X must reproject to ORIGINAL PIXEL");
        assert.ok(Math.abs((1-ndc.y)/2-v)<1e-5,"Roadpoint Y must reproject to ORIGINAL PIXEL");
        positions.push(p);
        tested++;
    }
    const lateral=Math.hypot(positions[0].x-positions[3].x,
                              positions[0].z-positions[3].z);
    assert.ok(lateral>3,"Road width collapsed to a near-zero line at v="+v);
}
const near=imageToGround(.5,.83),far=imageToGround(.5,.37);
assert.ok(near&&far);
assert.ok(near.distanceTo(far)>20,
          "Video depth must produce a substantial 3D road surface (not sky/grass only)");
assert.ok(source.includes("geometryHealth.roadSections!==3"),
          "Road mesh must explicitly reject missing or degenerate surfaces");
console.log("SUCCESS:",tested,"real Three.js pixel-ray/ground intersections, stable widths and depths");
