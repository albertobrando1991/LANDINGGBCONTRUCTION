const CACHE_NAME = "gb-app-v3";
const SHELL = ["/", "/manifest.json", "/campo.webmanifest", "/favicon.svg"];

async function precacheApplication() {
  const cache = await caches.open(CACHE_NAME);
  await Promise.all(SHELL.map((url) => cache.add(url).catch(() => undefined)));
  try {
    const response = await fetch("/asset-manifest.json", { cache: "no-store" });
    if (!response.ok) return;
    const manifest = await response.json();
    const assets = new Set([
      ...(manifest.entrypoints || []),
      ...Object.values(manifest.files || {}),
    ]);
    await Promise.all(
      [...assets]
        .filter((url) => typeof url === "string" && !url.endsWith(".map"))
        .map((url) => cache.add(url).catch(() => undefined)),
    );
  } catch {
    // La cache runtime continua a funzionare anche senza asset manifest.
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(precacheApplication());
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter(
              (name) =>
                (name.startsWith("gb-campo-") || name.startsWith("gb-app-")) &&
                name !== CACHE_NAME,
            )
            .map((name) => caches.delete(name)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put("/", copy));
          }
          return response;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }

  if (["script", "style", "font", "image"].includes(request.destination)) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
});
