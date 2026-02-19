import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptsDir, "..");

// Node 25's experimental Web Storage emits warnings unless a persistence file is provided.
// Vitest spawns its own runtime processes/isolates; passing `--localstorage-file` as a Node arg
// to the outer process doesn't reliably propagate. Use NODE_OPTIONS so children inherit it.
const localStorageFile = path.join(projectRoot, ".vitest-localstorage.json");
const vitestEntry = path.join(projectRoot, "node_modules", "vitest", "vitest.mjs");

const args = ["--no-warnings", vitestEntry, ...process.argv.slice(2)];

const existingNodeOptions = process.env.NODE_OPTIONS?.trim();
const nodeOptionsParts = [`--localstorage-file ${localStorageFile}`];
if (existingNodeOptions) nodeOptionsParts.push(existingNodeOptions);
const NODE_OPTIONS = nodeOptionsParts.join(" ");

const child = spawn(process.execPath, args, {
  cwd: projectRoot,
  stdio: "inherit",
  env: { ...process.env, NODE_OPTIONS },
});

child.on("exit", (code, signal) => {
  if (typeof code === "number") process.exit(code);
  process.exit(signal ? 1 : 0);
});
