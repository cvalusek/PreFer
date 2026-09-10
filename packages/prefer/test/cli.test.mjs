import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const run = promisify(execFile);

test("the bundled standalone CLI starts without npm or TypeScript", async () => {
  const { stdout } = await run(process.execPath, [fileURLToPath(new URL("../dist/prefer.mjs", import.meta.url)), "help"]);
  assert.match(stdout, /PreFer catalog and release CLI/u);
  assert.match(stdout, /catalog extend/u);
});
