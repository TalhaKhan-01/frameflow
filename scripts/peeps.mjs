/* Regenerate the drawn cast in scenes/_cast/ from DiceBear's open-peeps style (Open Peeps by Pablo Stanley, CC0 1.0).

     npm i --prefix <tmp> @dicebear/core@9.4.2 @dicebear/open-peeps@9.4.2
     node scripts/peeps.mjs <tmp>/node_modules

   Output is plain SVG (deterministic: fixed options, no seed randomness left), one file per person and face,
   plus cast.json. Renders never need the packages: the build inlines the SVGs a scene uses. */
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const mods = process.argv[2];
if (!mods) { console.error("usage: node scripts/peeps.mjs <node_modules>"); process.exit(2); }
const { createAvatar } = await import(pathToFileURL(path.join(mods, "@dicebear/core/lib/index.js")));
const style = await import(pathToFileURL(path.join(mods, "@dicebear/open-peeps/lib/index.js")));

const OUT = path.join(path.dirname(new URL(import.meta.url).pathname), "..", "scenes", "_cast");
// every option fixed, so the drawing never depends on DiceBear's seeded picks
const PEOPLE = {
  student:   { head: "short4",     skin: "d08b5b", cloth: "8fa7df" },
  friend:    { head: "long",       skin: "edb98a", cloth: "e78276" },
  techie:    { head: "mediumStraight", skin: "d08b5b", cloth: "78e185", acc: "glasses" },
  uncle:     { head: "turban",     skin: "ae5d29", cloth: "ffcf77", hair: "full" },
  auntie:    { head: "grayBun",    skin: "ae5d29", cloth: "e279c7" },
  neighbour: { head: "hijab",      skin: "edb98a", cloth: "9ddadb" },
  elder:     { head: "noHair2",    skin: "694d3d", cloth: "9ddadb", hair: "moustache1", acc: "glasses2" },
};
const FACES = ["smile", "explaining", "concerned", "awe", "suspicious", "serious", "fear", "smileLOL"];

fs.mkdirSync(OUT, { recursive: true });
for (const [who, p] of Object.entries(PEOPLE)) for (const face of FACES) {
  const svg = createAvatar(style, {
    seed: who, head: [p.head], face: [face], skinColor: [p.skin], clothingColor: [p.cloth], headContrastColor: ["2c1b18"],
    facialHair: p.hair ? [p.hair] : [], facialHairProbability: p.hair ? 100 : 0,
    accessories: p.acc ? [p.acc] : [], accessoriesProbability: p.acc ? 100 : 0, maskProbability: 0,
  }).toString()
    .replace(/<metadata[\s\S]*?<\/metadata>/, "")   // licence lives in LICENSE.txt, not in every file
    // the viewBox mask repeats one id in every file; a nested <svg> clips to its viewBox anyway
    .replace(/<mask id="viewboxMask">[\s\S]*?<\/mask>/, "").replace(' mask="url(#viewboxMask)"', "");
  fs.writeFileSync(path.join(OUT, `${who}-${face}.svg`), svg);
}
fs.writeFileSync(path.join(OUT, "cast.json"), JSON.stringify({ people: Object.keys(PEOPLE), faces: FACES, viewBox: 704,
  source: "@dicebear/open-peeps 9.4.2 (Open Peeps by Pablo Stanley)", licence: "CC0 1.0" }, null, 1) + "\n");
console.log(`${Object.keys(PEOPLE).length * FACES.length} SVGs in ${OUT}`);
