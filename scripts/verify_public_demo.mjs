// Read-only login/browser checks against the explicitly separate public demo.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'frontend/package.json'));
const {chromium,expect}=require('@playwright/test');
const base='http://127.0.0.1:8003';
const accounts=JSON.parse(await fs.readFile(path.join(root,'demo/public-accounts.json'),'utf8')).accounts;
const out=path.join(root,'data/public-demo-browser');await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
const checks=[];
try {
  for(const account of accounts){
    await page.goto(base);
    await expect(page.getByLabel('Email address')).toBeVisible();
    if(account.role==='OPERATOR')await page.screenshot({path:path.join(out,'public-demo-login.png'),fullPage:true});
    await page.getByLabel('Email address').fill(account.email);
    await page.getByLabel('Password',{exact:true}).fill(account.password);
    await page.getByRole('button',{name:'Sign in to workspace'}).click();
    await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
    await expect(page.getByRole('link',{name:'Overview',exact:true})).toBeVisible();
    await expect(page.getByRole('link',{name:'Review Inbox',exact:true})).toBeVisible();
    if(account.role==='OPERATOR'){
      await expect(page.locator('.recharts-area-curve')).toBeVisible();
      await page.waitForTimeout(750); // Let the real chart finish its display animation.
      await page.screenshot({path:path.join(out,'public-demo-overview.png'),fullPage:true});
    }
    checks.push({role:account.role,login_passed:true});
    await page.getByRole('button',{name:'Sign out',exact:true}).click();
  }
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({passed:true,url:base,checks,scope:'Four real browser logins and read-only navigation; no demo reset or financial writes'},null,2));
  console.log('Four public-demo browser logins: PASS');
} finally {await browser.close();}
