import { useMemo, useRef, useState } from "react";
import { Camera, Loader2, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";
import { compressCampoPhoto } from "@/lib/campoPhotos";
import { uploadOrQueueCantiereArchive } from "@/lib/cantiereArchive";

function phaseFilename(phase) {
  const slug =
    String(phase || "generale")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "generale";
  return `foto-${slug}-${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`;
}

export default function CantiereQuickPhotoModal({
  cantiereId,
  fasi = [],
  onClose,
  onUploaded,
}) {
  const qc = useQueryClient();
  const { user } = useAuth() || {};
  const { slug } = useTenant();
  const inputRef = useRef(null);
  const defaultPhase = useMemo(
    () =>
      fasi.find((fase) => fase.stato === "in_corso")?.nome ||
      fasi[0]?.nome ||
      "Generale",
    [fasi],
  );
  const [phase, setPhase] = useState(defaultPhase);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);

  const upload = async () => {
    if (!file || busy) return;
    setBusy(true);
    try {
      const compressed = await compressCampoPhoto(file);
      const photo = new File([compressed.blob], phaseFilename(phase), {
        type: "image/jpeg",
        lastModified: Date.now(),
      });
      const result = await uploadOrQueueCantiereArchive({
        cantiereId,
        file: photo,
        tenantSlug: slug,
        userId: user?.id || user?.email,
        label: `Foto cantiere - ${phase}`,
      });
      if (!result.queued) {
        qc.invalidateQueries({
          queryKey: ["cantiere-portale-documenti", cantiereId],
        });
      }
      toast.success(
        result.queued
          ? "Foto salvata offline e in attesa di sincronizzazione"
          : "Foto salvata nell'archivio privato del cantiere",
      );
      onUploaded?.(
        result.queued
          ? { _offline_pending: true, displayName: photo.name }
          : result.data,
      );
      onClose();
    } catch (error) {
      toast.error(error?.message || "Foto non caricata");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Foto rapida cantiere"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4"
    >
      <section className="w-full max-w-md rounded-2xl border border-stroke bg-surface p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-display text-lg uppercase text-ink">
              Foto rapida
            </h3>
            <p className="mt-1 text-xs text-fog">
              La foto viene compressa e salvata come documento privato. Potrai
              condividerla dal Portale cliente.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Chiudi foto rapida"
            className="rounded-lg p-2 text-fog hover:text-ink disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-5 space-y-4">
          <label className="block space-y-1">
            <span className="font-display text-[10px] uppercase text-fog">
              Fase associata
            </span>
            <select
              value={phase}
              onChange={(event) => setPhase(event.target.value)}
              disabled={busy}
              className="w-full rounded-xl border border-stroke bg-bg px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none"
            >
              {fasi.length ? (
                fasi.map((fase) => (
                  <option key={fase.nome} value={fase.nome}>
                    {fase.nome}
                  </option>
                ))
              ) : (
                <option value="Generale">Generale</option>
              )}
            </select>
          </label>

          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(event) => {
              setFile(event.target.files?.[0] || null);
              event.target.value = "";
            }}
            className="sr-only"
            aria-label="Scatta o scegli foto cantiere"
          />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-brand/40 bg-brand/10 px-4 font-display text-xs uppercase text-brand disabled:opacity-50"
          >
            <Camera className="h-5 w-5" />
            {file ? "Cambia foto" : "Scatta o scegli foto"}
          </button>
          {file && (
            <p className="truncate text-xs text-fog" title={file.name}>
              Selezionata: {file.name}
            </p>
          )}
          <button
            type="button"
            onClick={() => void upload()}
            disabled={!file || busy}
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 font-display text-xs uppercase text-white disabled:opacity-40"
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <UploadCloud className="h-4 w-4" />
            )}
            Comprimi e carica
          </button>
        </div>
      </section>
    </div>
  );
}
