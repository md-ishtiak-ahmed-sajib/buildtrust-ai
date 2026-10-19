import { describe, it, expect } from "vitest";
import { multiplyExact } from "./shared";
describe("exact quantity search parameters", () => {
  it("preserves decimals without binary rounding", () => {
    expect(multiplyExact("0.1", "0.2")).toBe("0.02");
    expect(multiplyExact("20", "1")).toBe("20");
    expect(multiplyExact("100.005", "2")).toBe("200.01");
  });
  it("keeps integer trailing zeros and rejects unsupported notation", () => {
    expect(multiplyExact("200", "10")).toBe("2000");
    expect(multiplyExact("1e3", "2")).toBe("0");
  });
});
