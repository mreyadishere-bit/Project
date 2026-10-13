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
 await page.locator("#top").click();
 await page.waitForTimeout(350);
 await page.screenshot({path:"surveyed-road-top.png",fullPage:true});
 await page.locator("#sourceview").click();
 await page.waitForTimeout(350);
 await page.screenshot({path:"surveyed-road-source.png",fullPage:true});
 assert.equal(await page.locator("#view canvas").count(),1);
 assert.deepEqual(errors,[],"Browser JS errors must not be silently masked");
 console.log("Surveyed 3D scene actually rendered: road-scale geometry, source-pose camera and moving calibrated agents.");
}finally{await browser.close()}
