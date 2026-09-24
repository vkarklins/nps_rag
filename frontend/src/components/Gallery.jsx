import { useEffect, useState } from "react";
import { BIOMES, biomeForPark } from "../biomes.js";
import { PARK_PHOTOS } from "../parkPhotos.js";
import { SCENES, SCENE_VIEWBOX } from "../scenery.js";

// Three "times of day" for placeholder scenes, so one park still gets a small gallery.
const VARIANTS = [
  { name: "Morning", sunX: 280, sunY: 150, shade: 0 },
  { name: "Midday", sunX: 1080, sunY: 90, shade: 0 },
  { name: "Dusk", sunX: 720, sunY: 250, shade: 0.2 },
];

function PlaceholderScene({ code, variant }) {
  const biome = biomeForPark(code);
  const p = BIOMES[biome];
  const scene = SCENES[biome];
  const v = VARIANTS[variant % VARIANTS.length];
  const gid = `g-${code}-${variant}`;
  return (
    <svg className="placeholder" viewBox={SCENE_VIEWBOX} preserveAspectRatio="xMidYMax slice">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={p.skyTop} />
          <stop offset="1" stopColor={p.skyBottom} />
        </linearGradient>
      </defs>
      <rect width="1440" height="400" fill={`url(#${gid})`} />
      <circle cx={v.sunX} cy={v.sunY} r="46" fill={p.sun} opacity="0.9" />
      <path d={scene.far} fill={p.far} />
      <path d={scene.mid} fill={p.mid} />
      <path d={scene.near} fill={p.near} />
      {v.shade > 0 && <rect width="1440" height="400" fill="#2a1a3a" opacity={v.shade} />}
    </svg>
  );
}

/**
 * A photo entry in parkPhotos.js is either a path string or an object:
 *   { src: "/parks/x.jpg", focus: "50% 30%", fit: "cover" | "contain" }
 * focus: which part of the photo to keep when it's cropped (CSS object-position).
 * fit:   force cropping ("cover") or whole-photo-on-blur ("contain"); by default,
 *        portrait photos get "contain" and landscape photos get "cover".
 */
function Photo({ entry }) {
  const { src, focus, fit } = typeof entry === "string" ? { src: entry } : entry;
  const [portrait, setPortrait] = useState(false);
  const contain = fit ? fit === "contain" : portrait;
  const position = focus || "50% 50%";

  return (
    <div className="photo-wrap">
      {contain && <img className="photo-backdrop" src={src} alt="" aria-hidden="true" />}
      <img
        className={`photo ${contain ? "contain" : ""}`}
        src={src}
        alt=""
        loading="lazy"
        style={{ objectPosition: position }}
        onLoad={(e) => setPortrait(e.currentTarget.naturalHeight > e.currentTarget.naturalWidth)}
      />
    </div>
  );
}

function ParkImage({ code, index }) {
  const photos = PARK_PHOTOS[code] || [];
  if (photos.length) {
    return <Photo entry={photos[index % photos.length]} />;
  }
  return <PlaceholderScene code={code} variant={index} />;
}

/** One park: a slideshow of its images. */
function Hero({ park }) {
  const photos = PARK_PHOTOS[park.code] || [];
  const count = photos.length || VARIANTS.length;
  const [index, setIndex] = useState(0);

  // Back to the first image when the park changes.
  useEffect(() => setIndex(0), [park.code]);

  // Advance every 5 s; depending on `index` restarts the wait after a manual click.
  useEffect(() => {
    const timer = setTimeout(() => setIndex((i) => (i + 1) % count), 5000);
    return () => clearTimeout(timer);
  }, [index, count]);

  return (
    <figure className="hero">
      <div className="hero-frame">
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className={`hero-slide ${i === index ? "on" : ""}`}>
            <ParkImage code={park.code} index={i} />
          </div>
        ))}
      </div>
      <figcaption>
        <span className="park-name">{park.name}</span>
      </figcaption>
      <div className="dots">
        {Array.from({ length: count }, (_, i) => (
          <button
            key={i}
            className={i === index ? "on" : ""}
            onClick={() => setIndex(i)}
            aria-label={`Show image ${i + 1}`}
          />
        ))}
      </div>
    </figure>
  );
}

const MAX_TILES = 6;

export default function Gallery({ parks, caption }) {
  const key = parks.map((p) => p.code).join(",");

  return (
    <section className="gallery" aria-label="Park gallery">
      <div className="panel-title">
        <span>{caption}</span>
      </div>
      <div className="gallery-body" key={key}>
        {parks.length === 0 && (
          <div className="gallery-empty">
            <PlaceholderScene code="__default" variant={0} />
            <p>Ask about a specific park and its pictures will appear here.</p>
          </div>
        )}
        {parks.length === 1 && <Hero park={parks[0]} />}
        {parks.length > 1 && (
          <div className="tiles">
            {parks.slice(0, MAX_TILES).map((park, i) => (
              <figure key={park.code} className="tile" style={{ animationDelay: `${i * 70}ms` }}>
                <ParkImage code={park.code} index={0} />
                <figcaption>{park.name.replace(/ National Parks?( and Preserve)?$/, "")}</figcaption>
              </figure>
            ))}
            {parks.length > MAX_TILES && (
              <div className="tile more">+{parks.length - MAX_TILES} more</div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
