import { fileURLToPath } from "node:url";
import path from "node:path";
import process from "node:process";
import dotenv from "dotenv";
import { StitchProxy } from "@google/stitch-sdk";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, "..", "..");
dotenv.config({ path: path.join(projectRoot, ".env"), quiet: true });

const apiKey = String(process.env.STITCH_API_KEY || "").trim();
if (!apiKey) {
  process.stderr.write(
    "STITCH_API_KEY non configurata. Aggiungila al file .env locale del progetto.\n",
  );
  process.exit(1);
}

const proxy = new StitchProxy({ apiKey });
const transport = new StdioServerTransport();
await proxy.start(transport);
