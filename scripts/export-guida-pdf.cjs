const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const chromeCandidates = [
  process.env.CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  path.join(process.env.LOCALAPPDATA || "", "Google\\Chrome\\Application\\chrome.exe"),
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);

const chrome = chromeCandidates.find((candidate) => fs.existsSync(candidate));
if (!chrome) {
  console.error("Chrome o Edge non trovati. Apri l'HTML e usa Stampa → Salva come PDF.");
  process.exit(1);
}

const htmlPath = path.resolve(
  __dirname,
  "../GUIDA_PORTALE_GB_CONSTRUCTION/index.html",
);
const outPath = path.resolve(
  __dirname,
  "../GUIDA_PORTALE_GB_CONSTRUCTION/Manuale_Portale_GB_Construction.pdf",
);

const result = spawnSync(
  chrome,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-pdf-header-footer",
    "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=12000",
    `--print-to-pdf=${outPath}`,
    pathToFileURL(htmlPath).href,
  ],
  { stdio: "inherit" },
);

if (result.status !== 0 || !fs.existsSync(outPath)) {
  console.error("Esportazione PDF non riuscita.");
  process.exit(result.status || 1);
}

const stats = fs.statSync(outPath);
console.log(`${outPath} (${Math.round(stats.size / 1024)} KB)`);
