const { spawnSync } = require("node:child_process");

const command =
  process.platform === "win32"
    ? {
        executable: process.env.ComSpec || "cmd.exe",
        args: ["/d", "/s", "/c", "npm audit --omit=dev --json"],
      }
    : { executable: "npm", args: ["audit", "--omit=dev", "--json"] };
const result = spawnSync(command.executable, command.args, {
  cwd: require("node:path").join(__dirname, "..", "frontend"),
  encoding: "utf8",
});

if (!result.stdout) {
  process.stderr.write(result.stderr || "npm audit non ha restituito un report.\n");
  process.exit(1);
}

let report;
try {
  report = JSON.parse(result.stdout);
} catch {
  process.stderr.write("Report npm audit non valido.\n");
  process.exit(1);
}

const vulnerabilities = report.vulnerabilities || {};
const allowedPackages = new Set(["react-router", "react-router-dom"]);
const unexpected = Object.keys(vulnerabilities).filter(
  (name) => !allowedPackages.has(name),
);

const router = vulnerabilities["react-router"];
const routerDom = vulnerabilities["react-router-dom"];
const routerAdvisories = (router?.via || []).filter(
  (entry) => typeof entry === "object",
);
const allowedRouterAdvisory = routerAdvisories.every(
  (entry) =>
    entry.url === "https://github.com/advisories/GHSA-qwww-vcr4-c8h2" &&
    /RSC Mode/i.test(entry.title || ""),
);
const allowedRouterDomChain = (routerDom?.via || []).every(
  (entry) => entry === "react-router",
);

if (
  unexpected.length ||
  (router && (routerAdvisories.length !== 1 || !allowedRouterAdvisory)) ||
  (routerDom &&
    ((routerDom.via || []).length !== 1 || !allowedRouterDomChain))
) {
  process.stderr.write(
    `Vulnerabilità runtime non ammesse: ${unexpected.join(", ") || "advisory router non riconosciuto"}.\n`,
  );
  process.exit(1);
}

const count = report.metadata?.vulnerabilities?.total || 0;
process.stdout.write(
  count
    ? "Audit runtime verde con eccezione documentata per React Router RSC (modalità non usata).\n"
    : "Audit runtime verde: nessuna vulnerabilità nota.\n",
);
