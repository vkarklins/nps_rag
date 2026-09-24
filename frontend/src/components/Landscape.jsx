import { SCENES, SCENE_VIEWBOX } from "../scenery.js";

// Full-page background: a sky gradient and three silhouette layers per biome. All biomes
// are drawn; only the active one is visible, so switching biome cross-fades the shapes
// while the colours (CSS variables) transition underneath.
export default function Landscape({ biome }) {
  return (
    <div className="landscape" aria-hidden="true">
      <div className="sky" />
      <div className="sun" />
      <svg className="scenery" viewBox={SCENE_VIEWBOX} preserveAspectRatio="xMidYMax slice">
        {Object.entries(SCENES).map(([name, scene]) => (
          <g key={name} className={`scene ${name === biome ? "active" : ""}`}>
            <path className="layer far" d={scene.far} />
            <path className="layer mid" d={scene.mid} />
            <path className="layer near" d={scene.near} />
          </g>
        ))}
      </svg>
    </div>
  );
}
