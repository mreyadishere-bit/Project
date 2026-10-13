import {chromium} from "playwright";
import assert from "node:assert/strict";

const browser=await chromium.launch({
  headless:true,
  args:["--use-gl=angle","--use-angle=swiftshader","--enable-webgl",
        "--enable-unsafe-swiftshader"]
});
const page=await browser.newPage({viewport:{width:1350,height:920},deviceScaleFactor:1});
const errors=[];
page.on("pageerror",e=>errors.push(e.message));
try{
 await page.goto("http://127.0.0.1:8123/survey.html",{waitUntil:"domcontentloaded"});
 await page.locator("#view canvas").waitFor({state:"visible",timeout:45000});
 await page.waitForFunction(()=>document.querySelector("#loading")?.hidden===true,
                            {timeout:45000});
 const stats=await page.locator("#stats").textContent();
 assert.match(stats,/Surveyed flat patch 8\.0 m × 25\.0 m/,
             "The road viewer must use the supplied surveyed real dimensions");
 assert.match(stats,/Camera fit RMSE/,
             "Camera fit quality must be shown, not hidden");
 assert.match(stats,/visible tracked meshes/,
             "Actual tracked-world car mesh replay must be live");
 const projectionText=await page.locator("#projectionStatus").textContent();
 const reprojection=Number(projectionText.match(/([\d.]+) px RMSE/)?.[1]);
 assert.ok(Number.isFinite(reprojection)&&reprojection<6,
    "Actual Three.js measured-road reprojection must agree with surveyed source frame: "+projectionText);
 await page.locator("#mode").selectOption("signal");
 await page.waitForTimeout(450);
 const scenario=await page.locator("#stats").textContent();
 assert.match(scenario,/HYPOTHETICAL/,"Surveyed road must show an optional functional signal concept");
 assert.match(scenario,/simulated vehicles/,"Simulated traffic must stay separate from observed tracks");
 await page.locator("#mode").selectOption("observed");
 await page.locator("#top").click();
 await page.waitForTimeout(350);
 await page.screenshot({path:"surveyed-road-top.png",fullPage:true});
 await page.locator("#sourceview").click();
 await page.waitForTimeout(350);
 const restored=await page.locator("#projectionStatus").textContent();
 const restoredError=Number(restored.match(/([\d.]+) px RMSE/)?.[1]);
 assert.ok(restoredError<6,"Source camera reset must restore actual PnP pose: "+restored);
 await page.screenshot({path:"surveyed-road-source.png",fullPage:true});
 assert.equal(await page.locator("#view canvas").count(),1);
 assert.deepEqual(errors,[],"Browser JS errors must not be silently masked");
 console.log("Surveyed 3D scene actually rendered: road-scale geometry, source-pose camera and moving calibrated agents.");
}finally{await browser.close()}
