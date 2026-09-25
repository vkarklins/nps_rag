// Sample questions for the welcome screen.
//
// The pool is in priority order. pickExamples() shows only questions for parks that have
// photos in parkPhotos.js: first one question per landscape theme (so clicking through
// them shows off different themes), then fills any remaining slots in pool order. The
// result is the same on every page load. Questions for parks without photos wait in the
// pool and start appearing once photos are added for them.
//
// Every topic here was checked against data/incidents.jsonl (2026-09-24) with a keyword
// search, to make sure the park has matching reports.

import { biomeForPark } from "./biomes.js";
import { PARK_PHOTOS } from "./parkPhotos.js";

export const QUESTION_POOL = [
  // Current picks (parks with photos), one per theme
  { park: "GRCA", q: "What falls have happened at the Grand Canyon?" },
  { park: "DEVA", q: "What should I know before hiking in Death Valley in summer?" },
  { park: "MORA", q: "What climbing accidents have happened on Mount Rainier?" },
  { park: "YOSE", q: "What rockfall incidents have been reported in Yosemite?" },
  { park: "LAVO", q: "Have visitors been hurt in Lassen Volcanic's hydrothermal areas?" },
  { park: "OLYM", q: "What incidents have been reported on Olympic's beaches and rivers?" },

  // More parks with photos
  { park: "JOTR", q: "What climbing accidents have happened in Joshua Tree?" },
  { park: "SEKI", q: "Have there been drownings in Sequoia and Kings Canyon?" },
  { park: "CAVE", q: "What rescues have happened inside Carlsbad Caverns?" },
  { park: "BIBE", q: "What heat or river incidents have been reported in Big Bend?" },
  { park: "NOCA", q: "What climbing accidents have happened in North Cascades?" },
  { park: "CRLA", q: "Have people fallen at Crater Lake?" },
  { park: "REDW", q: "What incidents have been reported in Redwood?" },
  { park: "PINN", q: "What climbing rescues have happened at Pinnacles?" },
  { park: "WHSA", q: "Have hikers gotten lost at White Sands?" },
  { park: "SAGU", q: "What search and rescue incidents have happened in Saguaro?" },
  { park: "PEFO", q: "Has anyone been caught taking petrified wood from Petrified Forest?" },
  { park: "GUMO", q: "What rescues have happened in Guadalupe Mountains?" },
  { park: "GRBA", q: "Have hikers gone missing in Great Basin?" },

  // Parks without photos yet
  { park: "GLAC", q: "What bear encounters have been reported in Glacier?" },
  { park: "DENA", q: "What climbing accidents have happened on Denali?" },
  { park: "YELL", q: "What should I know about thermal areas in Yellowstone?" },
  { park: "HAVO", q: "What lava-related incidents have happened in Hawaii Volcanoes?" },
  { park: "VIIS", q: "Any snorkeling or swimming incidents in the Virgin Islands?" },
  { park: "ZION", q: "What flash flood incidents have been reported in Zion?" },
  { park: "EVER", q: "What alligator or boating incidents have happened in the Everglades?" },
  { park: "GRSM", q: "What bear incidents have been reported in the Smokies?" },
  { park: "ROMO", q: "Have people been struck by lightning in Rocky Mountain?" },
  { park: "KATM", q: "What bear encounters have happened in Katmai?" },
  { park: "GLBA", q: "What kayaking or boating incidents have happened in Glacier Bay?" },
];

export function pickExamples(count = 6, photos = PARK_PHOTOS) {
  const hasPhotos = (item) => (photos[item.park] || []).length > 0;
  // With no photos at all, fall back to the whole pool.
  const pool = QUESTION_POOL.some(hasPhotos) ? QUESTION_POOL.filter(hasPhotos) : QUESTION_POOL;

  const chosen = new Set();
  const themes = new Set();
  for (const item of pool) {
    if (chosen.size === count) break;
    const theme = biomeForPark(item.park);
    if (!themes.has(theme)) {
      themes.add(theme);
      chosen.add(item);
    }
  }
  for (const item of pool) {
    if (chosen.size === count) break;
    chosen.add(item);
  }
  // Show them in pool order.
  return pool.filter((item) => chosen.has(item)).map((item) => item.q);
}
