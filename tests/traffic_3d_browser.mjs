import {chromium} from 'playwright';
import assert from 'node:assert/strict';

const browser=await chromium.launch({
 headless:true,
 args:['--use-gl=angle','--use-angle=swiftshader',
       '--enable-webgl','--enable-unsafe-swiftshader']
});
const page=await browser.newPage({viewport:{width:1450,height:950},deviceScaleFactor:1});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text())});
try{
 await page.goto('http://127.0.0.1:8123/scene.html',{waitUntil:'domcontentloaded'});
 await page.locator('#simulation canvas').waitFor({state:'visible',timeout:40000});
 await page.waitForFunction(()=>document.getElementById('loading')?.hidden===true,
                            {timeout:45000});
 assert.equal(await page.locator('#simulation canvas').count(),1);
 const initial=(await page.locator('#phase').textContent()).toLowerCase();
 assert.ok(initial.includes('vehicle green'),'Wrong initial phase: '+initial);
 await page.screenshot({path:'road3d-green.png',fullPage:true});
 await page.locator('#seek').evaluate(element=>{
    element.value='770';element.dispatchEvent(new Event('input',{bubbles:true}));
 });
 await page.waitForTimeout(600);
 const phase=(await page.locator('#phase').textContent()).toLowerCase();
 assert.ok(phase.includes('pedestrian walk'),'No WALK phase in browser: '+phase);
 const text=await page.locator('#control').textContent();
 assert.match(text,/Vehicles STOP/,'Traffic must stop during pedestrian WALK');
 await page.screenshot({path:'road3d-pedestrian-walk.png',fullPage:true});
 await page.locator('#toggle').click();
 assert.match(await page.locator('#toggle').textContent(),/Play simulation/);
 await page.locator('#topview').click();
 assert.match(await page.locator('#topview').textContent(),/Perspective/);
 if(errors.some(e=>/webgl|three|uncaught|typeerror/i.test(e)))
   throw new Error('Browser runtime errors: '+errors.join(' || '));
 console.log('Verified: actual 3D scene, signal phases, play/pause and top view');
}finally{
 await browser.close();
}
