import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=process.env.BUILDTRUST_ARTIFACT_RUNTIME;
const skill=process.env.BUILDTRUST_PRESENTATIONS_SKILL;
if(!runtime||!skill)throw new Error('Set BUILDTRUST_ARTIFACT_RUNTIME and BUILDTRUST_PRESENTATIONS_SKILL to the optional document runtime and presentation helper directories. This optional deck builder is independent of app startup.');
const modules=path.join(runtime,'node/node_modules');process.env.RUNTIME_NODE_MODULES=modules;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(modules,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {resolvePresentationFont,finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const font=resolvePresentationFont({sourceFont:'Arial'});
const checks=JSON.parse(await fs.readFile(path.join(root,'submission/execution-evidence/verification-summary.json'),'utf8'));
const build=path.join(root,'data/presentation-build');await fs.mkdir(build,{recursive:true});
const slidesDir=path.join(root,'submission/presentation-preview');await fs.mkdir(slidesDir,{recursive:true});
const p=Presentation.create({slideSize:{width:1280,height:720}});
const navy='#19343F',teal='#286E62',ink='#29434D',muted='#60777D',cream='#F7F9F7';
function text(s,value,x,y,w,h,size=28,color=ink,bold=false){const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});sh.text=value;sh.text.style={typeface:font,fontSize:size,color,bold};return sh;}
function slide(title,note,{dark=false}={}){const s=p.slides.add();s.background.fill=dark?navy:cream;if(title)text(s,title,72,62,1136,86,44,dark?'#FFFFFF':navy,true);text(s,`BuildTrust AI  ·  Fictional sandbox demonstration`,72,673,1000,22,16,dark?'#BDD1C9':muted);text(s,String(p.slides.items.length).padStart(2,'0'),1175,673,40,22,16,dark?'#BDD1C9':muted);s.speakerNotes.text=note;return s;}
async function image(s,file,x,y,w,h,alt){const bytes=await fs.readFile(path.join(root,file));s.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt,fit:'contain',position:{left:x,top:y,width:w,height:h}});}
function table(s,values,x,y,w,h,widths){const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});t.borders.assign({fill:'#D9E4DE',width:1,style:'solid'});for(let r=0;r<values.length;r++){for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.fill=r===0?navy:r%2?'#FFFFFF':'#EDF3EF';cell.text.style={typeface:font,fontSize:24,color:r===0?'#FFFFFF':ink,bold:r===0};}}return t;}
function box(s,label,x,y,w,h){const sh=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:'#EDF3EF',line:{fill:'#87A99C',width:1}});sh.text=label;sh.text.style={typeface:font,fontSize:26,color:ink};return sh;}

let s=slide('',`0:00–0:40. BuildTrust AI helps construction teams check costs and review payments. This is a working local app, not a set of sample screen designs. Its records and calculations are real application operations, but the projects and transfers are fictional. No bank is connected. A visitor can start the separate public demo and use the four passwords in the README. Explain that people approve financial actions. Give the audience a moment to read the product name. Sources: README.md; features.md; docs/technical-documentation.md.`,{dark:true});
text(s,'BuildTrust AI',72,147,1060,108,80,'#FFFFFF',true);
text(s,'Construction costs\nand payment review',76,280,1080,128,44,'#E2ECE7');
text(s,'Clear evidence for construction finance.',78,475,1020,68,27,'#A8CDC0');
text(s,'2026 Shenzhen FinTechathon  ·  International Track  ·  Topic E',78,582,1100,42,23,'#BDD1C9');

s=slide('Four records before payment',`0:40–1:30. A bill of quantities lists approved quantities. A purchase order records what was ordered and at what rate. A delivery receipt records accepted supply. An invoice states what the supplier wants to be paid. These records answer different questions. The invoice alone cannot prove that goods arrived or that the amount is authorized. Point to the pictured fictional invoice, then explain that the app keeps the original file and its source references. Uploaded words such as approved do not grant authority. Sources: docs/technical-documentation.md; demo/fixtures/scenario-a-inflated.pdf; docs/financial-rules.md.`);
text(s,'The records must agree',72,196,610,70,34,navy,true);
text(s,'BOQ: the approved quantities.\n\nPO and receipt: order and delivery.\n\nInvoice: a claim to check.',72,296,610,285,29,muted);
await image(s,'submission/screenshots/10-fictional-invoice-source.png',790,160,343,486,'Actual generated fictional supplier invoice source PDF');

