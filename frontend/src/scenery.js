// Procedurally drawn landscape silhouettes, one set per biome. Each scene is three layers
// (far, mid, near) of SVG path data in a 1440 x 400 box, filled with the biome's colours.
// Used for the page background and the placeholder gallery images.

const W = 1440;
const H = 400;

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const close = (d) => `${d} L ${W} ${H} L 0 ${H} Z`;

/** Jagged mountain ridge. */
function ridge(seed, base, amp, peaks, width = W) {
  const r = rng(seed);
  let d = `M 0 ${base}`;
  const step = width / (peaks * 2);
  for (let i = 1; i <= peaks * 2; i++) {
    const x = i * step + (r() - 0.5) * step * 0.6;
    const up = i % 2 === 1;
    const y = up ? base - amp * (0.45 + r() * 0.55) : base - amp * r() * 0.3;
    d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return close(`${d} L ${W} ${base}`);
}

/** Smooth rolling hills / dunes. */
function hills(seed, base, amp, n) {
  const r = rng(seed);
  const pts = [];
  for (let i = 0; i <= n; i++) {
    pts.push([(i / n) * W, base - amp * (0.2 + r() * 0.8)]);
  }
  let d = `M 0 ${pts[0][1].toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1];
    const [x1, y1] = pts[i];
    const mx = (x0 + x1) / 2;
    d += ` C ${mx.toFixed(1)} ${y0.toFixed(1)}, ${mx.toFixed(1)} ${y1.toFixed(1)}, ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  }
  return close(d);
}

/** Flat-topped mesas and buttes. */
function mesas(seed, base, amp, n) {
  const r = rng(seed);
  let d = `M 0 ${base}`;
  let x = 0;
  for (let i = 0; i < n && x < W; i++) {
    const gap = 40 + r() * 120;
    const width = 80 + r() * 220;
    const top = base - amp * (0.4 + r() * 0.6);
    const slope = 20 + r() * 30;
    x += gap;
    d += ` L ${x} ${base} L ${x + slope * 0.4} ${top + 10} L ${x + slope} ${top}`;
    d += ` L ${x + width - slope} ${top} L ${x + width - slope * 0.4} ${top + 12} L ${x + width} ${base}`;
    x += width;
  }
  return close(`${d} L ${W} ${base}`);
}

/** A row of pine trees standing on a gentle hill line. */
function pines(seed, base, size, count) {
  const r = rng(seed);
  let d = `M 0 ${base}`;
  const step = W / count;
  for (let i = 0; i < count; i++) {
    const cx = i * step + step / 2 + (r() - 0.5) * step * 0.5;
    const h = size * (0.6 + r() * 0.6);
    const w = h * 0.36;
    const ground = base - Math.sin((cx / W) * Math.PI * 2 + seed) * 12;
    d += ` L ${(cx - w).toFixed(1)} ${ground.toFixed(1)}`;
    d += ` L ${(cx - w * 0.45).toFixed(1)} ${(ground - h * 0.45).toFixed(1)}`;
    d += ` L ${(cx - w * 0.7).toFixed(1)} ${(ground - h * 0.45).toFixed(1)}`;
    d += ` L ${cx.toFixed(1)} ${(ground - h).toFixed(1)}`;
    d += ` L ${(cx + w * 0.7).toFixed(1)} ${(ground - h * 0.45).toFixed(1)}`;
    d += ` L ${(cx + w * 0.45).toFixed(1)} ${(ground - h * 0.45).toFixed(1)}`;
    d += ` L ${(cx + w).toFixed(1)} ${ground.toFixed(1)}`;
  }
  return close(`${d} L ${W} ${base}`);
}

/** Gentle waves. */
function waves(seed, base, amp, n) {
  let d = `M 0 ${base}`;
  for (let i = 0; i <= 96; i++) {
    const x = (i / 96) * W;
    const y = base + Math.sin((i / 96) * Math.PI * 2 * n + seed) * amp;
    d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return close(d);
}

/** A broad volcano cone. */
function volcano(base, peakX, height, width) {
  const l = peakX - width / 2;
  const rgt = peakX + width / 2;
  return close(
    `M 0 ${base} L ${l} ${base} C ${peakX - width * 0.2} ${base - height * 0.6}, ${peakX - 60} ${base - height}, ${peakX - 30} ${base - height}` +
      ` L ${peakX + 30} ${base - height} C ${peakX + 60} ${base - height}, ${peakX + width * 0.2} ${base - height * 0.6}, ${rgt} ${base} L ${W} ${base}`
  );
}

export const SCENES = {
  default: { far: ridge(3, 260, 170, 6), mid: hills(8, 320, 90, 6), near: pines(5, 380, 70, 26) },
  desert: { far: mesas(11, 250, 90, 5), mid: hills(4, 320, 70, 5), near: hills(19, 375, 45, 4) },
  canyon: { far: mesas(7, 230, 130, 6), mid: mesas(21, 300, 110, 5), near: hills(2, 380, 40, 7) },
  forest: { far: hills(12, 240, 110, 5), mid: pines(9, 320, 90, 30), near: pines(31, 390, 130, 22) },
  alpine: { far: ridge(17, 250, 210, 5), mid: ridge(6, 310, 120, 7), near: pines(14, 385, 95, 24) },
  arctic: { far: ridge(23, 240, 220, 4), mid: ridge(41, 305, 110, 6), near: hills(5, 385, 25, 9) },
  coastal: { far: hills(29, 280, 60, 3), mid: waves(1, 330, 8, 5), near: waves(3, 370, 10, 4) },
  volcanic: { far: volcano(290, 820, 200, 1100), mid: hills(13, 330, 60, 6), near: hills(37, 385, 35, 8) },
  prairie: { far: mesas(43, 270, 60, 7), mid: hills(15, 320, 40, 8), near: hills(27, 375, 25, 10) },
};

export const SCENE_VIEWBOX = `0 0 ${W} ${H}`;
