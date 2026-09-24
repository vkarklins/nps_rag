// Your own park photos, by park code. Put the files in frontend/public/parks/ and list
// them here; parks without photos get a drawn placeholder in their landscape colours.
//
// Example:
//   YOSE: ["/parks/yose-1.jpg", "/parks/yose-2.jpg"],
//
// Portrait photos are shown whole, on a blurred copy of themselves; landscape photos
// fill the frame and are trimmed at the edges. To override either, use an object:
//   { src: "/parks/yose-3.jpg", fit: "cover", focus: "50% 20%" }
//   fit:   "cover" (fill the frame, crop) or "contain" (whole photo on blur)
//   focus: the part to keep when cropping, as "x% y%" ("50% 0%" = top centre)

export const PARK_PHOTOS = {
  YOSE: ["/parks/yose-1.jpg", "/parks/yose-2.jpg", "/parks/yose-3.jpg"],
};