s=slide('Cash and the minimum reserve',`1:30–2:20. A valid invoice can still be unsafe to pay today. The app checks recorded cash and daily forecasts. Both the base forecast and the delayed-customer-receipts forecast must keep the required reserve. In the stress example, cash is BDT 150,000 and the invoice is 70,000. Paying would leave 80,000, below the 100,000 reserve, so payment is blocked. Future expected receipts are not cash already received. Explain the three visible scenarios and the matching daily table. The pictured chart comes from a separate actual test run. Sources: scenario-e.json; screenshots/05-cashflow.png; docs/financial-rules.md.`);
text(s,'A correct invoice may\nneed to wait for cash.',72,188,430,140,37,navy,true);
text(s,'BDT 100,000',72,366,440,72,48,teal,true);
text(s,'Minimum cash kept in the demo',76,444,410,64,24,muted);
text(s,'Base and delayed receipts must pass.\nHigher future costs show a warning.',76,548,430,78,23,muted);
await image(s,'submission/screenshots/05-cashflow.png',535,174,673,453,'Actual cash flow interface with persisted base, delay and cost scenarios');

s=slide('Payment review',`2:20–3:15. Follow the saved steps from documents to payment. The app reads actual files, compares approved records and checks risks and cash using fixed rules. If everything passes, it prepares an exact proposal and reserves the required cash and delivery quantity. It then waits. A different authorized person must review and approve. Execution needs another explicit confirmation and fresh checks. A failed transaction rolls back its financial changes. The receipt, ledger and audit provide evidence of the outcome. Pause at the approval stage to emphasize that automation cannot cross it. Sources: backend/app/workflow.py; docs/technical-documentation.md; scenarios A and B.`);
text(s,'Approved quantities   +   Order   +   Delivery   +   Invoice',76,190,1120,65,29,navy,true);
text(s,'Read files  →  Compare records  →  Check risks and cash',76,298,1120,72,29,ink);
text(s,'Exact proposal  →  Approval by a different person',76,406,1120,72,33,teal,true);
text(s,'Recheck  →  Simulated payment  →  Receipt, ledger and audit',76,521,1120,81,28,ink);

s=slide('How the app works',`3:15–4:10. The browser has fourteen connected areas. It sends requests to FastAPI, which checks login, current role and project access. Saved workflows call document, quantity, pricing and finance services. The server uses Decimal calculations and stores money as integer minor units. SQLite keeps the records and private files keep the source evidence. Payment, cash, ledger and success audit are saved in one transaction. Optional AI only explains evidence and falls back to built-in text if unavailable. It cannot approve or execute. Point through the diagram and answer where the human decision sits. Sources: docs/architecture.md; docs/architecture.mmd; backend source.`);
box(s,'React / TypeScript\nFinancial workspace',72,205,280,104);
box(s,'FastAPI\nRole and project checks',472,205,350,104);
box(s,'SQLite + audit\nExact money',940,205,268,104);
text(s,'→',378,225,60,60,45,teal);text(s,'→',849,225,65,60,45,teal);
box(s,'Saved workflow\nSteps and evidence',72,430,280,116);
box(s,'Rule-based checks\nClaims, risk and cash',472,430,350,116);
box(s,'Human approval\nPayment record',940,430,268,116);
text(s,'→',378,457,60,60,45,teal);text(s,'→',849,457,65,60,45,teal);
text(s,'↓',610,334,62,65,43,teal);text(s,'↑',1040,334,62,65,43,teal);
text(s,'AI can explain the evidence. People approve financial actions.',75,589,1130,42,23,muted);

s=slide('An inflated steel invoice',`4:10–5:30. Walk through the table slowly. Approved quantities, the order and accepted delivery each support 80 tonnes. The invoice claims 95 at BDT 70,000 per tonne. Supported value is 5,600,000 and the claim is 6,650,000. Subtracting gives 1,050,000. The extra 15 tonnes divided by 80 gives 18.75 percent. The app blocks the unsupported claim and shows the source comparison. Point to the actual UI screenshot and explain its kilogram display conversion. No delivery quantity is consumed by a blocked invoice. The screenshot and HTTP evidence are separate runs with the same verified arithmetic. Sources: scenario-a.json; screenshots/08-four-way-focus.png; docs/financial-rules.md.`);
table(s,[['Record','Tonnes'],['Approved BOQ','80'],['Purchase order','80'],['Accepted delivery','80'],['Supplier invoice','95']],72,190,480,310,[340,140]);
text(s,'BDT 1,050,000',76,526,540,77,49,'#A14B42',true);
text(s,'Extra claim: 18.75% above supported quantity. Payment blocked.',78,605,1100,34,23,'#A14B42');
await image(s,'submission/screenshots/08-four-way-focus.png',590,235,616,310,'Actual blocked steel invoice interface and evidence comparisons');

