import { useCallback, useEffect, useRef, useState } from "react";
import { CloudOff, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";
import {
  listOfflineOperations,
  OFFLINE_QUEUE_EVENT,
  syncOfflineOperations,
} from "@/lib/offlineStore";

export default function OfflineSyncStatus() {
  const { user } = useAuth();
  const { slug } = useTenant();
  const qc = useQueryClient();
  const [online, setOnline] = useState(() => navigator.onLine);
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const syncingRef = useRef(false);
  const userId = user?.id || user?.email;

  const refresh = useCallback(async () => {
    if (!userId) return setPending(0);
    const operations = await listOfflineOperations(slug, userId);
    setPending(operations.length);
    return operations.length;
  }, [slug, userId]);

  const flush = useCallback(
    async (announce = false) => {
      if (!navigator.onLine || !userId || syncingRef.current) return;
      const count = await refresh();
      if (!count) return;
      syncingRef.current = true;
      setSyncing(true);
      try {
        const result = await syncOfflineOperations(slug, userId);
        await refresh();
        if (result.synced) {
          void qc.invalidateQueries();
          if (announce) {
            toast.success(
              `${result.synced} ${
                result.synced === 1
                  ? "salvataggio sincronizzato"
                  : "salvataggi sincronizzati"
              }`,
            );
          }
        }
        if (result.failures.length && announce) {
          toast.error("Alcuni salvataggi attendono ancora la sincronizzazione");
        }
      } finally {
        syncingRef.current = false;
        setSyncing(false);
      }
    },
    [qc, refresh, slug, userId],
  );

  useEffect(() => {
    navigator.storage?.persist?.().catch(() => undefined);
    void refresh();
    const handleOnline = () => {
      setOnline(true);
      void flush(true);
    };
    const handleOffline = () => setOnline(false);
    const handleQueue = () => void refresh();
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    window.addEventListener(OFFLINE_QUEUE_EVENT, handleQueue);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener(OFFLINE_QUEUE_EVENT, handleQueue);
    };
  }, [flush, refresh]);

  useEffect(() => {
    if (online) void flush(false);
  }, [flush, online]);

  if (online && !pending && !syncing) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`border-b px-3 py-2 text-xs sm:px-6 ${
        online
          ? "border-brand/30 bg-brand/10 text-brand"
          : "border-warning/30 bg-warning/10 text-warning"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
        <span className="inline-flex min-w-0 items-center gap-2">
          {syncing ? (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
          ) : (
            <CloudOff className="h-4 w-4 shrink-0" />
          )}
          <span>
            {!online
              ? `Modalita offline: i dati vengono conservati su questo dispositivo${
                  pending ? ` (${pending} in attesa)` : ""
                }.`
              : `Sincronizzazione in attesa: ${pending} salvataggi.`}
          </span>
        </span>
        {online && pending > 0 && (
          <button
            type="button"
            onClick={() => void flush(true)}
            disabled={syncing}
            className="inline-flex min-h-9 shrink-0 items-center gap-1 rounded-lg border border-brand/40 px-3 font-display text-[10px] uppercase disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`}
            />
            Sincronizza
          </button>
        )}
      </div>
    </div>
  );
}
