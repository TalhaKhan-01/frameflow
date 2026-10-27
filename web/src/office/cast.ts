// The people of Thirdspace House (P17): one entry per board desk (ids from desks.ts DESKS) plus the new hires, the
// street and the owner. Names chosen by Talha on 27 Oct; the creative source is the vault's Docs/Cast Bible.md.
// tests/test_cast.py fails when a desk has no cast entry.
export interface Person {
  id: string;
  name: string;
  title: string;
  catchphrase: string;
  rival: string;    // a cast id, or a thing ("the clock")
  cue: string;      // the voice cue played with the chat bubble (P17.2.4)
  voice: string;    // starting description for VoiceStudio voice design (P17.2); "house" = Habit's house voice
  floor?: string;   // only for people without a desk in desks.ts
}

export const CAST: Person[] = [
  { id: "narrator", name: "Habit", title: "Bade Sahab ka Khaas", catchphrase: "Make learning a Habit.", rival: "everyone", cue: "chime", voice: "house" },
  { id: "you", name: "Bade Sahab", title: "The Owner", catchphrase: "…", rival: "nobody dares", cue: "phone", voice: "muffled, through a phone" },
  { id: "showrunner", name: "Deadline Didi", title: "Showrunner", catchphrase: "11:30 matlab 11:30.", rival: "the clock", cue: "stopwatch", voice: "female, 30s, brisk, firm, Indian English" },
  { id: "researcher", name: "Googly", title: "Researcher", catchphrase: "Breaking! …probably.", rival: "factcheck", cue: "tab-pop", voice: "young male, fast, high energy, Hinglish" },
  { id: "factcheck", name: "Sach-in", title: "Fact-checker", catchphrase: "Source dikhao.", rival: "researcher", cue: "stamp", voice: "male, 40s, low, slow, dry" },
  { id: "packaging", name: "Click Bhai", title: "Packaging", catchphrase: "Bhai, thumbnail pe laal arrow?", rival: "standards", cue: "double-click", voice: "male, 20s, salesy, upbeat, Mumbai street" },
  { id: "writer", name: "Kavi Kalam", title: "Writer", catchphrase: "Yeh line dil se likhi hai.", rival: "editor", cue: "typewriter", voice: "male, 30s, expressive, theatrical, warm" },
  { id: "editor", name: "Kat", title: "Script Editor", catchphrase: "Kat.", rival: "writer", cue: "snip", voice: "female, 20s, flat, dry, quiet" },
  { id: "director", name: "Frame Prakash", title: "Director", catchphrase: "Light, camera, PRAKASH!", rival: "animator", cue: "clapper", voice: "male, 50s, booming, filmy" },
  { id: "standards", name: "Mr. Disclaimer", title: "Standards", catchphrase: "Terms and conditions apply.", rival: "packaging", cue: "pen-click", voice: "male, 60s, gentle, precise, British-Indian" },
  { id: "animatic", name: "Flip", title: "Animatic", catchphrase: "Draft hai, dil pe mat lo.", rival: "artdirector", cue: "flipbook", voice: "young, fast, light" },
  { id: "artdirector", name: "Rangeela", title: "Art Director", catchphrase: "Yeh colour humara nahi hai.", rival: "director", cue: "brush", voice: "female, 30s, sing-song, expressive" },
  { id: "screening", name: "Seeti", title: "Screening", catchphrase: "Seeti maar scene!", rival: "writer", cue: "whistle", voice: "male, 30s, loud, theatre-audience energy" },
  { id: "animator", name: "Buffer Bhaiya", title: "Render Rig", catchphrase: "Ek minute… ek minute…", rival: "director", cue: "fan-whir", voice: "male, 40s, tired, slow, out of breath" },
  { id: "qc", name: "Pixel Pandey", title: "QC", catchphrase: "Ek pixel idhar-udhar.", rival: "artdirector", cue: "loupe-ping", voice: "male, 50s, fussy, nasal" },
  { id: "publisher", name: "Postmaster Pintu", title: "Publisher", catchphrase: "Post ho gaya, sir!", rival: "the platforms", cue: "bicycle-bell", voice: "male, 40s, cheerful, small-town" },
  { id: "analyst", name: "Views-wananthan", title: "Analyst", catchphrase: "Data jhooth nahi bolta.", rival: "trendulkar", cue: "chalk", voice: "male, 50s, measured, South Indian English" },
  // new hires (P20): they get desks when their modules exist
  { id: "dhwani", name: "DJ Dhwani", title: "Sound Designer", catchphrase: "Drop ka wait karo.", rival: "editor", cue: "scratch", voice: "female, 20s, cool, laid-back", floor: "2" },
  { id: "kabadi", name: "Kabadi Kumar", title: "Footage Scavenger", catchphrase: "Free ka maal, licence ke saath.", rival: "director", cue: "sack", voice: "male, 30s, street-smart, cheerful", floor: "B" },
  { id: "trendulkar", name: "Trendulkar", title: "Trend Scout", catchphrase: "Yeh topic century maarega.", rival: "analyst", cue: "bat-tock", voice: "male, 20s, confident, cricket commentator", floor: "G" },
  // the street
  { id: "chaiwala", name: "Gossip Guru Chai-tanya", title: "Chaiwala", catchphrase: "Chai piyo, khabar suno.", rival: "Bade Sahab's secrets", cue: "kettle", voice: "male, 50s, warm, conspiratorial", floor: "street" },
  { id: "cat", name: "Cache", title: "The Cat", catchphrase: "Meow.", rival: "Buffer Bhaiya's warm top", cue: "meow", voice: "none", floor: "awning" },
];
export const PERSON = Object.fromEntries(CAST.map((p) => [p.id, p])) as Record<string, Person>;
