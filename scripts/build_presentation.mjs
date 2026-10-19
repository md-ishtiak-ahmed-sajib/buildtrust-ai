import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=process.env.BUILDTRUST_ARTIFACT_RUNTIME;
const skill=process.env.BUILDTRUST_PRESENTATIONS_SKILL;
if(!runtime||!skill)throw new Error('Set BUILDTRUST_ARTIFACT_RUNTIME and BUILDTRUST_PRESENTATIONS_SKILL to the bundled Codex runtime and presentation skill directories. This optional deck builder is independent of app startup.');
const modules=path.join(runtime,'node/node_modules');process.env.RUNTIME_NODE_MODULES=modules;
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(modules,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {resolvePresentationFont,finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const font=resolvePresentationFont();
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

let s=slide('',`0:00–0:40. Introduce the construction SME problem and the exact product boundary. BuildTrust AI performs real local document, finance, authorization and ledger operations. All settlement is simulated. Source: prompt/prompt.md and README.md.`,{dark:true});
text(s,'BuildTrust AI',72,147,1060,108,80,'#FFFFFF',true);
text(s,'An autonomous construction\nfinance copilot',76,280,1080,128,44,'#E2ECE7');
text(s,'From Construction Documents to Secure Financial Decisions.',78,475,1020,68,27,'#A8CDC0');
text(s,'2026 Shenzhen FinTechathon  ·  International Track  ·  Topic E',78,582,1100,42,23,'#BDD1C9');

s=slide('The construction payment problem',`0:40–1:30. A BOQ establishes scope, a PO records contracted supply, a GRN certifies accepted delivery, and an invoice states the supplier claim. Neither estimates nor an invoice alone establish entitlement. This is the business problem; do not invent market-size or loss statistics. Source: prompt/prompt.md; demo/fixtures/scenario-a-inflated.pdf. The pictured record is fictional.`);
text(s,'Evidence for supplier entitlement',72,196,610,70,34,navy,true);
text(s,'A purchase order establishes the contract.\n\nAn accepted receipt supports entitlement.\n\nAn invoice still needs verification.',72,296,610,285,29,muted);
await image(s,'submission/screenshots/10-fictional-invoice-source.png',790,160,343,486,'Actual generated fictional supplier invoice source PDF');

s=slide('Entitlement and liquidity',`1:30–2:20. Two independent tests are required: is the supplier entitled to the claimed amount, and can the company preserve its cash reserve? The stress project has BDT 150,000 and a valid BDT 70,000 claim, leaving BDT 80,000 versus a BDT 100,000 reserve. The screenshot is a separate actual browser test run. Sources: submission/execution-evidence/scenario-e.json and screenshots/05-cashflow.png.`);
text(s,'A valid invoice can still\nbe unsafe to pay today.',72,188,430,140,37,navy,true);
text(s,'BDT 100,000',72,366,440,72,48,teal,true);
text(s,'Required demonstration cash reserve',76,444,410,64,24,muted);
text(s,'Base and delayed receivables must pass.\nCost-pressure scenarios remain visible.',76,548,430,78,23,muted);
await image(s,'submission/screenshots/05-cashflow.png',535,174,673,453,'Actual cash flow interface with persisted base, delay and cost scenarios');

s=slide('A complete financial workflow',`2:20–3:15. Explain the actual persisted workflow. Intake and extraction read actual files; matching, risk and cash flow invoke deterministic services; a successful workflow prepares and reserves a proposal and pauses for a different human. Execution occurs only via an explicit authenticated API action. Audit evidence records each transition. Sources: backend/app/workflow.py; technical-documentation.md; actual scenario A/B workflow steps.`);
text(s,'BOQ     +     Purchase order     +     Accepted receipt     +     Invoice',76,190,1120,65,29,navy,true);
text(s,'Extract and review  →  Reconcile  →  Assess risk  →  Check liquidity',76,298,1120,72,29,ink);
text(s,'Prepare exact payment  →  Independent human approval',76,406,1120,72,33,teal,true);
text(s,'Revalidate  →  Atomic sandbox settlement  →  Ledger and audit evidence',76,521,1120,81,28,ink);

s=slide('System architecture',`3:15–4:10. The UI calls FastAPI with database-enforced identity and project access. The persisted state machine invokes deterministic engines. Approval and execution are separate human actions. SQLite commits payment, cash, subledger and success audit evidence atomically. Optional Ollama prose has no payment credentials or write tools. The diagram consists of editable native slide objects. Source: docs/architecture.mmd and actual backend source.`);
box(s,'React / TypeScript\nFinancial workspace',72,205,280,104);
box(s,'FastAPI\nRole + project authorization',472,205,350,104);
box(s,'SQLite + audit\nExact money',940,205,268,104);
text(s,'→',378,225,60,60,45,teal);text(s,'→',849,225,65,60,45,teal);
box(s,'Persisted workflow\nTyped tool steps',72,430,280,116);
box(s,'Deterministic engines\nMatching · risk · cash flow',472,430,350,116);
box(s,'Human approval\nIdempotent payment',940,430,268,116);
text(s,'→',378,457,60,60,45,teal);text(s,'→',849,457,65,60,45,teal);
text(s,'↓',610,334,62,65,43,teal);text(s,'↑',1040,334,62,65,43,teal);
text(s,'Optional model: explanation only. Financial authority stays in deterministic code.',75,589,1130,42,23,muted);

s=slide('Inflated steel invoice detected',`4:10–5:30. Walk through Scenario A. BOQ, PO and accepted delivery each support 80 tonnes; invoice claims 95 tonnes at BDT 70,000/tonne. Supported amount is 5,600,000; claim is 6,650,000; excess is 1,050,000 and 18.75%. Deterministic blocking findings prevent preparation/settlement. The screenshot comes from an actual UI run, and the separate HTTP evidence reproduces the same amounts. Source: submission/execution-evidence/scenario-a.json; screenshots/02-inflated-invoice.png.`);
table(s,[['Record','Tonnes'],['Approved BOQ','80'],['Purchase order','80'],['Accepted delivery','80'],['Supplier invoice','95']],72,190,480,310,[340,140]);
text(s,'BDT 1,050,000',76,526,540,77,49,'#A14B42',true);
text(s,'Unsupported claim  ·  18.75% variance  ·  BLOCKED',78,605,1100,34,23,'#A14B42');
await image(s,'submission/screenshots/08-four-way-focus.png',590,235,616,310,'Actual blocked steel invoice interface and evidence comparisons');

s=slide('An authorized sandbox transaction',`5:30–6:40. A separate compliant cement invoice passes all checks. Operator prepares; a different Finance Manager approves BDT 70,000; a human explicitly confirms simulated execution. Cash changes from 1,000,000 to 930,000 once. Scenario H retries the exact execution and returns the same receipt with one deduction. Screenshot and HTTP evidence are separate runs; their unique mock references are expected to differ. Sources: scenario-b.json, scenario-h.json, and screenshots/04-mock-receipt.png.`);
text(s,'BDT 70,000',72,194,500,90,59,teal,true);
text(s,'One approved simulated settlement',76,288,465,62,25,muted);
text(s,'1,000,000 → 930,000',76,401,520,78,37,navy,true);
text(s,'Recorded cash balance in BDT',78,483,440,45,23,muted);
text(s,'Same request key → same receipt\nNo second cash deduction',78,560,490,77,25,teal,true);
await image(s,'submission/screenshots/09-receipt-focus.png',618,174,588,458,'Actual mock receipt generated after authorized sandbox settlement');

s=slide('Security and execution evidence',`6:40–7:50. Permission tiers, project access, independent approval, exact snapshots, current cash checks, receipt allocations and mandatory idempotency are implemented. Report only executed counts: ${checks.backend_tests} backend tests, ${checks.frontend_tests} frontend tests, ${checks.browser_workflows} browser workflows and 8 HTTP scenarios. Fresh Windows installation also passed. The audit chain is local tamper evidence; unrestricted DB administrators could rewrite it. Sources: docs/test-results.md, execution-evidence logs, clean-install.json, scenario manifests, and security-self-assessment.md.`);
text(s,'Independent approval\n\nExact payment snapshots\n\nAtomic, idempotent settlement\n\nVerified local audit chain',76,202,610,339,28,ink);
table(s,[['Executed validation','Passed'],['Backend tests',String(checks.backend_tests)],['Frontend tests',String(checks.frontend_tests)],['Browser workflows',String(checks.browser_workflows)],['HTTP scenarios A–H','8']],726,188,480,340,[340,140]);
text(s,'Local hash chaining cannot prevent a privileged database administrator from rewriting history.',76,580,1120,63,23,muted);

s=slide('Cost planning and commercial controls',`7:50–8:50. Show the fictional estimate example: 20 tonnes at 70,000 increases to 74,000 per tonne. Cost increases by 80,000, the scheduled forecast falls from 600,000 to 520,000, and recorded cash remains 2,000,000. Explain component mapping, separately reviewed certificates and corrections, and protected PO amendments. Actual browser and API evidence support these workflows. Paid provider acceptance, representative Bengali documents, professional rule approval, platform checks and team submission remain external gates. Sources: docs/completion-verification.md; screenshots/upgrade-price-comparison.png; execution-evidence/verification-summary.json.`,{dark:true});
text(s,'BDT 80,000',76,190,570,91,54,'#FFFFFF',true);
text(s,'Increase in the fictional 20-tonne estimate',79,289,555,70,28,'#D8E7E0');
text(s,'600,000 to 520,000',76,394,595,68,39,'#A8CDC0',true);
text(s,'Scheduled forecast in BDT. Recorded cash stays at 2,000,000.',79,471,540,106,26,'#D8E7E0');
await image(s,'submission/screenshots/upgrade-recommended-offer.png',690,210,518,340,'Actual recommended demonstration offer with specification checks');
text(s,'Independent reviews protect procurement, cost corrections and every cash installment.',79,592,1120,56,25,'#A8CDC0');

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
