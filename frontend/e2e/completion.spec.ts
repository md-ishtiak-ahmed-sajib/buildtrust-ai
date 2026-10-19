import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const credentials = JSON.parse(fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!, 'utf8'));
const today = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Dhaka'}).format(new Date());
const output = process.env.BUILDTRUST_E2E_OUTPUT!;

async function setup(request: APIRequestContext) {
  const headers: Record<string,Record<string,string>>={};
  for (const person of ['operator','manager','admin']) {
    const response=await request.post('/api/v1/auth/login',{data:{email:`${person}@buildtrust.demo`,password:credentials[`${person}@buildtrust.demo`]}});
    expect(response.status()).toBe(200);headers[person]={Authorization:`Bearer ${(await response.json()).access_token}`};
  }
  const send=async (url:string,data:unknown,person='operator') => {
    const response=await request.post('/api/v1'+url,{headers:headers[person],data});
    expect(response.ok(),await response.text()).toBeTruthy();return response.json();
  };
  const get=async(url:string)=>(await (await request.get('/api/v1'+url,{headers:headers.operator})).json());
  const approve=async(row:{id:number;version:number})=>{
    for (const [action,person] of [['submit','operator'],['check','manager'],['approve','admin']]) row=await send(`/controls/${row.id}/${action}`,{expected_version:row.version},person);
    return row;
  };
  const control=async(project:number,payload:Record<string,unknown>,name:string)=>approve(await send('/controls',{project_id:project,name,payload:{evidence:'Synthetic isolated browser acceptance evidence',...payload}}));
  return {headers,send,get,control};
}
async function login(page:Page,person:string,project:number,area='Commercial Management') {
  if (await page.getByRole('button',{name:'Sign out',exact:true}).count()) await page.getByRole('button',{name:'Sign out',exact:true}).click();
  else await page.goto('/');
  await page.getByLabel('Email address').fill(`${person}@buildtrust.demo`);
  await page.getByLabel('Password',{exact:true}).fill(credentials[`${person}@buildtrust.demo`]);
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await page.getByLabel('Select project').selectOption(String(project));
  await page.getByRole('link',{name:area,exact:true}).click();
}
async function form(page:Page,kind:string,name:string) {
  await page.getByRole('button',{name:'Prepare control',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Prepare independently reviewed control'});
  await dialog.getByLabel('Control type').selectOption(kind);
  await dialog.getByLabel('Control name',{exact:true}).fill(name);
  await dialog.getByLabel('Source evidence and assumptions').fill('Synthetic browser acceptance, independently reviewed source evidence');
  return dialog;
}
async function finish(page:Page,project:number,name:string,area='Commercial Management') {
  const card=()=>page.locator('.control-card').filter({has:page.getByRole('heading',{name,exact:true})});
  await card().getByRole('button',{name:'Submit for checking',exact:true}).click();
  await page.getByRole('button',{name:'Confirm',exact:true}).click();
  await expect(card()).toContainText('Submitted');
  await login(page,'manager',project,area);
  await card().getByRole('button',{name:'Check control',exact:true}).click();
  await expect(card()).toContainText('Checked');
  await login(page,'admin',project,area);
  await card().getByRole('button',{name:'Approve control',exact:true}).click();
  await page.getByRole('button',{name:'Confirm',exact:true}).click();
  await expect(card()).toContainText('Approved');
}

test('component contract forecast preserves labour and shows separate tax and retention',async({page,request})=>{
  const api=await setup(request), data=await api.send('/advanced/demo-project?new_run=true',{},'admin'),project=data.project_id;
  let estimate=await api.get(`/estimates/${data.estimate_id}`);const line=estimate.fields.lines[0];
  line.components.push({id:'labour-browser',category:'LABOUR',description:'Placement labour',unit:'tonne',consumption:'1',unit_price:'5000'});
  const updated=await request.patch(`/api/v1/estimates/${estimate.id}`,{headers:api.headers.operator,data:{expected_version:estimate.version,name:estimate.name,fields:estimate.fields}});
  expect(updated.ok()).toBeTruthy();estimate=await updated.json();
  const policy=await api.control(project,{kind:'ACCOUNTING_POLICY',effective_date:today,tax_treatment:'RECOVERABLE',tax_percent:'10'},'Composite browser policy');
  const code=await api.send('/accounting/cost-codes',{project_id:project,code:'BROWSER.COMP',name:'Composite material'});
  await api.control(project,{kind:'SUPPLIER_CHANGE',code:'COMP-BROWSER',name:'Composite browser supplier',beneficiary_token:'SANDBOX-COMP-BROWSER',verification_reference:'Synthetic independent callback',verification_attested:true},'Composite browser supplier');
  const supplier=(await api.get(`/suppliers?project_id=${project}`))[0];
  const contract=await api.control(project,{kind:'COMMERCIAL_CONTRACT',number:'BROWSER-COMP-CON',direction:'SUPPLIER',supplier_id:supplier.id,policy_id:policy.id,effective_date:today,payment_terms_days:30,tax_percent:'10',retention_percent:'5',lines:[{code:'STEEL',description:line.components[0].description,unit:'tonne',quantity:'20',rate:'74000',cost_code_id:code.id}]},'Browser component contract');
  await login(page,'operator',project);
  const dialog=await form(page,'CONTRACT_ESTIMATE_LINK','Browser reviewed component forecast');
  await dialog.getByLabel('Approved supplier contract',{exact:true}).selectOption(String(contract.id));
  await dialog.getByLabel('Contract item code',{exact:true}).fill('STEEL');
  await dialog.getByLabel('Estimate to map').selectOption(String(estimate.id));
  await dialog.getByLabel('BOQ item covered by this contract').selectOption(line.id);
  await dialog.getByLabel('Specific rate component').selectOption(line.components[0].id);
  await dialog.getByLabel('Contract quantity mapped to future scope').fill('20');
  await dialog.getByLabel('Explicit expected cash date').fill(today);
  await dialog.getByLabel('The contract covers the selected scope').check();
  await dialog.getByRole('button',{name:'Save control draft'}).click();await expect(dialog).toHaveCount(0);
  await finish(page,project,'Browser reviewed component forecast');
  await page.getByRole('link',{name:'Performance & Scenarios',exact:true}).click();
  await page.getByLabel('Uncommitted estimate overlay').selectOption(String(estimate.id));
  const table=page.getByRole('table',{name:'Estimated cash requirements and distinct cost allocations'});
  await expect(table).toContainText('1,554,000.00');await expect(table).toContainText('100,000.00');
  await expect(table).toContainText('74,000.00');await expect(table).toContainText('Unscheduled');
  await page.screenshot({path:path.join(output,'completion-composite-forecast.png'),fullPage:true});
});

test('PO authorization and unreceived amendment retain original purchase evidence',async({page,request})=>{
  const api=await setup(request);const project=(await api.get('/projects'))[0].id;
  const sources=await api.get(`/commercial/sources?project_id=${project}`);const boq=sources.boq.find((r:{label:string})=>r.label.includes('REBAR-500'));
  await login(page,'operator',project);
  let dialog=await form(page,'PROCUREMENT_AUTHORIZATION','Browser prospective procurement authority');
  await dialog.getByLabel('Approved procurement BOQ',{exact:true}).selectOption(String(boq.id));
  await dialog.getByLabel('Additional authorized quantity').fill('20');await dialog.getByLabel('Additional authorized value').fill('80000');
  await dialog.getByLabel('Scope and value authority evidence').fill('Approved prospective 20 tonnes and 80000 value uplift');
  await dialog.getByRole('button',{name:'Save control draft'}).click();await expect(dialog).toHaveCount(0);
  await finish(page,project,'Browser prospective procurement authority');
  const payload={document_type:'PO',supplier_code:'DEMO-STEEL',po_number:'BROWSER-UNRECEIVED-PO',currency:'BDT',items:[{item_code:'REBAR-500',description:'Reinforcement Steel 500 MPa',unit:'tonnes',quantity:'20',unit_rate:'70000',amount:'1400000'}]};
  const upload=await request.post('/api/v1/documents/upload',{headers:api.headers.operator,multipart:{project_id:String(project),file:{name:'browser-unreceived.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(payload))}}});
  expect(upload.status()).toBe(201);await api.send(`/documents/${(await upload.json()).id}/confirm`,{},'admin');
  const pol=(await api.get(`/commercial/sources?project_id=${project}`)).procurement_lines.find((r:{label:string})=>r.label.includes('BROWSER-UNRECEIVED-PO'));
  await login(page,'operator',project);dialog=await form(page,'PROCUREMENT_AMENDMENT','Browser controlled PO amendment');
  await dialog.getByLabel('Original approved purchase order line').selectOption(String(pol.id));
  await dialog.getByLabel('Approved procurement BOQ',{exact:true}).selectOption(String(boq.id));
  await dialog.getByLabel('Unreceived quantity to cancel').fill('20');await dialog.getByLabel('Successor order quantity').fill('20');
  await dialog.getByLabel('Successor rate',{exact:true}).fill('74000');await dialog.getByLabel('Successor purchase order number').fill('BROWSER-SUCCESSOR-PO');
  await dialog.getByLabel('Amendment reason and support').fill('Replacement price applies only to unreceived future quantities');
  await dialog.getByRole('button',{name:'Save control draft'}).click();await expect(dialog).toHaveCount(0);
  await finish(page,project,'Browser controlled PO amendment');
  const after=await api.get(`/commercial/sources?project_id=${project}`);
  expect(after.procurement_lines.some((r:{label:string})=>r.label.includes('BROWSER-SUCCESSOR-PO')&&r.label.includes('74000'))).toBeTruthy();
  expect(after.procurement_lines.some((r:{label:string})=>r.label.includes('BROWSER-UNRECEIVED-PO')&&r.label.includes('70000'))).toBeTruthy();
  await page.screenshot({path:path.join(output,'completion-procurement-amendment.png'),fullPage:true});
});

test('customer certificate correction changes revenue without refunding cash',async({page,request})=>{
  const api=await setup(request),project=(await api.get('/projects'))[0].id;
  const policy=await api.control(project,{kind:'ACCOUNTING_POLICY',effective_date:today},'Correction browser policy');
  const certificate=await api.control(project,{kind:'CUSTOMER_CERTIFICATE',policy_id:policy.id,customer:'Synthetic browser client',certificate_number:'BROWSER-COR-CLIENT',revenue:'200000',recognition_date:today},'Browser source customer certificate');
  const before=await api.get(`/accounting/summary?project_id=${project}`);
  await login(page,'operator',project);const dialog=await form(page,'CERTIFICATE_CORRECTION','Browser source-linked reversal');
  await dialog.getByLabel('Approved source certificate',{exact:true}).selectOption(String(certificate.id));
  await dialog.getByLabel('Base certification value to reverse').fill('10000');
  await dialog.getByLabel('Unique correction reference').fill('BROWSER-REV-10000');
  await dialog.getByLabel('Reason (accepted cost requires its own correction)').fill('Supported certificate reversal with no automatic cash refund');
  await dialog.getByRole('button',{name:'Save control draft'}).click();await expect(dialog).toHaveCount(0);
  await finish(page,project,'Browser source-linked reversal');
  const after=await api.get(`/accounting/summary?project_id=${project}`);
  expect(Number(before.recognized_revenue)-Number(after.recognized_revenue)).toBe(10000);
  expect(after.recorded_cash).toBe(before.recorded_cash);
  await page.screenshot({path:path.join(output,'completion-certificate-correction.png'),fullPage:true});
});

test('sensitivity and maturity compare saved historical estimates in the browser',async({page,request})=>{
  const api=await setup(request),data=await api.send('/advanced/demo-project?new_run=true',{},'admin'),project=data.project_id;
  let historical=await api.get(`/estimates/${data.estimate_id}`);
  for (const [action,person] of [['submit','operator'],['check','manager'],['approve','admin']]) historical=await api.send(`/estimates/${historical.id}/${action}`,{expected_version:historical.version},person);
  const revised=await api.send(`/estimates/${historical.id}/revise`,{expected_version:historical.version});
  await login(page,'operator',project,'Cost Control & Accounting');
  let dialog=await form(page,'SENSITIVITY','Browser material sensitivity');
  await dialog.getByLabel('Source estimate',{exact:true}).selectOption(String(revised.id));
  await dialog.getByLabel('Material price change percent').fill('10');
  await dialog.getByRole('button',{name:'Save control draft'}).click();await expect(dialog).toHaveCount(0);
  await finish(page,project,'Browser material sensitivity','Cost Control & Accounting');
  await login(page,'operator',project,'Cost Control & Accounting');
  dialog=await form(page,'ESTIMATE_MATURITY','Browser historical maturity review');
  await dialog.getByLabel('Source estimate',{exact:true}).selectOption(String(revised.id));
  await dialog.getByLabel('Approved historical estimates to compare').selectOption([String(historical.id)]);
  await dialog.getByLabel('Design definition and available detail').fill('Fictional detailed material quantities and drawings reviewed');
  await dialog.getByLabel('Input source references').fill('Fictional structural drawing revision A\nApproved historical estimate evidence');
  await dialog.getByLabel('Uncertainty basis').fill('Uncertainty based on unchanged fictional scope and evidenced reference prices');
  await dialog.getByRole('button',{name:'Save control draft'}).click();await expect(dialog).toHaveCount(0);
  await finish(page,project,'Browser historical maturity review','Cost Control & Accounting');
  const card=page.locator('.control-card').filter({has:page.getByRole('heading',{name:'Browser historical maturity review',exact:true})});
  await card.getByText('Evidence and calculations',{exact:true}).click();await expect(card).toContainText(/Historical Comparisons/i);
  await expect(card).toContainText('REQUIRES_EXTERNAL_ACCEPTANCE');
  await page.screenshot({path:path.join(output,'completion-sensitivity-maturity.png'),fullPage:true});
});
