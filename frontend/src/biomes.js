// Landscape "biomes": each park maps to one, and each biome has a palette. The palette is
// applied as CSS custom properties (registered with @property in styles.css so colour
// changes animate), and drives the background scenery and placeholder gallery images.

export const BIOMES = {
  default: {
    label: "National parks",
    skyTop: "#cfdde0", skyBottom: "#f4ecdc", sun: "#e7b46a",
    far: "#9fb5ad", mid: "#6f8f7e", near: "#3c5a49",
    accent: "#3d6450", accentInk: "#ffffff", tint: "#f7f2e7",
  },
  desert: {
    label: "Desert",
    skyTop: "#f2c98b", skyBottom: "#fbeccb", sun: "#f4a53c",
    far: "#e2b77f", mid: "#c8915a", near: "#9a6437",
    accent: "#a8612b", accentInk: "#ffffff", tint: "#fbf3e4",
  },
  canyon: {
    label: "Red rock canyon",
    skyTop: "#9cc3d9", skyBottom: "#f6dfc6", sun: "#f3b05a",
    far: "#d99a78", mid: "#bc6843", near: "#86412a",
    accent: "#a9472a", accentInk: "#ffffff", tint: "#faf0e8",
  },
  forest: {
    label: "Dense forest",
    skyTop: "#b9d4c4", skyBottom: "#eef3e2", sun: "#e9d58c",
    far: "#86ab8d", mid: "#4f7d5c", near: "#244c35",
    accent: "#2f6b45", accentInk: "#ffffff", tint: "#f1f5ec",
  },
  alpine: {
    label: "Alpine mountains",
    skyTop: "#8fb3d6", skyBottom: "#e8eff2", sun: "#f1dc9a",
    far: "#aebfcf", mid: "#6d8497", near: "#2f4a42",
    accent: "#3a5f7d", accentInk: "#ffffff", tint: "#f0f4f6",
  },
  arctic: {
    label: "Glaciers & tundra",
    skyTop: "#a9cde8", skyBottom: "#eef7fb", sun: "#fdf1c7",
    far: "#d4e6f1", mid: "#9dc0d9", near: "#5a88a8",
    accent: "#2f6f9a", accentInk: "#ffffff", tint: "#f2f8fb",
  },
  coastal: {
    label: "Coast & tropics",
    skyTop: "#7fd0dc", skyBottom: "#eaf8f4", sun: "#ffd27a",
    far: "#8fcfc4", mid: "#3fa3a0", near: "#1c6e73",
    accent: "#16767a", accentInk: "#ffffff", tint: "#effaf8",
  },
  volcanic: {
    label: "Volcanic",
    skyTop: "#e6a784", skyBottom: "#f7e3d3", sun: "#ff7a3c",
    far: "#8c7a78", mid: "#5a4a4c", near: "#2b2326",
    accent: "#b7472a", accentInk: "#ffffff", tint: "#f8efea",
  },
  prairie: {
    label: "Prairie & badlands",
    skyTop: "#a8c8e0", skyBottom: "#f5efd6", sun: "#f5c567",
    far: "#d6c9a0", mid: "#b39f68", near: "#7a6a3a",
    accent: "#8a6d2a", accentInk: "#ffffff", tint: "#f8f4e6",
  },
};

export const PARK_BIOMES = {
  // Deserts
  DEVA: "desert", JOTR: "desert", SAGU: "desert", WHSA: "desert", GRSA: "desert",
  BIBE: "desert", GUMO: "desert", PEFO: "desert", CAVE: "desert", GRBA: "desert",
  // Red rock & canyons
  ARCH: "canyon", BRCA: "canyon", CANY: "canyon", CARE: "canyon", ZION: "canyon",
  GRCA: "canyon", MEVE: "canyon", BLCA: "canyon", PINN: "canyon",
  // Forests
  GRSM: "forest", SHEN: "forest", CONG: "forest", CUVA: "forest", REDW: "forest",
  OLYM: "forest", MACA: "forest", HOSP: "forest", NERI: "forest", ACAD: "forest",
  VOYA: "forest", ISRO: "forest", SEKI: "forest", YOSE: "forest", INDU: "forest",
  // Alpine mountains
  ROMO: "alpine", GLAC: "alpine", GRTE: "alpine", MORA: "alpine", NOCA: "alpine",
  CRLA: "alpine", YELL: "alpine",
  // Cold: Alaska
  DENA: "arctic", GAAR: "arctic", GLBA: "arctic", KATM: "arctic", KEFJ: "arctic",
  KOVA: "arctic", LACL: "arctic", WRST: "arctic",
  // Coast & tropics
  BISC: "coastal", DRTO: "coastal", EVER: "coastal", VIIS: "coastal", NPSA: "coastal",
  CHIS: "coastal",
  // Volcanic
  HAVO: "volcanic", HALE: "volcanic", LAVO: "volcanic",
  // Prairie & badlands
  BADL: "prairie", THRO: "prairie", WICA: "prairie",
  // JEFF (Gateway Arch) and anything unknown -> default
};

export function biomeForPark(code) {
  return PARK_BIOMES[code] || "default";
}

/** The most common biome among `codes` (first one wins a tie), or "default". */
export function dominantBiome(codes) {
  if (!codes || codes.length === 0) return "default";
  const counts = new Map();
  for (const code of codes) {
    const biome = biomeForPark(code);
    counts.set(biome, (counts.get(biome) || 0) + 1);
  }
  let best = "default";
  let bestCount = 0;
  for (const [biome, count] of counts) {
    if (count > bestCount) {
      best = biome;
      bestCount = count;
    }
  }
  return best;
}

/** CSS custom properties for a biome, for the app's root style. */
export function biomeStyle(biome) {
  const p = BIOMES[biome] || BIOMES.default;
  return {
    "--sky-top": p.skyTop,
    "--sky-bottom": p.skyBottom,
    "--sun": p.sun,
    "--far": p.far,
    "--mid": p.mid,
    "--near": p.near,
    "--accent": p.accent,
    "--accent-ink": p.accentInk,
    "--tint": p.tint,
  };
}
