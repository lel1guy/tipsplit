// TipSplit end-to-end smoke — the regression net for the whole weekly ritual.
// Boots the real app against a throwaway DB, drives the UI, asserts, tears down.
// Exit 0 = everything works.
//
// Run:  node e2e/smoke.mjs
// Needs: node + the ms-playwright chromium cache (reuses BarSpec's playwright-core).
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire("/home/vitor/dev/barspec/");
const { chromium } = require("playwright-core");

const REPO = new URL("..", import.meta.url).pathname;
const PORT = 8892;
const BASE = `http://127.0.0.1:${PORT}`;
const PIN = "2468";
const SHOT = "/tmp/tipsplit-mobile.png";

function findChromium() {
  const cache = join(process.env.HOME, ".cache", "ms-playwright");
  for (const dir of readdirSync(cache)) {
    if (!dir.startsWith("chromium-")) continue;
    for (const name of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      const p = join(cache, dir, name);
      if (existsSync(p)) return p;
    }
  }
  throw new Error("chromium not found in ~/.cache/ms-playwright");
}

let server, browser, passed = 0, failed = 0;
const results = [];
const ok = (name, cond, extra = "") => {
  if (cond) { passed++; results.push(`  ✅ ${name}`); }
  else { failed++; results.push(`  ❌ ${name} ${extra}`); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const dbFile = join(mkdtempSync(join(tmpdir(), "ts-e2e-")), "e2e.db");

async function boot() {
  server = spawn(".venv/bin/python", ["-m", "uvicorn", "main:app",
    "--host", "127.0.0.1", "--port", String(PORT)], {
    cwd: REPO, env: { ...process.env, TIPSPLIT_DB: dbFile }, stdio: "ignore",
  });
  for (let i = 0; i < 60; i++) {
    try { await fetch(BASE + "/api/auth/status"); return; } catch { await sleep(500); }
  }
  throw new Error("server did not come up");
}

async function run() {
  browser = await chromium.launch({ executablePath: findChromium() });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  // dialogs: prompts get queued answers (staff PIN, then the unlock reason)
  const promptQueue = ["4321", "horas da Ana estavam mal"];
  page.on("dialog", (d) =>
    d.accept(d.type() === "prompt" ? promptQueue.shift() : undefined));

  // ---- 1. first run: the gate asks for a new PIN ----
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector("#gate:not(.hidden)");
  ok("gate asks to define a PIN", (await page.textContent("#gateTitle")).includes("Define"));
  await page.fill("#gatePin", PIN);
  await page.click("#gateBtn");
  await page.waitForSelector("#dash .stat", { timeout: 15000 });   // gate gone = app up

  // ---- 2. dashboard + sidebar ----
  await page.waitForSelector("#dash .stat");
  const stats = await page.$$eval("#dash .stat .cap", (els) => els.map((e) => e.textContent));
  ok("dashboard shows the week's numbers", stats.length >= 4, JSON.stringify(stats));
  ok("dashboard names the pool + advances",
     stats.join("|").includes("Pool") && stats.join("|").includes("Adiantamentos"), stats.join("|"));
  ok("sidebar shows the active headcount",
     /^\d+$/.test((await page.textContent("#badgeEquipa")).trim()),
     await page.textContent("#badgeEquipa"));
  ok("seeded week listed", (await page.$$("#weekList .week-item")).length >= 1);
  ok("brand + version in the sidebar", (await page.textContent(".brand")).includes("TipSplit"));

  // ---- 3. new week opens with the grid ----
  await page.click("#newWeekBtn");
  await page.waitForSelector("#poolInput");
  const rows = (await page.$$("#gridBody tr")).length;
  ok("new week grid lists the roster", rows >= 10, `rows=${rows}`);

  // ---- 4. hours + pool -> server-side preview ----
  await page.fill("#poolInput", "100");
  for (const [row, hours] of [[0, 8], [1, 4]]) {
    for (const day of ["mon", "tue", "wed", "thu", "fri"]) {
      await page.fill(`#gridBody tr:nth-child(${row + 1}) input[data-k="${day}"]`, String(hours));
    }
  }
  await sleep(600);                                    // debounced /preview round-trip
  ok("total hours computed", (await page.textContent("#statHours")).trim() === "60");
  ok("pool check says fully split", (await page.textContent("#checkMsg")).includes("todo dividido"));
  const statement = await page.textContent("#statement");
  ok("fairness statement rendered", statement.includes("÷") && statement.includes("Regra"));
  const sum = await page.textContent("#statSum");
  ok("net total equals the pool", sum.includes("100"), sum);
  const nets = await page.$$eval("#gridBody [data-net]", (els) => els.map((e) => e.textContent));
  ok("40h vs 20h split 2:1", nets[0].includes("66") && nets[1].includes("33"), nets.slice(0, 2).join(" "));

  // ---- 5. save + reload keeps it ----
  await page.click("#saveBtn");
  await sleep(700);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector("#weekList .week-item");
  await page.click("#weekList .week-item");
  await page.waitForSelector("#poolInput");
  ok("pool persisted", (await page.inputValue("#poolInput")) === "100");
  ok("hours persisted", (await page.textContent("#statHours")).trim() === "60");

  // ---- 6. vale: recorded in Equipa, visible on the week ----
  const netText = async () => {
    await page.waitForFunction(() =>
      !document.querySelector("#gridBody tr:nth-child(1) [data-net]").textContent.includes("—"),
      null, { timeout: 10000 });
    return page.textContent("#gridBody tr:nth-child(1) [data-net]");
  };
  const parse = (t) => parseFloat(String(t).replace(/[^\d.,]/g, "").replace(",", "."));
  const netBefore = parse(await netText());

  await page.click('[data-view="equipa"]');               // the forms moved into this view
  await page.waitForSelector("#teamPanel table");
  ok("equipa view lists the roster with access state",
     (await page.textContent("#teamPanel")).includes("sem PIN"));
  ok("vale form asks which week the advance belongs to",
     (await page.$$("#valeWeek option")).length >= 1);
  await page.fill("#valeAmount", "10");
  await page.fill("#valeNote", "adiantamento qa");
  await page.click("#addValeBtn");
  await page.waitForFunction(
    () => document.querySelector("#valeList").textContent.includes("10,00"),
    null, { timeout: 15000 });
  ok("vale listed under the person",
     (await page.textContent("#valeList")).includes("10,00"));
  ok("ledger is grouped per week", (await page.textContent("#valeList")).includes("Semana de"),
     (await page.textContent("#valeList")).slice(0, 60));
  await page.click("#teamPanel [data-pin]");               // prompt answers "4321"
  await page.waitForFunction(() =>
    document.querySelector("#teamPanel").textContent.includes("PIN ✓"),
    null, { timeout: 15000 });
  ok("staff PIN issued from Equipa",
     (await page.textContent("#teamPanel")).includes("PIN ✓"));

  await page.click('[data-view="semana"]');
  await page.click("#weekList .week-item");
  await page.waitForSelector("#poolInput");
  const netAfter = parse(await netText());
  ok("vale deducted from the net", Math.abs((netBefore - netAfter) - 10) < 0.02,
     `${netBefore} -> ${netAfter}`);
  ok("vale visible in the week grid",
     (await page.textContent("#gridBody tr:nth-child(1) [data-vales]")).includes("10"));
  ok("the week shows its own advances",
     (await page.textContent("#weekVales")).includes("10,00"),
     (await page.textContent("#weekVales")).slice(0, 60));

  // ---- 7. lock the week ----
  await page.click("#lockBtn");
  await sleep(800);
  await page.waitForSelector(".badge");
  ok("locked badge shown", (await page.textContent(".badge")).includes("fechada"));
  ok("save button gone when locked", (await page.$$("#saveBtn")).length === 0);
  ok("unlock button offered", (await page.$$("#unlockBtn")).length === 1);
  const payslipHref = await page.getAttribute('a[href*="/print/payslips/"]', "href");
  ok("payslip link present", !!payslipHref, String(payslipHref));
  const weekId = payslipHref.match(/payslips\/(\d+)/)[1];

  // ---- 8. payday paperwork ----
  await page.goto(BASE + payslipHref, { waitUntil: "networkidle" });
  const slip = await page.textContent("body");
  ok("payslip has a signature line", slip.includes("Assinatura"));
  ok("payslip shows the amount due", slip.includes("A receber"));
  ok("payslip carries the fairness rule", slip.includes("Regra"));
  await page.goto(`${BASE}/print/cashsheet/${weekId}`, { waitUntil: "networkidle" });
  const sheet = await page.textContent("body");
  ok("cash sheet totals the cash", sheet.includes("Dinheiro a tirar da caixa") && sheet.includes("☐"));

  // ---- 9. exports ----
  const xlsx = await page.request.get(`${BASE}/api/export/week/${weekId}?fmt=xlsx`);
  const xbuf = await xlsx.body();
  ok("week xlsx downloads as a real workbook",
     xlsx.status() === 200 && xbuf[0] === 0x50 && xbuf[1] === 0x4b, `status=${xlsx.status()}`);
  const csv = await page.request.get(`${BASE}/api/export/week/${weekId}?fmt=csv`);
  ok("week csv has the PT header", (await csv.text()).startsWith("Pessoa;Função"));
  const annual = await page.request.get(`${BASE}/api/export/annual/${new Date().getFullYear()}?fmt=xlsx`);
  ok("annual export works", annual.status() === 200 && (await annual.body())[0] === 0x50);

  // ---- 10. unlock with a reason, and the reason is recorded ----
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector("#weekList .week-item");
  await page.click("#weekList .week-item");
  await page.waitForSelector("#unlockBtn");
  await page.click("#unlockBtn");
  await sleep(900);
  ok("week reopened", (await page.$$(".badge")).length === 0);
  ok("save button back", (await page.$$("#saveBtn")).length === 1);
  ok("unlock reason recorded in the audit list",
     (await page.textContent("#auditList")).includes("week.unlock"),
     (await page.textContent("#auditList")).slice(0, 60));

  // ---- 11. phone layout (same session, 390x844) ----
  const phone = await ctx.newPage();
  await phone.setViewportSize({ width: 390, height: 844 });
  await phone.goto(BASE, { waitUntil: "networkidle" });
  await phone.waitForSelector("#dash .stat");
  const m = await phone.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    btn: Math.round(document.querySelector("#newWeekBtn").getBoundingClientRect().height),
    stacked: getComputedStyle(document.querySelector(".app")).gridTemplateColumns.split(" ").length,
  }));
  ok("no horizontal scroll at 390px", m.overflow <= 1, `overflow=${m.overflow}`);
  ok("tap targets >= 44px on a phone", m.btn >= 44, `btn=${m.btn}`);
  ok("sidebar stacks above content on a phone", m.stacked === 1, `cols=${m.stacked}`);
  await phone.screenshot({ path: SHOT, fullPage: true });

  // ---- 12. the team's own page: a staff login sees their numbers and nothing else ----
  await page.click('[data-view="semana"]');
  await page.click("#weekList .week-item");
  await page.waitForSelector("#poolInput");
  await page.click("#lockBtn");                            // payslip needs a settled week
  await page.waitForSelector(".badge", { timeout: 10000 });

  await page.click("#logoutBtn");
  await page.waitForSelector("#gate:not(.hidden)", { timeout: 5000 });
  ok("logout returns to the PIN gate",
     (await page.textContent("#gateTitle")).includes("PIN da casa"));
  const probe = await page.request.get(BASE + "/api/dashboard");
  ok("API refuses anonymous callers", probe.status() === 401, `status=${probe.status()}`);

  await page.fill("#gatePin", "4321");
  await page.click("#gateBtn");
  await page.waitForFunction(() => document.body.classList.contains("is-staff"),
                             null, { timeout: 15000 });
  const staffBody = await page.textContent("#staffBody");
  ok("staff lands on their own page",
     (await page.textContent("#staffPage h1")).includes("As minhas gorjetas"),
     (await page.textContent("#staffPage h1")).slice(0, 40));
  ok("staff sees their own line", staffBody.includes("Rateio"));
  ok("staff sees the week's table (variant B)", staffBody.includes("(eu)"));
  ok("staff table reconciles: rateio, advances, net",
     staffBody.includes("Adiant.") && staffBody.includes("para pagar agora"),
     staffBody.includes("Adiant.") ? "no reconciliation line" : "no advances column");
  ok("staff gets a provable statement", staffBody.includes("Regra"));
  ok("staff can open their own payslip", (await page.$$('a[href^="/print/me/"]')).length === 1,
     staffBody.includes("aberta") ? "week shown as OPEN" : staffBody.slice(0, 120));
  const weekId2 = (await page.getAttribute('a[href^="/print/me/"]', "href")).match(/me\/(\d+)/)[1];
  const myPay = await page.request.get(`${BASE}/print/me/${weekId2}`);
  ok("own payslip renders for the staff session", myPay.status() === 200, `status=${myPay.status()}`);

  const leaked = [];
  for (const path of ["/api/settings", "/api/audit", "/api/dashboard", "/api/team",
                      "/api/weeks/1", "/api/staff", `/print/payslips/${weekId2}`,
                      `/api/export/annual/2026?fmt=csv`]) {
    const r = await page.request.get(BASE + path);
    if (r.status() !== 403) leaked.push(`${path}=${r.status()}`);
  }
  ok("staff is 403 everywhere except /api/me and their own payslip",
     leaked.length === 0, leaked.join(" "));
  ok("staff can read /api/me", (await page.request.get(BASE + "/api/me")).status() === 200);

  const phone2 = await ctx.newPage();
  await phone2.setViewportSize({ width: 390, height: 844 });
  await phone2.goto(BASE, { waitUntil: "networkidle" });
  await phone2.waitForSelector("#staffPage");
  const m2 = await phone2.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    btn: Math.round(document.querySelector("#staffLogout").getBoundingClientRect().height),
  }));
  ok("staff page: no horizontal scroll at 390px", m2.overflow <= 1, `overflow=${m2.overflow}`);
  ok("staff page: tappable logout", m2.btn >= 44, `btn=${m2.btn}`);
  await phone2.screenshot({ path: "/tmp/tipsplit-staff-phone.png", fullPage: true });
}

try {
  await boot();
  await run();
} catch (e) {
  failed++;
  results.push(`  ❌ run crashed: ${e.message}`);
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) server.kill();
  await sleep(300);
  rmSync(join(dbFile, ".."), { recursive: true, force: true });
}

console.log(results.join("\n"));
console.log(`\n${passed} passed, ${failed} failed`);
console.log(`screenshot: ${SHOT}`);
process.exit(failed ? 1 : 0);
