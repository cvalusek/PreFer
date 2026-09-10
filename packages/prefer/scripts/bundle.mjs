import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

await build({
  absWorkingDir: packageRoot,
  entryPoints: [resolve(packageRoot, "src/cli.ts")],
  outfile: resolve(packageRoot, "dist/prefer.mjs"),
  bundle: true,
  platform: "node",
  target: "node24",
  format: "esm",
  sourcemap: true,
  banner: {
    js: "import { createRequire as __preferCreateRequire } from 'node:module'; const require = __preferCreateRequire(import.meta.url);"
  }
});
