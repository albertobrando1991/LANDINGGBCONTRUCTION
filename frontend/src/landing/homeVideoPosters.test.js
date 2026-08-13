import fs from "fs";
import path from "path";
import { CANTIERE_VIDEOS } from "@/lib/assets";

function publicFile(assetUrl) {
  const relativePath = decodeURIComponent(assetUrl).replace(/^\//, "");
  return path.join(process.cwd(), "public", relativePath);
}

test("le card della home usano cover leggere, presenti e univoche", () => {
  const previews = CANTIERE_VIDEOS.map((video) => video.previewPoster);

  expect(new Set(previews).size).toBe(CANTIERE_VIDEOS.length);
  for (const preview of previews) {
    expect(preview).toMatch(/^\/cantieri\/previews\/.+\.webp$/);
    expect(fs.statSync(publicFile(preview)).size).toBeLessThanOrEqual(50_000);
  }
});

test("il payload complessivo delle cover per le card resta sotto il 25% degli originali", () => {
  const originalBytes = CANTIERE_VIDEOS.reduce(
    (total, video) => total + fs.statSync(publicFile(video.poster)).size,
    0,
  );
  const previewBytes = CANTIERE_VIDEOS.reduce(
    (total, video) => total + fs.statSync(publicFile(video.previewPoster)).size,
    0,
  );

  expect(previewBytes).toBeLessThanOrEqual(originalBytes * 0.25);
});
