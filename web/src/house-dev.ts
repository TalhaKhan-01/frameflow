// Dev harness for Thirdspace House (P16, not deployed): the building with the real Studio snapshot.
import "./sampler.css";
import { mountHouse } from "./office/house";

const data = await (await fetch("/data/studio.json")).json();
const makes = data.videos.filter((v: { timeline?: unknown }) => v.timeline)
  .map((v: { id: string; yt_title?: string; title: string; timeline: never }) => ({ id: v.id, title: v.yt_title || v.title, timeline: v.timeline, href: `/#/video/${v.id}` }));
const night = new URLSearchParams(location.search).get("night");
const house = mountHouse(document.getElementById("house")!, {
  makes, night: night === null ? undefined : night === "1",
  stats: ["901 ideas collected so far.", "4 videos made, 2 posted.", "The kettle is always on."],
  links: { library: "/#/library", lessons: "/#/lessons" },
});
(window as unknown as { house: unknown }).house = house;
