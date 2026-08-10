import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  ExternalLink,
  Image as ImageIcon,
  Loader2,
  MailPlus,
  Share2,
  UserMinus,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  canUseTenantStorage,
  listCantiereDocuments,
  tenantIdFromUser,
} from "@/lib/storage";

function basename(path) {
  return (
    String(path || "")
      .split("/")
      .pop() || "File cantiere"
  );
}

export default function CantierePortalAccess({ cantiereId }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nome: "", email: "" });
  const tenantId = tenantIdFromUser(user);
  const storageEnabled = canUseTenantStorage(user);
  const queryKey = ["cantiere-portale", cantiereId];
  const portal = useQuery({
    queryKey,
    queryFn: async () =>
      (await client.get(`/cantieri/${cantiereId}/portale`)).data,
    enabled: open,
  });
  const documents = useQuery({
    queryKey: ["cantiere-portale-documenti", cantiereId],
    queryFn: () => listCantiereDocuments({ tenantId, cantiereId }),
    enabled: open && storageEnabled,
  });
  const sharesByPath = useMemo(
    () =>
      new Map(
        (portal.data?.shares || []).map((item) => [item.storage_path, item]),
      ),
    [portal.data?.shares],
  );

  const refresh = () => qc.invalidateQueries({ queryKey });
  const invite = useMutation({
    mutationFn: () =>
      client.post(`/cantieri/${cantiereId}/portale/invita`, form),
    onSuccess: ({ data }) => {
      refresh();
      setForm({ nome: "", email: "" });
      toast.success(
        data.invited
          ? "Invito cliente inviato"
          : "Cliente collegato al cantiere ed email inviata",
      );
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });
  const deactivate = useMutation({
    mutationFn: (userId) =>
      client.patch(
        `/cantieri/${cantiereId}/portale/clienti/${userId}/disattiva`,
      ),
    onSuccess: () => {
      refresh();
      toast.success("Accesso cliente disattivato");
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });
  const share = useMutation({
    mutationFn: (asset) =>
      client.post(`/cantieri/${cantiereId}/portale/condivisioni`, asset),
    onSuccess: () => {
      refresh();
      toast.success("File condiviso nel portale cliente");
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });
  const revoke = useMutation({
    mutationFn: (id) =>
      client.delete(`/cantieri/${cantiereId}/portale/condivisioni/${id}`),
    onSuccess: () => {
      refresh();
      toast.success("Condivisione revocata");
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });

  const toggleAsset = (asset) => {
    const existing = sharesByPath.get(asset.storage_path);
    if (existing) return revoke.mutate(existing.id);
    share.mutate(asset);
  };

  return (
    <section className="border-t border-stroke pt-4">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-3 text-left"
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-2 font-display text-xs uppercase text-ink">
          <ExternalLink className="h-4 w-4 text-brand" /> Portale cliente
        </span>
        <ChevronDown
          className={`h-4 w-4 text-fog transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="mt-4 space-y-5 rounded-2xl border border-stroke bg-bg p-4">
          {portal.isLoading ? (
            <div className="inline-flex items-center gap-2 font-body text-xs text-fog">
              <Loader2 className="h-4 w-4 animate-spin" /> Caricamento portale…
            </div>
          ) : portal.isError ? (
            <div className="font-body text-xs text-red-400">
              Configurazione portale non disponibile
              {portal.error?.response?.data?.detail
                ? `: ${formatApiErrorDetail(portal.error.response.data.detail)}`
                : "."}
            </div>
          ) : (
            <>
              {user?.role === "owner" || user?.role === "admin" ? (
                <div className="space-y-3">
                  <div className="font-display text-[10px] uppercase tracking-wider text-fog">
                    Invita cliente
                  </div>
                  <div className="grid gap-2 sm:grid-cols-[1fr_1.4fr_auto]">
                    <input
                      value={form.nome}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          nome: event.target.value,
                        }))
                      }
                      placeholder="Nome cliente"
                      className="rounded-xl border border-stroke bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none"
                    />
                    <input
                      type="email"
                      value={form.email}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          email: event.target.value,
                        }))
                      }
                      placeholder="email@cliente.it"
                      className="rounded-xl border border-stroke bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none"
                    />
                    <button
                      type="button"
                      disabled={!form.email || invite.isPending}
                      onClick={() => invite.mutate()}
                      className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2 font-display text-[10px] uppercase text-white disabled:opacity-50"
                    >
                      {invite.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <MailPlus className="h-4 w-4" />
                      )}{" "}
                      Invita
                    </button>
                  </div>
                </div>
              ) : null}

              {(portal.data?.clients || []).length > 0 && (
                <div className="space-y-2">
                  {(portal.data.clients || []).map((item) => (
                    <div
                      key={item.user_id}
                      className="flex items-center justify-between gap-3 rounded-xl border border-stroke bg-surface px-3 py-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate font-body text-xs text-ink">
                          {item.nome || item.email || "Cliente"}
                        </div>
                        <div className="truncate font-body text-[10px] text-fog">
                          {item.email || item.user_id}
                        </div>
                      </div>
                      {item.attivo ? (
                        <button
                          type="button"
                          onClick={() => deactivate.mutate(item.user_id)}
                          disabled={
                            deactivate.isPending ||
                            !(user?.role === "owner" || user?.role === "admin")
                          }
                          className="rounded-lg border border-stroke p-2 text-fog hover:border-red-400 hover:text-red-400 disabled:opacity-40"
                          aria-label="Disattiva accesso cliente"
                        >
                          <UserMinus className="h-4 w-4" />
                        </button>
                      ) : (
                        <span className="font-display text-[9px] uppercase text-fog">
                          Disattivato
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-3 border-t border-stroke pt-4">
                <div className="font-display text-[10px] uppercase tracking-wider text-fog">
                  Asset visibili al cliente
                </div>
                {(documents.data || []).map((document) => {
                  const shared = sharesByPath.has(document.path);
                  return (
                    <button
                      key={document.path}
                      type="button"
                      onClick={() =>
                        toggleAsset({
                          tipo: "documento",
                          bucket: "documenti",
                          storage_path: document.path,
                          titolo: document.displayName,
                        })
                      }
                      className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left ${shared ? "border-emerald-500/30 bg-emerald-500/10" : "border-stroke bg-surface"}`}
                    >
                      {shared ? (
                        <Check className="h-4 w-4 text-emerald-400" />
                      ) : (
                        <Share2 className="h-4 w-4 text-fog" />
                      )}
                      <span className="min-w-0 flex-1 truncate font-body text-xs text-ink">
                        {document.displayName}
                      </span>
                      <span className="font-display text-[9px] uppercase text-fog">
                        {shared ? "Condiviso" : "Condividi"}
                      </span>
                    </button>
                  );
                })}
                {(portal.data?.photo_candidates || []).map((path) => {
                  const shared = sharesByPath.has(path);
                  return (
                    <button
                      key={path}
                      type="button"
                      onClick={() =>
                        toggleAsset({
                          tipo: "foto",
                          bucket: "foto-cantiere",
                          storage_path: path,
                          titolo: basename(path),
                        })
                      }
                      className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left ${shared ? "border-emerald-500/30 bg-emerald-500/10" : "border-stroke bg-surface"}`}
                    >
                      <ImageIcon
                        className={`h-4 w-4 ${shared ? "text-emerald-400" : "text-fog"}`}
                      />
                      <span className="min-w-0 flex-1 truncate font-body text-xs text-ink">
                        {basename(path)}
                      </span>
                      <span className="font-display text-[9px] uppercase text-fog">
                        {shared ? "Condivisa" : "Condividi"}
                      </span>
                    </button>
                  );
                })}
                {!documents.isLoading &&
                  !(documents.data || []).length &&
                  !(portal.data?.photo_candidates || []).length && (
                    <p className="font-body text-xs text-fog">
                      Carica documenti o fotografie nel cantiere per poterli
                      condividere.
                    </p>
                  )}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
