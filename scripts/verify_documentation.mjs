// Optional authoring check. Runtime app startup does not need Marked or Mermaid.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=process.env.BUILDTRUST_ARTIFACT_RUNTIME;
if(!runtime)throw new Error('Set BUILDTRUST_ARTIFACT_RUNTIME to the bundled authoring runtime.');
const {marked}=await import(pathToFileURL(path.join(runtime,'node/node_modules/marked/lib/marked.esm.js')).href);
const require=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=require('@playwright/test');
const mermaid=path.join(root,'data/docs-tools/node_modules/mermaid/dist/mermaid.min.js');
await fs.access(mermaid);
const out=path.join(root,'data/documentation-preview');await fs.mkdir(out,{recursive:true});
const docs=['README.md','features.md',...(await fs.readdir(path.join(root,'docs'),{recursive:true})).filter(n=>n.endsWith('.md')).map(n=>'docs/'+n.replaceAll('\\','/')),'demo/README.md','submission/README.md','submission/submission-checklist.md','submission/screenshots/README.md','submission/execution-evidence/README.md'];
const css=`*{box-sizing:border-box}body{margin:0;background:#f7f9f7;color:#19343f;font:17px/1.65 Arial,sans-serif}article{max-width:1080px;margin:auto;padding:32px 24px}h1{font-size:38px;line-height:1.2}h2{font-size:27px;margin-top:36px}h3{font-size:21px}a{color:#1f6257}img,svg{max-width:100%;height:auto}pre{padding:16px;background:#e8eeeb;overflow:auto;font-size:14px}code{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;min-width:650px;font-size:15px}td,th{text-align:left;padding:12px;border:1px solid #becfc7;vertical-align:top}th{background:#19343f;color:white}.table-wrap{overflow:auto}blockquote{border-left:4px solid #286e62;padding-left:20px}li{margin:8px 0}p{overflow-wrap:anywhere}@media(max-width:600px){article{padding:20px 16px}h1{font-size:30px}h2{font-size:24px}}`;
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1280,height:1000}});
const result={passed:false,documents:[],svg_checks:[],broken_links:[],public_password_table_matches:true};
try{
  const accounts=JSON.parse(await fs.readFile(path.join(root,'demo/public-accounts.json'),'utf8')).accounts;
  const readme=await fs.readFile(path.join(root,'README.md'),'utf8');
  for(const a of accounts)if(!readme.includes('`'+a.email+'`')||!readme.includes('`'+a.password+'`'))throw new Error('README public account differs from fixture: '+a.role);
  for(const name of docs){
    const source=await fs.readFile(path.join(root,name),'utf8');
    for(const match of source.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/g)){
      let target=match[1].replace(/^<|>$/g,'').split('#')[0];
      if(!target||/^(https?:|mailto:)/.test(target))continue;
      target=decodeURIComponent(target);
      const file=/^[A-Za-z]:[\\/]/.test(target)?target:path.resolve(root,path.dirname(name),target);
      try{await fs.access(file)}catch{result.broken_links.push({document:name,target})}
    }
    const html=path.join(out,name.replaceAll('/','-')+'.html');
    await fs.writeFile(html,`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><base href="${pathToFileURL(path.join(root,path.dirname(name))+path.sep).href}"><style>${css}</style></head><body><article>${marked.parse(source)}</article></body></html>`);
    await page.goto(pathToFileURL(html).href);
    await page.evaluate(()=>{
      for(const table of document.querySelectorAll('table')){const w=document.createElement('div');w.className='table-wrap';table.before(w);w.append(table)}
      for(const code of document.querySelectorAll('code.language-mermaid')){const d=document.createElement('div');d.className='mermaid';d.textContent=code.textContent;code.parentElement.replaceWith(d)}
    });
    const diagrams=await page.locator('.mermaid').count();
    if(diagrams){await page.addScriptTag({path:mermaid});await page.evaluate(async()=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral'});await mermaid.run({querySelector:'.mermaid'})})}
    await page.evaluate(async()=>{await Promise.all([...document.images].map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r}))) });
    const images=await page.evaluate(()=>[...document.images].map(i=>({src:i.getAttribute('src'),loaded:i.naturalWidth>0,alt:!!i.alt})));
    if(images.some(i=>!i.loaded||!i.alt))throw new Error('Missing image or alternative text: '+name);
    const record={document:name,mermaid_diagrams:diagrams,images:images.length,rendered:true};
    if(['README.md','features.md','docs/README.md','docs/judges-quickstart.md'].includes(name)){
      await page.screenshot({path:path.join(out,name.replaceAll('/','-')+'.png'),fullPage:true});
      await page.screenshot({path:path.join(out,name.replaceAll('/','-')+'-top.png')});
      await page.setViewportSize({width:390,height:844});
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw new Error('Whole-page mobile overflow: '+name);
      await page.screenshot({path:path.join(out,name.replaceAll('/','-')+'-mobile.png'),fullPage:true});
      await page.screenshot({path:path.join(out,name.replaceAll('/','-')+'-mobile-top.png')});
      await page.setViewportSize({width:1280,height:1000});record.mobile_checked=true;
    }
    result.documents.push(record);
  }
  for(const name of (await fs.readdir(path.join(root,'docs/assets'))).filter(n=>n.endsWith('.svg'))){
    await page.goto(pathToFileURL(path.join(root,'docs/assets',name)).href);
    const issues=await page.evaluate(()=>{const root=document.querySelector('svg'),box=root.viewBox.baseVal;return [...root.querySelectorAll('text')].filter(t=>{const b=t.getBBox();return b.x<0||b.x+b.width>box.width||b.y<0||b.y+b.height>box.height}).map(t=>t.textContent)});
    if(issues.length)throw new Error('Clipped SVG text '+name+': '+issues.join('; '));
    await page.locator('svg').screenshot({path:path.join(out,name+'.png')});
    result.svg_checks.push({name,text_within_bounds:true});
  }
  await page.goto('about:blank');await page.addScriptTag({path:mermaid});
  const architecture=await fs.readFile(path.join(root,'docs/architecture.mmd'),'utf8');
  await page.evaluate(async(source)=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict'});await mermaid.parse(source)},architecture);
  result.architecture_mermaid_parsed=true;
  if(result.broken_links.length)throw new Error('Broken documentation links: '+JSON.stringify(result.broken_links));
  result.passed=true;
  console.log(`Documentation: ${result.documents.length} pages, ${result.svg_checks.length} SVGs, links, image text and mobile checks PASS`);
}finally{await fs.writeFile(path.join(out,'result.json'),JSON.stringify(result,null,2));await browser.close()}
