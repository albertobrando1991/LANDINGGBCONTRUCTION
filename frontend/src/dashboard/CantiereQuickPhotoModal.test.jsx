import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CantiereQuickPhotoModal from "./CantiereQuickPhotoModal";
import { compressCampoPhoto } from "@/lib/campoPhotos";
import {
  canUseTenantStorage,
  tenantIdFromUser,
  uploadCantiereDocument,
} from "@/lib/storage";

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { role: "staff", auth_provider: "supabase" } }),
}));

jest.mock("@/lib/campoPhotos", () => ({
  compressCampoPhoto: jest.fn(),
}));

jest.mock("@/lib/storage", () => ({
  canUseTenantStorage: jest.fn(() => true),
  tenantIdFromUser: jest.fn(() => "10000000-0000-4000-8000-000000000001"),
  uploadCantiereDocument: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

test("comprime e salva la foto privata associandola alla fase in corso", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const onClose = jest.fn();
  const onUploaded = jest.fn();
  canUseTenantStorage.mockReturnValue(true);
  tenantIdFromUser.mockReturnValue("10000000-0000-4000-8000-000000000001");
  const compressed = new File(["jpeg"], "compressa.jpg", {
    type: "image/jpeg",
  });
  compressCampoPhoto.mockResolvedValue({ blob: compressed });
  uploadCantiereDocument.mockResolvedValue({ path: "privato/foto.jpg" });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <CantiereQuickPhotoModal
          cantiereId="64b64c8f2f9b2d7a1c000001"
          fasi={[
            { nome: "Demolizioni", stato: "completata" },
            { nome: "Impianti", stato: "in_corso" },
          ]}
          onClose={onClose}
          onUploaded={onUploaded}
        />
      </QueryClientProvider>,
    );
  });

  expect(container.querySelector("select").value).toBe("Impianti");
  const input = container.querySelector('input[type="file"]');
  const source = new File(["foto"], "cantiere.png", { type: "image/png" });
  Object.defineProperty(input, "files", {
    value: [source],
    configurable: true,
  });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const uploadButton = Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent.includes("Comprimi e carica"),
  );
  await act(async () => {
    uploadButton.click();
    await Promise.resolve();
  });

  expect(compressCampoPhoto).toHaveBeenCalledWith(source);
  expect(uploadCantiereDocument).toHaveBeenCalledWith(
    expect.objectContaining({
      cantiereId: "64b64c8f2f9b2d7a1c000001",
      tenantId: "10000000-0000-4000-8000-000000000001",
      file: expect.objectContaining({ type: "image/jpeg" }),
    }),
  );
  expect(uploadCantiereDocument.mock.calls[0][0].file.name).toContain(
    "foto-impianti-",
  );
  expect(onUploaded).toHaveBeenCalledWith({ path: "privato/foto.jpg" });
  expect(onClose).toHaveBeenCalled();

  await act(async () => root.unmount());
  container.remove();
});
