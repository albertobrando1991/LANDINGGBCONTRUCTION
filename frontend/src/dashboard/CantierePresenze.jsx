import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  Clock3,
  Loader2,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";
import client, { extractErrorDetail } from "@/lib/api";
import {
  loadWithOfflineCache,
  putOfflineCache,
  removeOfflineOperation,
  runOrQueueJson,
} from "@/lib/offlineStore";
import {
  assegnazioneMatchesCantiere,
  isAssegnazioneAttiva,
} from "@/lib/personale";

const fieldClass =
  "w-full rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-brand";

function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function summarizePresenze(current, righe, data) {
  return {
    ...(current || {}),
    data,
    righe,
    totale_unita: righe.reduce(
      (sum, item) => sum + Number(item.unita_presenti || 0),
      0,
    ),
    totale_interni: righe
      .filter((item) => item.personale_tipo === "interno")
      .reduce((sum, item) => sum + Number(item.unita_presenti || 0), 0),
    totale_subappaltatori: righe
      .filter((item) => item.personale_tipo === "subappaltatore")
      .reduce((sum, item) => sum + Number(item.unita_presenti || 0), 0),
  };
}

export default function CantierePresenze({
  cantiere,
  personale = [],
  assegnazioni = [],
  standalone = false,
}) {
  const qc = useQueryClient();
  const { user } = useAuth() || {};
  const { slug } = useTenant();
  const userId = user?.id || user?.email;
  const [open, setOpen] = useState(standalone);
  const [data, setData] = useState(today);
  const [form, setForm] = useState({
    personale_id: "",
    unita_presenti: 1,
    tipo_giornata: "intera",
    ore_lavorate: 8,
    note: "",
  });
  const queryKey = ["presenze-cantiere", cantiere.id, data];
  const presenze = useQuery({
    queryKey,
    queryFn: () =>
      loadWithOfflineCache({
        tenantSlug: slug,
        userId,
        cacheKey: `presenze:${cantiere.id}:${data}`,
        load: async () =>
          (
            await client.get(`/cantieri/${cantiere.id}/presenze`, {
              params: { data },
            })
          ).data,
      }),
    enabled: standalone || open,
  });
  const candidates = useMemo(() => {
    const assigned = new Set(
      assegnazioni
        .filter(
          (item) =>
            assegnazioneMatchesCantiere(item, cantiere.id) &&
            isAssegnazioneAttiva(item, data),
        )
        .map((item) => item.personale_id),
    );
    const active = personale.filter((item) => item.attivo);
    return assigned.size
      ? [
          ...active.filter((item) => assigned.has(item.id)),
          ...active.filter((item) => !assigned.has(item.id)),
        ]
      : active;
  }, [assegnazioni, cantiere.id, data, personale]);

  const persistCachedRows = (righe) => {
    const current = qc.getQueryData(queryKey) || { data, righe: [] };
    const next = summarizePresenze(current, righe, data);
    qc.setQueryData(queryKey, next);
    void putOfflineCache(slug, userId, `presenze:${cantiere.id}:${data}`, next);
  };

  const create = useMutation({
    mutationFn: async () => {
      const body = {
        ...form,
        data,
        unita_presenti: Number(form.unita_presenti),
        ore_lavorate: Number(form.ore_lavorate),
        note: form.note || null,
      };
      const result = await runOrQueueJson({
        tenantSlug: slug,
        userId,
        method: "post",
        url: `/cantieri/${cantiere.id}/presenze`,
        data: body,
        label: "Presenza cantiere",
        coalesceKey: `presenza:${cantiere.id}:${body.personale_id}:${data}`,
        clientId: true,
      });
      if (!result.queued) return result.data;
      const person = candidates.find((item) => item.id === body.personale_id);
      return {
        id: `offline:${result.operation.id}`,
        ...body,
        personale_nome: person?.nome || "Presenza in attesa",
        personale_tipo: person?.tipo,
        _offline_pending: true,
        _offline_operation: result.operation,
        _offline_presence_key: `${cantiere.id}:${body.personale_id}:${data}`,
      };
    },
    onSuccess: (saved) => {
      const current = qc.getQueryData(queryKey) || { data, righe: [] };
      const savedKey = saved?._offline_presence_key;
      persistCachedRows([
        ...(current.righe || []).filter((item) => {
          if (String(item.id) === String(saved.id)) return false;
          if (savedKey && item._offline_presence_key === savedKey) return false;
          return !(
            String(item.personale_id) === String(saved.personale_id) &&
            String(item.data || data) === String(saved.data || data)
          );
        }),
        saved,
      ]);
      if (!saved?._offline_pending) {
        void qc.invalidateQueries({ queryKey });
        void qc.invalidateQueries({ queryKey: ["presenze-personale"] });
      }
      setForm((current) => ({ ...current, personale_id: "", note: "" }));
      toast.success(
        saved?._offline_pending
          ? "Presenza salvata offline"
          : "Presenza registrata",
      );
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });
  const remove = useMutation({
    mutationFn: async (item) => {
      if (item?._offline_operation) {
        await removeOfflineOperation(item._offline_operation);
        return { removedId: item.id, queued: true };
      }
      const result = await runOrQueueJson({
        tenantSlug: slug,
        userId,
        method: "delete",
        url: `/personale/presenze/${item.id}`,
        label: "Rimozione presenza",
        coalesceKey: `presenza-delete:${item.id}`,
        ignoreStatuses: [404],
      });
      return { removedId: item.id, queued: result.queued };
    },
    onSuccess: ({ removedId, queued }) => {
      const current = qc.getQueryData(queryKey);
      if (current) {
        persistCachedRows(
          (current.righe || []).filter(
            (item) => String(item.id) !== String(removedId),
          ),
        );
      }
      if (!queued) {
        void qc.invalidateQueries({ queryKey });
        void qc.invalidateQueries({ queryKey: ["presenze-personale"] });
      }
      toast.success(queued ? "Rimozione salvata offline" : "Presenza rimossa");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });

  const setTipo = (tipo_giornata) =>
    setForm((current) => ({
      ...current,
      tipo_giornata,
      ore_lavorate:
        tipo_giornata === "intera"
          ? 8
          : tipo_giornata === "mezza"
            ? 4
            : current.ore_lavorate,
    }));

  return (
    <section
      className={
        standalone
          ? "rounded-2xl border border-stroke bg-surface p-5"
          : "border-t border-stroke pt-4"
      }
    >
      {standalone ? (
        <header>
          <p className="inline-flex items-center gap-2 font-display text-sm uppercase text-ink">
            <Users className="h-5 w-5 text-brand" /> Presenze giornaliere
          </p>
          <p className="mt-1 text-xs text-fog">
            Registra persone o squadre presenti senza appesantire la panoramica
            del cantiere.
          </p>
        </header>
      ) : (
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <span className="inline-flex items-center gap-2 font-display text-xs uppercase text-ink">
            <Users className="h-4 w-4 text-brand" /> Presenze giornaliere
            {presenze.data?.totale_unita > 0 && (
              <span className="rounded-full bg-brand/15 px-2 py-0.5 text-[10px] text-brand">
                {presenze.data.totale_unita}
              </span>
            )}
          </span>
          <ChevronDown
            className={`h-4 w-4 text-fog transition ${open ? "rotate-180" : ""}`}
          />
        </button>
      )}
      {(standalone || open) && (
        <div
          className={`mt-4 space-y-4 ${
            standalone ? "" : "rounded-2xl border border-stroke bg-bg p-4"
          }`}
        >
          <input
            type="date"
            value={data}
            onChange={(event) => setData(event.target.value)}
            className={fieldClass}
            aria-label="Data presenze cantiere"
          />
          {standalone && presenze.data && (
            <div className="grid grid-cols-3 gap-2">
              <PresenzaMetric
                label="Totale"
                value={presenze.data.totale_unita || 0}
              />
              <PresenzaMetric
                label="Interni"
                value={presenze.data.totale_interni || 0}
              />
              <PresenzaMetric
                label="Subappalto"
                value={presenze.data.totale_subappaltatori || 0}
              />
            </div>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            <select
              value={form.personale_id}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  personale_id: event.target.value,
                }))
              }
              className={fieldClass}
              aria-label="Persona o squadra presente"
            >
              <option value="">Persona o squadra</option>
              {candidates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nome} ·{" "}
                  {item.tipo === "interno" ? "interno" : "subappalto"}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              max="999"
              value={form.unita_presenti}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  unita_presenti: event.target.value,
                }))
              }
              className={fieldClass}
              aria-label="Numero persone presenti"
            />
            <select
              value={form.tipo_giornata}
              onChange={(event) => setTipo(event.target.value)}
              className={fieldClass}
              aria-label="Tipo giornata"
            >
              <option value="intera">Giornata intera</option>
              <option value="mezza">Mezza giornata</option>
              <option value="ore">A ore</option>
            </select>
            <input
              type="number"
              min="0.25"
              max="24"
              step="0.25"
              value={form.ore_lavorate}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  ore_lavorate: event.target.value,
                }))
              }
              className={fieldClass}
              aria-label="Ore lavorate"
            />
          </div>
          {!candidates.length && (
            <p className="rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
              Nessuna persona attiva disponibile. Aggiungila nella sezione
              Personale prima di registrare una presenza.
            </p>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={form.note}
              onChange={(event) =>
                setForm((current) => ({ ...current, note: event.target.value }))
              }
              placeholder="Note facoltative"
              className={fieldClass}
            />
            <button
              type="button"
              disabled={!form.personale_id || create.isPending}
              onClick={() => create.mutate()}
              className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl bg-brand px-4 font-display text-[10px] uppercase text-white disabled:opacity-40"
            >
              {create.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Registra
            </button>
          </div>
          {presenze.isLoading ? (
            <p className="text-xs text-fog">Caricamento presenze...</p>
          ) : presenze.isError ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
              <span>Impossibile caricare le presenze della giornata.</span>
              <button
                type="button"
                onClick={() => presenze.refetch()}
                className="min-h-10 rounded-lg border border-red-400/40 px-3 font-display text-[10px] uppercase"
              >
                Riprova
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {(presenze.data?.righe || []).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-stroke bg-surface px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-xs text-ink">
                      {item.personale_nome}
                    </p>
                    <p className="mt-1 inline-flex items-center gap-1 text-[10px] text-fog">
                      <Clock3 className="h-3 w-3" /> {item.unita_presenti}{" "}
                      presenti · {Number(item.ore_lavorate || 0)} ore
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => remove.mutate(item)}
                    disabled={remove.isPending}
                    aria-label={`Rimuovi presenza ${item.personale_nome}`}
                    className="rounded-lg border border-stroke p-2 text-fog hover:border-red-400 hover:text-red-400"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  {item._offline_pending && (
                    <span className="shrink-0 rounded-full border border-warning/30 bg-warning/10 px-2 py-1 text-[9px] uppercase text-warning">
                      Offline
                    </span>
                  )}
                </div>
              ))}
              {!presenze.data?.righe?.length && (
                <p className="text-xs text-fog">
                  Nessuna presenza registrata per questa data.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function PresenzaMetric({ label, value }) {
  return (
    <div className="rounded-xl border border-stroke bg-bg px-3 py-2.5 text-center">
      <p className="font-display text-[9px] uppercase text-fog">{label}</p>
      <p className="mt-1 font-display text-lg text-ink">{value}</p>
    </div>
  );
}
