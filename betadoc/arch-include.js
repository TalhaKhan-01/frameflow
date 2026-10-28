// The architecture page's body lives once in src/arch-body.html; both the betadoc and the Studio (web/) build it into
// their own architecture.html shell (each with its own header and footer) through this plugin.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const BODY = resolve(import.meta.dirname, "src/arch-body.html");

export const archInclude = () => ({
  name: "arch-include",
  transformIndexHtml: { order: "pre", handler: (html) => html.replace("<!--arch-body-->", readFileSync(BODY, "utf8")) },
});
