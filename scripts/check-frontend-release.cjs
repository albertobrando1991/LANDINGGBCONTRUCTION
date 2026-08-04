const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");

const root = path.resolve(__dirname, "..");
const buildDir = path.join(root, "frontend", "build");

function fail(message) {
  console.error(`Release frontend non valida: ${message}`);
  process.exitCode = 1;
}

function read(relativePath) {
  const target = path.join(buildDir, relativePath);
  if (!fs.existsSync(target)) {
    fail(`manca ${relativePath}`);
    return "";
  }
  return fs.readFileSync(target, "utf8");
}

const index = read("index.html");
const robots = read("robots.txt");
const sitemap = read("sitemap.xml");
const manifestRaw = read("manifest.json");
read("favicon.svg");

for (const [label, pattern] of [
  ["lingua italiana", /<html lang="it">/i],
  ["canonical produzione", /rel="canonical" href="https:\/\/gbconstruction\.it\/"/i],
  ["structured data LocalBusiness", /"@type":\s*"GeneralContractor"/i],
]) {
  if (!pattern.test(index)) fail(`index.html senza ${label}`);
}

for (const forbidden of ["posthog.init", "session_recording", "phc_"]) {
  if (index.toLowerCase().includes(forbidden.toLowerCase())) {
    fail(`analytics non consensuale rilevato: ${forbidden}`);
  }
}

if (!robots.includes("Sitemap: https://gbconstruction.it/sitemap.xml")) {
  fail("robots.txt senza sitemap di produzione");
}
if (!sitemap.includes("<loc>https://gbconstruction.it/</loc>")) {
  fail("sitemap.xml senza homepage canonica");
}

try {
  const manifest = JSON.parse(manifestRaw);
  if (manifest.lang !== "it" || manifest.start_url !== "/") {
    fail("manifest.json non allineato alla produzione italiana");
  }
} catch (error) {
  fail(`manifest.json non valido: ${error.message}`);
}

const jsDir = path.join(buildDir, "static", "js");
const mainFile = fs.existsSync(jsDir)
  ? fs.readdirSync(jsDir).find((name) => /^main\..+\.js$/.test(name))
  : null;
if (!mainFile) {
  fail("bundle main non trovato");
} else {
  const raw = fs.readFileSync(path.join(jsDir, mainFile));
  const gzipBytes = zlib.gzipSync(raw, { level: 9 }).length;
  const budgetBytes = 180 * 1024;
  if (gzipBytes > budgetBytes) {
    fail(`bundle main ${gzipBytes} byte gzip oltre il budget ${budgetBytes}`);
  } else {
    console.log(`Bundle main: ${gzipBytes} byte gzip (budget ${budgetBytes})`);
  }
}

if (!process.exitCode) {
  console.log("Metadata, privacy analytics e budget frontend verificati.");
}
