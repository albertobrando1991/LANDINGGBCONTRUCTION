const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium } = require("@playwright/test");

const buildDir = path.resolve(__dirname, "..", "build");
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webmanifest": "application/manifest+json",
};

function startServer() {
  const server = http.createServer((request, response) => {
    const pathname = decodeURIComponent(
      new URL(request.url, "http://local").pathname,
    );
    const requested = path.resolve(buildDir, `.${pathname}`);
    const safePath = requested.startsWith(buildDir) ? requested : buildDir;
    const filePath =
      fs.existsSync(safePath) && fs.statSync(safePath).isFile()
        ? safePath
        : path.join(buildDir, "index.html");
    response.setHeader(
      "Content-Type",
      contentTypes[path.extname(filePath)] || "application/octet-stream",
    );
    fs.createReadStream(filePath).pipe(response);
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function seedOfflineData(page, date) {
  await page.evaluate(
    async ({ date: currentDate }) => {
      const open = indexedDB.open("gb-offline-v1", 1);
      open.onupgradeneeded = () => open.result.createObjectStore("data");
      const database = await new Promise((resolve, reject) => {
        open.onsuccess = () => resolve(open.result);
        open.onerror = () => reject(open.error);
      });
      const transaction = database.transaction("data", "readwrite");
      const store = transaction.objectStore("data");
      const savedAt = new Date().toISOString();
      const user = {
        id: "user-1",
        email: "offline@gbconstruction.it",
        name: "Tecnico Offline",
        role: "admin",
      };
      const cantiere = {
        id: "64b64c8f2f9b2d7a1c000001",
        cliente: "Cliente Offline",
        indirizzo: "Via del Cantiere 1",
        avanzamento: 35,
        stato: "attivo",
        fasi: [{ nome: "Impianti", stato: "in_corso" }],
      };
      const person = {
        id: "20000000-0000-4000-8000-000000000001",
        nome: "Mario Offline",
        tipo: "interno",
        attivo: true,
      };
      store.put({ user, saved_at: savedAt }, "last-user:gbconstruction");
      store.put(
        { data: [cantiere], saved_at: savedAt },
        "cache:gbconstruction:user-1:cantieri:attivo",
      );
      store.put(
        { data: cantiere, saved_at: savedAt },
        `cache:gbconstruction:user-1:cantiere:${cantiere.id}`,
      );
      store.put(
        { data: [person], saved_at: savedAt },
        "cache:gbconstruction:user-1:personale",
      );
      store.put(
        { data: [], saved_at: savedAt },
        "cache:gbconstruction:user-1:personale-assegnazioni",
      );
      store.put(
        {
          data: {
            data: currentDate,
            righe: [],
            totale_unita: 0,
            totale_interni: 0,
            totale_subappaltatori: 0,
          },
          saved_at: savedAt,
        },
        `cache:gbconstruction:user-1:presenze:${cantiere.id}:${currentDate}`,
      );
      await new Promise((resolve, reject) => {
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
      database.close();
    },
    { date },
  );
}

async function run() {
  if (!fs.existsSync(path.join(buildDir, "index.html"))) {
    throw new Error("Build frontend assente: esegui prima npm run build");
  }
  const server = await startServer();
  const address = server.address();
  const origin = `http://127.0.0.1:${address.port}`;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    timezoneId: "Europe/Rome",
  });
  const page = await context.newPage();
  try {
    process.stdout.write("[offline-mobile] apertura build\n");
    await page.goto(origin, { waitUntil: "domcontentloaded" });
    process.stdout.write("[offline-mobile] installazione service worker\n");
    await page.evaluate(async () => {
      await navigator.serviceWorker.register("/service-worker.js");
      await navigator.serviceWorker.ready;
    });
    const controlled = await page.evaluate(() =>
      Boolean(navigator.serviceWorker.controller),
    );
    if (!controlled) {
      await page.reload({ waitUntil: "domcontentloaded" });
    }
    const date = await page.evaluate(() => {
      const now = new Date();
      return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 10);
    });
    await seedOfflineData(page, date);
    process.stdout.write("[offline-mobile] passaggio offline\n");
    await context.setOffline(true);
    await page.goto(`${origin}/dashboard/cantieri`, {
      waitUntil: "domcontentloaded",
      timeout: 15_000,
    });

    await page
      .getByText("Cliente Offline")
      .waitFor({ timeout: 15_000 })
      .catch(async (error) => {
        const text = await page
          .locator("body")
          .innerText()
          .catch(() => "");
        throw new Error(
          `${error.message}\nPagina offline: ${text.slice(0, 500)}`,
        );
      });
    process.stdout.write("[offline-mobile] dashboard caricata da cache\n");
    await page
      .getByRole("link", { name: /Apri il cantiere Cliente Offline/i })
      .click();
    await page.getByRole("link", { name: /Presenze/i }).click();
    await page
      .getByLabel("Persona o squadra presente")
      .selectOption("20000000-0000-4000-8000-000000000001");
    await page.getByRole("button", { name: /Registra/i }).click();
    await page.getByText("Presenza salvata offline").waitFor({
      timeout: 15_000,
    });
    await page.getByText(/Modalita offline/i).waitFor({ timeout: 15_000 });

    for (const viewport of [
      { width: 390, height: 844 },
      { width: 820, height: 1180 },
    ]) {
      await page.setViewportSize(viewport);
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      if (overflow > 1) {
        throw new Error(
          `Overflow orizzontale di ${overflow}px a ${viewport.width}px`,
        );
      }
    }

    const queued = await page.evaluate(async () => {
      const open = indexedDB.open("gb-offline-v1");
      const database = await new Promise((resolve, reject) => {
        open.onsuccess = () => resolve(open.result);
        open.onerror = () => reject(open.error);
      });
      const transaction = database.transaction("data", "readonly");
      const request = transaction.objectStore("data").getAllKeys();
      const keys = await new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      database.close();
      return keys.filter((key) => String(key).startsWith("operation:")).length;
    });
    if (queued !== 1)
      throw new Error(`Attesa 1 operazione offline, trovate ${queued}`);
    process.stdout.write(
      "OFFLINE MOBILE OK: 390x844, 820x1180, coda IndexedDB persistita\n",
    );
  } finally {
    await context.setOffline(false).catch(() => undefined);
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

run().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
