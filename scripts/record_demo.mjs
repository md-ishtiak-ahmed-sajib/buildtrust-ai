import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=require('@playwright/test');
const base=process.env.BUILDTRUST_RECORDING_BASE_URL;
const runtime=process.env.BUILDTRUST_RECORDING_RUNTIME;
if(!base||!runtime)throw new Error('Use scripts/record_demo.py to provision a private recording runtime.');
const address=new URL(base),folder=path.resolve(runtime);
if(!['127.0.0.1','localhost'].includes(address.hostname)||address.port==='8000'||folder===path.join(root,'data')||!folder.startsWith(path.join(root,'data')+path.sep))throw new Error('A separate local recording runtime and port are required.');
const marker=JSON.parse(await fs.readFile(path.join(folder,'recording-runtime.json'),'utf8'));
if(marker.purpose!=='isolated-recording'||marker.base_url!==base||path.resolve(marker.database)!==path.join(folder,'buildtrust.db'))throw new Error('Recording marker does not match the supplied address.');
const credentials=JSON.parse(await fs.readFile(path.join(folder,'demo-credentials.json'),'utf8'));
const timing=JSON.parse(await fs.readFile(path.join(root,'data/media/timing.json'),'utf8'));
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({extraHTTPHeaders:{'X-BuildTrust-Request':'1'},viewport:{width:1440,height:1000},recordVideo:{dir:path.join(root,'data/media/raw'),size:{width:1440,height:1000}},reducedMotion:'reduce'});
const page=await context.newPage();

const admin=await context.request.post(base+'/api/v1/auth/login',{data:{email:'admin@buildtrust.demo',password:credentials['admin@buildtrust.demo']}});
if(!admin.ok())throw new Error('Private recording authentication failed');
const factors=JSON.parse(await fs.readFile(path.join(folder,'mfa-testing-credentials.json'),'utf8'));
const adminStep=await admin.json();const adminAuth=await context.request.post(base+'/api/v1/auth/mfa/verify',{data:{challenge_token:adminStep.challenge_token,code:factors['admin@buildtrust.demo'].codes.shift()}});
if(!adminAuth.ok())throw new Error('Private recording second-factor authentication failed');
const adminHeaders={Authorization:'Bearer '+(await adminAuth.json()).access_token};
const upgradeResponse=await context.request.post(base+'/api/v1/advanced/demo-project?new_run=true',{headers:adminHeaders});
if(!upgradeResponse.ok())throw new Error('Private upgrade fixture failed');
const upgrade=await upgradeResponse.json();
async function login(role){const email=role+'@buildtrust.demo';await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(credentials[email]);await page.getByRole('button',{name:'Sign in to workspace'}).click();if(factors[email]){await page.getByRole('heading',{name:'Verify your authenticator'}).waitFor();await page.getByLabel('Authenticator or recovery code',{exact:true}).fill(factors[email].codes.shift());await page.getByRole('button',{name:'Verify and continue'}).click();}await page.getByRole('button',{name:'Sign out',exact:true}).waitFor()}
const actions=[
 async()=>{await page.goto(base);await login('operator');await page.getByRole('link',{name:'Overview',exact:true}).click()},
 async()=>{await page.getByRole('link',{name:'Documents',exact:true}).click();await page.getByRole('button',{name:/BOQ boq.json/}).click();await page.getByRole('button',{name:'Field provenance',exact:true}).click()},
 async()=>{await page.getByRole('link',{name:'Invoice Intelligence',exact:true}).click();await page.getByRole('button',{name:/INV-STEEL-095/}).click();await page.getByRole('button',{name:'Run financial workflow'}).click();await page.getByText('Quantity Mismatch',{exact:true}).waitFor()},
 async()=>{await page.getByRole('heading',{name:'Why was this blocked?'}).scrollIntoViewIfNeeded();await page.getByRole('button',{name:'Ask',exact:true}).click();await page.locator('.copilot-answer').waitFor();await page.locator('.copilot-answer').scrollIntoViewIfNeeded()},
 async()=>{await page.getByRole('button',{name:/INV-CEMENT-070/}).click();await page.getByRole('button',{name:'Run financial workflow'}).click();await page.getByRole('link',{name:'Open prepared payment'}).waitFor();await page.getByRole('heading',{name:'Financial workflow',exact:true}).scrollIntoViewIfNeeded()},
 async()=>{await page.getByRole('link',{name:'Open prepared payment'}).click();await page.getByRole('heading',{name:/Proposal #/}).waitFor()},
 async()=>{await page.getByRole('button',{name:'Sign out',exact:true}).click();await login('manager');await page.getByRole('link',{name:'Payment Center',exact:true}).click();await page.getByRole('button',{name:'Approve payment',exact:true}).click();await page.getByRole('button',{name:'Confirm',exact:true}).click();await page.getByRole('button',{name:'Execute simulation'}).click();await page.getByRole('button',{name:'Confirm',exact:true}).click();await page.getByRole('dialog',{name:'Simulated payment receipt'}).waitFor()},
 async()=>{await page.getByRole('button',{name:'Close dialog'}).click();await page.getByRole('button',{name:'Sign out',exact:true}).click();await login('operator');await page.getByLabel('Select project').selectOption(String(upgrade.project_id));await page.getByRole('link',{name:'BOQ & Estimates',exact:true}).click();await page.locator('.boq-material-links').getByRole('button').click();const drawer=page.getByRole('dialog',{name:'Material price comparison'});await drawer.getByLabel('Source mode').selectOption('DEMO');await drawer.getByRole('button',{name:'Search prices',exact:true}).click();await drawer.locator('.quote-card.recommended').getByRole('button',{name:'Use this price'}).click();await drawer.getByRole('region',{name:'Confirm selected rate'}).getByRole('button',{name:'Confirm and recalculate'}).click();await page.getByText('520,000.00',{exact:true}).first().scrollIntoViewIfNeeded()},
 async()=>{await page.getByRole('link',{name:'Audit & Security',exact:true}).click();await page.getByRole('button',{name:'Verify audit chain'}).click();await page.getByText('Chain verified',{exact:true}).waitFor()}
];
const started=Date.now(),actual=[];
try{for(let i=0;i<actions.length;i++){await actions[i]();actual.push({scene:i+1,title:timing[i].title,actual_started_seconds:(Date.now()-started)/1000});console.log(`Recording scene ${i+1}/9: ${timing[i].title}`);const until=timing[i].start+timing[i].duration;const remaining=until*1000-(Date.now()-started);if(remaining>0)await page.waitForTimeout(remaining)}
 const video=page.video();await context.close();await video.saveAs(path.join(root,'data/media/browser-recording.webm'));await fs.writeFile(path.join(root,'data/media/recording.json'),JSON.stringify({recorded_at:new Date().toISOString(),actual_scenes:actual,simulation:true,source:'Actual Playwright browser recording',runtime:folder,base_url:base,working_database_reset:false,app_source_files:marker.app_source_files,app_source_fingerprint:marker.app_source_fingerprint},null,2));
}finally{await browser.close()}
