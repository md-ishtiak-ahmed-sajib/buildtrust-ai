import {test,expect} from './fixtures';
import {totp} from './mfa-client';
import fs from 'node:fs';
import path from 'node:path';
const credentials=JSON.parse(fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!,'utf8'));
test.use({manualMfa:true});

async function verifyAndContinue(page: import('@playwright/test').Page, refreshCode?:()=>Promise<void>) {
  for (let attempt=0;attempt<4;attempt++) {
    if(refreshCode)await refreshCode();
    const responsePromise=page.waitForResponse(r=>r.url().includes('/auth/mfa/')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Verify and continue'}).click();
    const response=await responsePromise;
    if(response.status()!==429)return;
    // Respect the same persistent admission limits as an ordinary browser user.
    await page.waitForTimeout(Math.min(60,Number(response.headers()['retry-after']||60))*1000+100);
  }
  throw new Error('MFA admission remained unavailable after the advertised retry period');
}

test('private Finance login requires visible authenticator enrollment and blocks cross-site requests',async({page,request})=>{
  const auth=await request.post('/api/v1/auth/login',{data:{email:'admin@buildtrust.demo',password:credentials['admin@buildtrust.demo']}});
  expect(auth.ok()).toBeTruthy();const headers={Authorization:'Bearer '+(await auth.json()).access_token};
  const projects=await (await request.get('/api/v1/projects',{headers})).json();
  const email=`mfa-browser-${Date.now()}@example.test`,password='Mfa-Private-Fixture-2026!';
  const created=await request.post('/api/v1/administration/users',{headers,data:{name:'Authenticator browser member',email,role:'FINANCE_MANAGER',password}});expect(created.status()).toBe(201);
  const identity=(await created.json()).id;
  expect((await request.post(`/api/v1/administration/members?project_id=${projects[0].id}`,{headers,data:{user_id:identity,member:true}})).ok()).toBeTruthy();
  await page.goto('/');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Set up your authenticator'})).toBeVisible();await expect(page.getByLabel('Select project')).toHaveCount(0);
  await page.getByRole('button',{name:'Show authenticator setup'}).click();
  const secret=await page.getByLabel('Manual setup key',{exact:true}).inputValue();
  await expect(page.getByAltText('Scan this private authenticator setup code')).toBeVisible();
  await page.getByLabel('Authenticator code',{exact:true}).fill('invalid-code');await verifyAndContinue(page);
  await expect(page.getByRole('alert')).toContainText('invalid');await expect(page.getByRole('heading',{name:'Set up your authenticator'})).toBeVisible();
  await verifyAndContinue(page,()=>page.getByLabel('Authenticator code',{exact:true}).fill(totp(secret)));
  await expect(page.getByRole('heading',{name:'Save your recovery codes'})).toBeVisible();
  const codes=(await page.getByLabel('One-time recovery codes').innerText()).split('\n');expect(codes).toHaveLength(10);
  await page.getByRole('button',{name:'I saved my codes — continue'}).click();await expect(page.getByLabel('Select project')).toBeVisible();
  const browserStorage=await page.evaluate(()=>({local:{...localStorage},session:{...sessionStorage}}));
  expect(JSON.stringify(browserStorage)).not.toContain(secret);for(const code of codes)expect(JSON.stringify(browserStorage)).not.toContain(code);
  await page.getByText('Account security',{exact:true}).click();await expect(page.getByRole('button',{name:'Disable MFA',exact:true})).toBeDisabled();
  await page.getByText('Account security',{exact:true}).click();await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Verify your authenticator'})).toBeVisible();
  await page.getByLabel('Authenticator or recovery code',{exact:true}).fill(codes[0]);await verifyAndContinue(page);await expect(page.getByLabel('Select project')).toBeVisible();
  expect((await request.post('/api/v1/auth/logout',{headers:{...headers,Origin:'https://evil.example'}})).status()).toBe(403);
  await page.screenshot({path:path.join(process.env.BUILDTRUST_E2E_OUTPUT!,'security-mfa-complete.png')});
});

test('stored malicious project text stays text under CSP',async({page,request})=>{
  const auth=await request.post('/api/v1/auth/login',{data:{email:'admin@buildtrust.demo',password:credentials['admin@buildtrust.demo']}});
  const headers={Authorization:'Bearer '+(await auth.json()).access_token};const projects=await(await request.get('/api/v1/projects',{headers})).json();
  // This browser assertion verifies escaped rendering of saved register content.
  const payload='<img src=x onerror="window.__storedXss=1">';
  const created=await request.post('/api/v1/administration/users',{headers,data:{name:payload,email:`xss-browser-${Date.now()}@example.test`,role:'OPERATOR',password:'Xss-Private-Fixture-2026!'}});expect(created.status()).toBe(201);
  const upload=await request.post('/api/v1/documents/upload',{headers,multipart:{project_id:String(projects[0].id),file:{name:'untrusted-<svg onload=window.__storedXss=1>.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({document_type:'BOQ',notes:payload,items:[{item_code:'XSS-ONLY',description:payload,quantity:'1',unit:'count',unit_rate:'1'}]}))}}});expect(upload.status()).toBe(201);
  const upgradeResponse=await request.post('/api/v1/advanced/demo-project?new_run=true',{headers});expect(upgradeResponse.ok()).toBeTruthy();const upgrade=await upgradeResponse.json();
  const quotation=await request.post('/api/v1/quotations',{headers,data:{material_id:upgrade.material_id,supplier:payload,title:'Synthetic stored-script fixture',price:'75',currency:'BDT',unit:'kg',quoted_quantity:'20000',minimum_quantity:'1000',specification:{grade:'B500B',diameter_mm:'16',standard:'BS 4449'},can_deliver:true,delivery_days:3,freight_basis:'INCLUDED',tax_basis:'INCLUDED',tax:'0',handling:'0',other_cost:'0',quotation_date:new Date().toISOString().slice(0,10),valid_until:new Date(Date.now()+7*86400000).toISOString().slice(0,10)}});expect(quotation.status()).toBe(201);
  await page.goto('/');await page.getByLabel('Email address').fill('admin@buildtrust.demo');await page.getByLabel('Password',{exact:true}).fill(credentials['admin@buildtrust.demo']);await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Verify your authenticator'})).toBeVisible();
  // Use the existing admin's private fixture recovery code, never an app bypass.
  const cache=JSON.parse(fs.readFileSync(process.env.BUILDTRUST_E2E_MFA_CACHE!,'utf8'));const code=cache['admin@buildtrust.demo'].codes.shift();fs.writeFileSync(process.env.BUILDTRUST_E2E_MFA_CACHE!,JSON.stringify(cache));
  await page.getByLabel('Authenticator or recovery code',{exact:true}).fill(code);await verifyAndContinue(page);
  await page.getByRole('link',{name:'Team & Access',exact:true}).click();await page.getByLabel('Search team accounts').fill((await created.json()).email);
  const savedRow=page.getByRole('row').filter({hasText:(await created.json()).email});
  await expect(savedRow.getByRole('cell').first()).toContainText(payload);
  await expect(savedRow.locator('img')).toHaveCount(0);expect(await page.evaluate(()=>Reflect.get(window,'__storedXss'))).toBeUndefined();
  await page.getByRole('link',{name:'Documents',exact:true}).click();await page.getByRole('button',{name:/untrusted-/}).first().click();
  await page.getByRole('button',{name:'Source preview',exact:true}).click();
  await expect(page.locator('.source-preview pre')).toContainText(JSON.stringify(payload).slice(1,-1));
  await expect(page.locator('.source-preview img')).toHaveCount(0);expect(await page.evaluate(()=>Reflect.get(window,'__storedXss'))).toBeUndefined();
  await page.getByLabel('Select project').selectOption(String(upgrade.project_id));await page.getByRole('link',{name:'Materials & Prices',exact:true}).click();
  await expect(page.locator('strong').filter({hasText:payload}).first()).toBeVisible();expect(await page.evaluate(()=>Reflect.get(window,'__storedXss'))).toBeUndefined();
  await page.getByRole('link',{name:'BOQ & Estimates',exact:true}).click();
  // Explicit synthetic response injection tests the explanation rendering boundary.
  // The real server response is still obtained; no financial record is replaced.
  await page.route('**/api/v1/advanced/ask',async route=>{const response=await route.fetch();expect(response.ok()).toBeTruthy();await route.fulfill({response,json:{...await response.json(),answer:payload}});});
  await page.getByRole('button',{name:'Analyze estimate',exact:true}).click();
  await expect(page.locator('.copilot-answer')).toContainText(payload);await expect(page.locator('.copilot-answer img')).toHaveCount(0);expect(await page.evaluate(()=>Reflect.get(window,'__storedXss'))).toBeUndefined();
  expect(projects.length).toBeGreaterThan(0);
});
