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

async function seedStore(page, databaseName, storeName, entries) {
  await page.evaluate(
    async ({ databaseName: name, storeName: objectStore, entries: values }) => {
      const open = indexedDB.open(name, 1);
      open.onupgradeneeded = () => open.result.createObjectStore(objectStore);
      const database = await new Promise((resolve, reject) => {
        open.onsuccess = () => resolve(open.result);
        open.onerror = () => reject(open.error);
      });
      const transaction = database.transaction(objectStore, "readwrite");
      const store = transaction.objectStore(objectStore);
      values.forEach(([key, value]) => store.put(value, key));
      await new Promise((resolve, reject) => {
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
      database.close();
    },
    { databaseName, storeName, entries },
  );
}

async function seedCampo(page) {
  const savedAt = new Date().toISOString();
  await seedStore(page, "gb-offline-v1", "data", [
    [
      "last-user:gbconstruction",
      {
        user: {
          id: "user-campo-offline",
          email: "campo-offline@gbconstruction.it",
          name: "Tecnico Campo Offline",
          role: "admin",
        },
        saved_at: savedAt,
      },
    ],
  ]);
  await seedStore(page, "gb-campo", "offline-data", [
    [
      "cache:gbconstruction:bootstrap",
      {
        saved_at: savedAt,
        data: [
          {
            id: "10000000-0000-4000-8000-000000000001",
            cliente: "Cantiere Offline",
            indirizzo: "Via Tablet 1",
            stato: "attivo",
            voci: [
              {
                id: "20000000-0000-4000-8000-000000000001",
                descrizione: "Muratura offline",
                um: "mq",
                qta_contrattuale: 20,
              },
            ],
          },
        ],
      },
    ],
    [
      "cache:gbconstruction:misure:10000000-0000-4000-8000-000000000001",
      { saved_at: savedAt, data: [] },
    ],
  ]);
  await seedStore(page, "gb-campo-rilievi", "offline-data", [
    ["cache:gbconstruction:lista", { saved_at: savedAt, data: [] }],
    [
      "cache:gbconstruction:riferimenti:leads",
      { saved_at: savedAt, data: [] },
    ],
    [
      "cache:gbconstruction:riferimenti:sopralluoghi",
      { saved_at: savedAt, data: [] },
    ],
  ]);
}

async function queuedRilievoOperations(page) {
  return page.evaluate(async () => {
    const open = indexedDB.open("gb-campo-rilievi", 1);
    const database = await new Promise((resolve, reject) => {
      open.onsuccess = () => resolve(open.result);
      open.onerror = () => reject(open.error);
    });
    const transaction = database.transaction("offline-data", "readonly");
    const request = transaction.objectStore("offline-data").getAllKeys();
    const keys = await new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    database.close();
    return keys.filter((key) => String(key).startsWith("queue:"));
  });
}

async function run() {
  if (!fs.existsSync(path.join(buildDir, "index.html"))) {
    throw new Error("Build frontend assente: esegui prima npm run build");
  }
  const server = await startServer();
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-gpu"],
  });
  const context = await browser.newContext({
    viewport: { width: 820, height: 1180 },
    timezoneId: "Europe/Rome",
  });
  const page = await context.newPage();
  try {
    process.stdout.write("[campo-offline] installazione shell PWA\n");
    await page.goto(origin, { waitUntil: "domcontentloaded" });
    await page.evaluate(async () => {
      await navigator.serviceWorker.register("/service-worker.js");
      await navigator.serviceWorker.ready;
    });
    if (!(await page.evaluate(() => Boolean(navigator.serviceWorker.controller)))) {
      await page.reload({ waitUntil: "domcontentloaded" });
    }
    await seedCampo(page);
    await context.setOffline(true);
    await page.goto(`${origin}/campo`, {
      waitUntil: "domcontentloaded",
      timeout: 15_000,
    });

    await page.getByRole("button", { name: /Nuovo rilievo/i }).click();
    await page.getByRole("textbox", { name: "Cliente", exact: true }).fill(
      "Cliente Tablet Offline",
    );
    await page.getByRole("button", { name: /Crea sul dispositivo/i }).click();
    await page.getByText("Cliente Tablet Offline", { exact: true }).waitFor();
    await page.getByRole("button", { name: /Aggiungi ambiente/i }).click();
    await page.getByRole("button", { name: /Salva adesso/i }).click();
    await page.getByText(/Ambiente salvato sul dispositivo/i).waitFor();
    await page.getByRole("button", { name: /Completa rilievo/i }).click();
    await page.getByRole("button", { name: /Riapri rilievo/i }).waitFor();

    const operations = await queuedRilievoOperations(page);
    const kinds = operations.map((key) => String(key).split(":")[2]).sort();
    for (const expected of [
      "ambiente",
      "rilievo",
      "rilievo-crea",
      "rilievo-stato",
    ]) {
      if (!kinds.includes(expected)) {
        throw new Error(
          `Operazione ${expected} assente dalla coda: ${kinds.join(", ")}`,
        );
      }
    }
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    if (overflow > 1) throw new Error(`Overflow orizzontale di ${overflow}px`);
    process.stdout.write(
      `CAMPO OFFLINE OK: creazione, ambiente e completamento accodati (${kinds.join(", ")})\n`,
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
