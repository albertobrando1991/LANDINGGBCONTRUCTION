import {
  captureAuthCallback,
  clearAuthCallback,
  pendingPasswordCallback,
} from "./authCallback";

describe("auth callback", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  test.each(["invite", "recovery"])(
    "conserva il callback %s prima che Supabase ripulisca l'URL",
    (type) => {
      captureAuthCallback(
        { search: "", hash: `#access_token=token&type=${type}` },
        sessionStorage,
      );

      expect(pendingPasswordCallback(sessionStorage)).toBe(true);
    },
  );

  test("ignora un normale accesso autenticato", () => {
    captureAuthCallback(
      { search: "?next=/portal", hash: "#access_token=token&type=magiclink" },
      sessionStorage,
    );

    expect(pendingPasswordCallback(sessionStorage)).toBe(false);
  });

  test("rimuove il callback dopo la scelta della password", () => {
    captureAuthCallback(
      { search: "?type=invite", hash: "" },
      sessionStorage,
    );
    clearAuthCallback(sessionStorage);

    expect(pendingPasswordCallback(sessionStorage)).toBe(false);
  });
});
