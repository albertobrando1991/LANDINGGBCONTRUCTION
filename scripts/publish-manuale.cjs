const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const sourceHtml = path.join(root, "GUIDA_PORTALE_GB_CONSTRUCTION", "index.html");
const shotsDir = path.join(root, "GB_CONSTRUCTION_SCREENSHOTS_PRESENTAZIONE");
const destDir = path.join(root, "frontend", "public", "manuale");
const destShots = path.join(destDir, "shots");

fs.mkdirSync(destShots, { recursive: true });

let html = fs.readFileSync(sourceHtml, "utf8");
html = html.replaceAll(
  "../GB_CONSTRUCTION_SCREENSHOTS_PRESENTAZIONE/",
  "/manuale/shots/",
);

fs.writeFileSync(path.join(destDir, "index.html"), html);

const copied = [];
for (const name of fs.readdirSync(shotsDir)) {
  if (!/\.(png|jpe?g|webp)$/i.test(name)) continue;
  fs.copyFileSync(path.join(shotsDir, name), path.join(destShots, name));
  copied.push(name);
}

console.log(`Published /manuale with ${copied.length} screenshots`);
