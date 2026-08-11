import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Download,
  FileText,
  Loader2,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";
import {
  downloadCantiereArchive,
  listCantiereArchive,
  uploadCantiereArchive,
} from "@/lib/cantiereArchive";

const ACCEPTED_DOCUMENTS = ".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx";

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function CantiereDocuments({ cantiereId, refreshKey = 0 }) {
  const inputRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [downloadingId, setDownloadingId] = useState(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listCantiereArchive(cantiereId);
      setDocuments(rows);
    } catch (error) {
      toast.error(error.message || "Documenti non disponibili");
    } finally {
      setLoading(false);
    }
  }, [cantiereId]);

  useEffect(() => {
    if (open) loadDocuments();
  }, [loadDocuments, open, refreshKey]);

  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      await uploadCantiereArchive(cantiereId, file);
      await loadDocuments();
      toast.success("Documento salvato nell'archivio privato");
    } catch (error) {
      toast.error(error.message || "Upload non riuscito");
    } finally {
      setUploading(false);
    }
  };

  const download = async (document) => {
    setDownloadingId(document.id);
    try {
      const blob = await downloadCantiereArchive(cantiereId, document.path);
      const signedUrl = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = signedUrl;
      anchor.download = document.displayName;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(signedUrl), 0);
    } catch (error) {
      toast.error(error.message || "Download non riuscito");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <section className="border-t border-stroke pt-4">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 text-left"
      >
        <span className="inline-flex items-center gap-2 font-display uppercase text-xs text-ink">
          <FileText className="w-4 h-4 text-brand" />
          Documenti privati
          {documents.length > 0 && (
            <span className="rounded-full bg-brand/15 px-2 py-0.5 text-[10px] text-brand">
              {documents.length}
            </span>
          )}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-fog transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          <>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED_DOCUMENTS}
              onChange={upload}
              className="sr-only"
              aria-label="Carica documento cantiere"
            />
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 rounded-xl border border-brand/40 bg-brand/10 px-3 py-2 font-display uppercase text-[10px] text-brand hover:bg-brand/15 disabled:opacity-60"
            >
              {uploading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <UploadCloud className="w-4 h-4" />
              )}
              Carica documento
            </button>
            <p className="font-body text-[11px] text-fog">
              PDF, immagini, Word o Excel. Massimo 25 MB. Download con link
              temporaneo di 5 minuti.
            </p>

            {loading ? (
              <div className="inline-flex items-center gap-2 font-body text-xs text-fog">
                <Loader2 className="w-4 h-4 animate-spin" /> Caricamento
                documenti...
              </div>
            ) : documents.length === 0 ? (
              <p className="font-body text-xs text-fog">
                Nessun documento archiviato per questo cantiere.
              </p>
            ) : (
              <ul className="space-y-2">
                {documents.map((document) => (
                  <li
                    key={document.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-stroke bg-bg px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-body text-xs text-ink">
                        {document.displayName}
                      </div>
                      <div className="font-body text-[10px] text-fog">
                        {[
                          formatDate(document.createdAt),
                          formatBytes(document.size),
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => download(document)}
                      disabled={downloadingId === document.id}
                      aria-label={`Scarica ${document.displayName}`}
                      className="shrink-0 rounded-lg border border-stroke p-2 text-fog hover:border-brand hover:text-brand disabled:opacity-60"
                    >
                      {downloadingId === document.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Download className="w-4 h-4" />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        </div>
      )}
    </section>
  );
}