s=slide('One approved payment',`5:30–6:40. The separate cement invoice passes the quantity, price, supplier and cash checks. An Operator prepares it and a different Finance Manager approves BDT 70,000. A person confirms execution. Cash changes from 1,000,000 to 930,000 once. The mock receipt identifies the simulation. Explain the retry rule: the same request key returns the same result instead of another cash deduction. Amount and beneficiary come from the approval, not a new browser value. All financial updates either save together or roll back together. The receipt screenshot and HTTP scenarios have different run IDs. Sources: scenario-b.json; scenario-h.json; screenshots/09-receipt-focus.png.`);
text(s,'BDT 70,000',72,194,500,90,59,teal,true);
text(s,'One approved simulated payment',76,288,465,62,25,muted);
text(s,'1,000,000 → 930,000',76,401,520,78,37,navy,true);
text(s,'Recorded cash in BDT',78,483,440,45,23,muted);
text(s,'Repeat request: same receipt\nCash changes only once',78,560,490,77,25,teal,true);
await image(s,'submission/screenshots/09-receipt-focus.png',618,174,588,458,'Actual mock receipt generated after authorized sandbox settlement');

s=slide('Checks and limits',`6:40–7:50. The table shows actual local results: ${checks.backend_tests} backend tests, ${checks.frontend_tests} frontend tests, ${checks.browser_workflows} browser workflows and eight original HTTP scenarios. Separate public-demo checks verify four documented logins and preserve the private profile. Tests cover denied roles, changed approvals, expiry, duplicate quantities, competing execution, rollback and retries. Fresh installation checks use a source copy. A passing suite is evidence for tested behavior, not complete security assurance. The audit chain can find inconsistent retained events, but a full database owner can rewrite it. The original twenty-item review and separate nineteen-control checklist cover revocable sessions, private Admin/Finance authenticator MFA, safe browser requests, offline recovery, private backups, secret scans and persistent caps. Public demo accounts stay exempt from MFA and keep the four README passwords. Native database RLS remains deferred; incoming webhooks are not applicable. Independent security and assistive-technology reviews remain separate. Sources: verification-summary.json; test logs; public-demo-install.json; docs/security-self-assessment.md.`);
  text(s,'Independent approval\n\nPrivate Admin / Finance MFA\n\nSafe requests and private files\n\nVerifiable audit evidence',76,202,610,339,28,ink);
table(s,[['Executed validation','Passed'],['Backend tests',String(checks.backend_tests)],['Frontend tests',String(checks.frontend_tests)],['Browser workflows',String(checks.browser_workflows)],['HTTP scenarios A–H','8']],726,188,480,340,[340,140]);
text(s,'A full database owner can rewrite the local audit chain.',76,580,1120,63,23,muted);

s=slide('Price and estimate changes',`7:50–8:50. In the fictional upgrade project, 20 tonnes at 70,000 cost 1,400,000. Selecting an eligible 74,000 rate changes cost to 1,480,000, an increase of 80,000. The scheduled cash forecast drops from 600,000 to 520,000, but recorded cash stays 2,000,000. The wrong grade cannot be selected. A different Manager checks the estimate and a separate Admin approves. Other areas cover quantities, accounting, contracts, installments and separate correction reviews. Paid search, real documents and professional acceptance need their own evidence. The public demo and complete source are available through the README and authorized GitHub repository. Sources: docs/completion-verification.md; upgrade screenshots; verification-summary.json; README.md.`,{dark:true});
text(s,'BDT 80,000',76,190,570,91,54,'#FFFFFF',true);
text(s,'Extra cost for the fictional 20 tonnes',79,289,555,70,28,'#D8E7E0');
text(s,'600,000 to 520,000',76,394,595,68,39,'#A8CDC0',true);
text(s,'Forecast cash in BDT. Recorded cash stays at 2,000,000.',79,471,540,106,26,'#D8E7E0');
await image(s,'submission/screenshots/upgrade-recommended-offer.png',690,210,518,340,'Actual recommended demonstration offer with specification checks');
text(s,'More tools: quantities, contracts, installments and reviewed corrections.',79,592,1120,56,25,'#A8CDC0');

for(const [index,sl] of p.slides.items.entries()){const blob=await p.export({slide:sl,format:'png',scale:1});await fs.writeFile(path.join(slidesDir,`slide-${String(index+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));}
const candidate=path.join(build,`candidate-${Date.now()}.pptx`);await (await PresentationFile.exportPptx(p)).save(candidate);
const canonical=path.join(root,'submission/BuildTrustAI_Presentation.pptx');
const final=process.env.BUILDTRUST_PPTX_OUTPUT?path.resolve(process.env.BUILDTRUST_PPTX_OUTPUT):canonical;
await fs.mkdir(path.dirname(final),{recursive:true});
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:final,
 pythonExecutable:path.join(runtime,'python/python.exe'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','6','--require-native-table-slide','8'],
 explicitTotalSlideCount:9,requiredNativeTableOwnerSlides:[6,8],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
 receiptPath:path.join(build,`validation-${Date.now()}.json`)});
await fs.writeFile(path.join(build,'inspection.ndjson'),(await p.inspect({kind:'slide,textbox,table,notes',maxChars:100000})).ndjson);
if(final!==canonical)await fs.copyFile(final,canonical);
console.log(JSON.stringify({final,slides:p.slides.items.length,font,validation:result},null,2));
