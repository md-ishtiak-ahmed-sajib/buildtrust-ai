import { test as base, expect } from "@playwright/test";
export { expect };
export type { Page, APIRequestContext } from "@playwright/test";
const pause = (seconds: number) => new Promise(resolve=>setTimeout(resolve,Math.min(60,Math.max(1,seconds))*1000+100));

// The suite signs in many people quickly. Respect the real server allowance;
// never disable throttling or reset buckets to make browser checks pass.
export const test=base.extend<{admissionAware:boolean}>({
  request:async({request},use)=>{
    const proxy=new Proxy(request,{get(target,key){
      if(key==="post")return async(url:string,options?:Parameters<typeof target.post>[1])=>{
        let result=await target.post(url,options);
        if(url.endsWith("/auth/login")&&result.status()===429){await pause(Number(result.headers()["retry-after"]||1));result=await target.post(url,options);}
        return result;
      };
      const value=Reflect.get(target,key);return typeof value==="function"?value.bind(target):value;
    }});
    await use(proxy);
  },
  admissionAware:[async({page},use,testInfo)=>{
    testInfo.setTimeout(Math.max(testInfo.timeout,120000));
    await page.route("**/api/v1/auth/login",async route=>{
      let response=await route.fetch();
      if(response.status()===429){await pause(Number(response.headers()["retry-after"]||1));response=await route.fetch();}
      await route.fulfill({response});
    });
    await use(true);
  },{auto:true}]
});
