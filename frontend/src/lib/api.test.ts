import { describe, it, expect } from "vitest";
import { sortChats, type ChatSummary } from "./api";
const c = (phone: string, status: ChatSummary["status"], last_ts: string): ChatSummary => ({ phone, status, last_ts });
describe("sortChats", () => {
  it("orders handed_off, collecting_info, bot_active then newest first", () => {
    const r = sortChats([c("a","bot_active","2026-11-10T12:00:00Z"), c("b","handed_off","2026-11-10T08:00:00Z"),
      c("c","collecting_info","2026-11-10T09:00:00Z"), c("d","handed_off","2026-11-10T10:00:00Z")]);
    expect(r.map(x=>x.phone)).toEqual(["d","b","c","a"]);
  });
});
