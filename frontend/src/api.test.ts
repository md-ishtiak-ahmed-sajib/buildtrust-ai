import { describe, it, expect, vi, afterEach } from "vitest";
import { formatMoney, titleCase, post, api, setToken } from "./api";
describe("financial display", () => {
  it("preserves BDT decimal presentation", () =>
    expect(formatMoney("1050000.00")).toBe("1,050,000.00"));
  it("does not render invalid data as a financial amount", () =>
    expect(formatMoney("invalid")).toBe("—"));
  it("formats human-readable state names", () =>
    expect(titleCase("PENDING_APPROVAL")).toBe("Pending Approval"));
});
describe("API authority and retry contract", () => {
  afterEach(() => {
    setToken("");
    vi.unstubAllGlobals();
  });
  it("forwards the same idempotency key without accepting an execution amount", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "SETTLED" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetcher);
    setToken("session-token");
    await post("/payments/1/execute", undefined, {
      "Idempotency-Key": "stable-key",
    });
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/api/v1/payments/1/execute");
    expect(options.body).toBeUndefined();
    expect(options.headers.get("Idempotency-Key")).toBe("stable-key");
    expect(options.headers.get("Authorization")).toBe("Bearer session-token");
  });
  it("clears memory authority when signing out", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    setToken("old-token");
    setToken("");
    await api("/projects");
    expect(fetcher.mock.calls[0][1].headers.has("Authorization")).toBe(false);
  });
  it("surfaces a structured policy denial", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "PAYMENT_BLOCKED",
              message: "Reserve would be breached.",
            },
          }),
          { status: 409 },
        ),
      ),
    );
    await expect(post("/payments/1/execute")).rejects.toThrow(
      "Reserve would be breached.",
    );
  });
  it('marks every mutating request without introducing cookie authority',async()=>{
    const fetcher=vi.fn().mockImplementation(()=>Promise.resolve(new Response('{}',{status:200})));vi.stubGlobal('fetch',fetcher);
    for(const method of ['POST','PUT','PATCH','DELETE'])await api('/example',{method});
    for(const [,options] of fetcher.mock.calls){expect(options.headers.get('X-BuildTrust-Request')).toBe('1');expect(options.credentials).toBeUndefined();}
  });
  it('keeps a failed MFA step distinct from an expired full session',async()=>{
    const dispatch=vi.fn();vi.stubGlobal('window',{dispatchEvent:dispatch});
    vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({error:{code:'MFA_CODE_INVALID',message:'Use a fresh code.'}}),{status:401})).mockResolvedValueOnce(new Response(JSON.stringify({error:{code:'UNAUTHENTICATED',message:'Sign in again.'}}),{status:401})));
    await expect(post('/auth/mfa/verify',{challenge_token:'restricted-step',code:'123456'})).rejects.toThrow('Use a fresh code.');expect(dispatch).not.toHaveBeenCalled();
    await expect(api('/projects')).rejects.toThrow('Sign in again.');expect(dispatch).toHaveBeenCalledOnce();
  });
});
