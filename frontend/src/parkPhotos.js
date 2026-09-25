// Your own park photos, by park code. Workflow:
//   1. Put full-size originals in frontend/public/parks/ (not committed; see .gitignore).
//   2. Resized copies (1600px on the long side, no camera metadata) go in
//      frontend/public/gallery/, which is what the app loads.
//   3. List the resized copies here. Parks without photos get a drawn placeholder.
//
// Portrait photos are shown whole, on a blurred copy of themselves; landscape photos
// fill the frame and are trimmed at the edges. To override either, use an object:
//   { src: "/gallery/yose-3.jpg", fit: "cover", focus: "50% 20%" }
//   fit:   "cover" (fill the frame, crop) or "contain" (whole photo on blur)
//   focus: the part to keep when cropping, as "x% y%" ("50% 0%" = top centre)

export const PARK_PHOTOS = {
  BIBE: ["/gallery/bibe-1.jpg", "/gallery/bibe-2.jpg", "/gallery/bibe-3.jpg"],
  CAVE: ["/gallery/cave-1.jpg", "/gallery/cave-2.jpg", "/gallery/cave-3.jpg"],
  CRLA: ["/gallery/crla-1.jpg", "/gallery/crla-2.jpg", "/gallery/crla-3.jpg"],
  DEVA: ["/gallery/deva-1.jpg", "/gallery/deva-2.jpg", "/gallery/deva-3.jpg"],
  GRBA: ["/gallery/grba-1.jpg", "/gallery/grba-2.jpg", "/gallery/grba-3.jpg"],
  GRCA: ["/gallery/grca-1.jpg", "/gallery/grca-2.jpg", "/gallery/grca-3.jpg"],
  GUMO: ["/gallery/gumo-1.jpg", "/gallery/gumo-2.jpg", "/gallery/gumo-3.jpg"],
  JOTR: ["/gallery/jotr-1.jpg", "/gallery/jotr-2.jpg", "/gallery/jotr-3.jpg"],
  LAVO: ["/gallery/lavo-1.jpg", "/gallery/lavo-2.jpg", "/gallery/lavo-3.jpg"],
  MORA: ["/gallery/mora-1.jpg", "/gallery/mora-2.jpg", "/gallery/mora-3.jpg"],
  NOCA: ["/gallery/noca-1.jpg", "/gallery/noca-2.jpg", "/gallery/noca-3.jpg"],
  OLYM: ["/gallery/olym-1.jpg", "/gallery/olym-2.jpg", "/gallery/olym-3.jpg"],
  PEFO: ["/gallery/pefo-1.jpg", "/gallery/pefo-2.jpg", "/gallery/pefo-3.jpg"],
  PINN: ["/gallery/pinn-1.jpg", "/gallery/pinn-2.jpg", "/gallery/pinn-3.jpg"],
  REDW: ["/gallery/redw-1.jpg", "/gallery/redw-2.jpg", "/gallery/redw-3.jpg"],
  SAGU: ["/gallery/sagu-1.jpg", "/gallery/sagu-2.jpg", "/gallery/sagu-3.jpg"],
  SEKI: ["/gallery/seki-1.jpg", "/gallery/seki-2.jpg", "/gallery/seki-3.jpg"],
  WHSA: ["/gallery/whsa-1.jpg", "/gallery/whsa-2.jpg", "/gallery/whsa-3.jpg"],
  YOSE: ["/gallery/yose-1.jpg", "/gallery/yose-2.jpg", "/gallery/yose-3.jpg"],
};
