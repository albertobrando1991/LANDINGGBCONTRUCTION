import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";
import { extractErrorDetail } from "@/lib/api";
import { putOfflineCache, runOrQueueJson } from "@/lib/offlineStore";

const inputClass =
  "mt-1 w-full rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-brand";

function todayValue() {
  return new Date().toISOString().slice(0, 10);
}

export default function PersonaleAssignmentEditor({
  cantieri = [],
  personale = [],
  initialCantiereId = "",
  initialPersonaleId = "",
  assignment = null,
  onClose,
  onSaved,
}) {
  const qc = useQueryClient();
  const { user } = useAuth() || {};
  const { slug } = useTenant();
  const userId = user?.id || user?.email;
  const editing = Boolean(assignment?.id);
  const [form, setForm] = useState(() => ({
    cantiere_id:
      assignment?.cantiere_legacy_id ||
      assignment?.cantiere_id ||
      initialCantiereId ||
      "",
    personale_id: assignment?.personale_id || initialPersonaleId || "",
    ruolo_in_cantiere: assignment?.ruolo_in_cantiere || "",
    data_da: assignment?.data_da || todayValue(),
    data_a: assignment?.data_a || "",
    stato: assignment?.stato || "assegnato",
    note: assignment?.note || "",
  }));

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        personale_id: form.personale_id,
        ruolo_in_cantiere: form.ruolo_in_cantiere || null,
        data_da: form.data_da,
        data_a: form.data_a || null,
        stato: form.stato,
        note: form.note || null,
      };
      if (editing) {
        delete body.personale_id;
        const result = await runOrQueueJson({
          tenantSlug: slug,
          userId,
          method: "patch",
          url: `/personale/assegnazioni/${assignment.id}`,
          data: body,
          label: "Aggiornamento squadra cantiere",
          coalesceKey: `assegnazione:${assignment.id}`,
        });
        return result.queued
          ? { ...assignment, ...body, _offline_pending: true }
          : result.data;
      }
      const result = await runOrQueueJson({
        tenantSlug: slug,
        userId,
        method: "post",
        url: `/cantieri/${form.cantiere_id}/personale`,
        data: body,
        label: "Assegnazione squadra cantiere",
        coalesceKey: `assegnazione-nuova:${form.cantiere_id}:${form.personale_id}:${form.data_da}`,
        clientId: true,
      });
      if (!result.queued) return result.data;
      const person = personale.find((item) => item.id === form.personale_id);
      const site = cantieri.find(
        (item) =>
          String(item.id || item.cantiere_id) === String(form.cantiere_id),
      );
      return {
        id: `offline:${result.operation.id}`,
        ...body,
        cantiere_legacy_id: form.cantiere_id,
        cantiere_id: form.cantiere_id,
        cantiere_cliente: site?.cliente || site?.nome,
        personale_id: form.personale_id,
        personale_nome: person?.nome,
        personale_tipo: person?.tipo,
        _offline_pending: true,
        _offline_assignment_key: `${form.cantiere_id}:${form.personale_id}:${form.data_da}`,
      };
    },
    onSuccess: (saved) => {
      const current = qc.getQueryData(["personale-assegnazioni"]) || [];
      const next = editing
        ? current.map((item) =>
            item.id === saved.id ? { ...item, ...saved } : item,
          )
        : [
            ...current.filter(
              (item) =>
                String(item.id) !== String(saved.id) &&
                item._offline_assignment_key !== saved._offline_assignment_key,
            ),
            saved,
          ];
      qc.setQueryData(["personale-assegnazioni"], next);
      void putOfflineCache(slug, userId, "personale-assegnazioni", next);
      if (!saved?._offline_pending) {
        void qc.invalidateQueries({ queryKey: ["personale-assegnazioni"] });
      }
      toast.success(
        saved?._offline_pending
          ? "Assegnazione salvata offline"
          : editing
            ? "Assegnazione aggiornata"
            : "Persona assegnata",
      );
      onSaved?.(saved);
      onClose?.();
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });

  const setField = (field, value) =>
    setForm((current) => ({ ...current, [field]: value }));

  const submit = (event) => {
    event.preventDefault();
    if (!form.cantiere_id || !form.personale_id) {
      toast.error("Seleziona cantiere e persona");
      return;
    }
    save.mutate();
  };

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="assignment-editor-title"
    >
      <section className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-3xl border border-stroke bg-surface p-5 shadow-2xl sm:rounded-3xl">
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
              Squadra cantiere
            </p>
            <h2
              id="assignment-editor-title"
              className="mt-1 font-display text-xl uppercase text-ink"
            >
              {editing ? "Modifica assegnazione" : "Nuova assegnazione"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Chiudi editor assegnazione"
            className="min-h-11 min-w-11 rounded-full border border-stroke text-fog"
          >
            <X className="mx-auto h-5 w-5" />
          </button>
        </header>

        <form onSubmit={submit} className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2">
            <span className="font-display text-[10px] uppercase text-fog">
              Cantiere
            </span>
            <select
              value={form.cantiere_id}
              disabled={editing}
              required
              onChange={(event) => setField("cantiere_id", event.target.value)}
              className={inputClass}
            >
              <option value="">Seleziona cantiere</option>
              {cantieri.map((item) => (
                <option
                  key={item.id || item.cantiere_id}
                  value={item.id || item.cantiere_id}
                >
                  {item.cliente || item.nome || "Cantiere"}
                </option>
              ))}
              {editing &&
                !cantieri.some(
                  (item) =>
                    String(item.id || item.cantiere_id) ===
                    String(form.cantiere_id),
                ) && (
                  <option value={form.cantiere_id}>
                    {assignment?.cantiere_cliente || "Cantiere assegnato"}
                  </option>
                )}
            </select>
          </label>

          <label className="sm:col-span-2">
            <span className="font-display text-[10px] uppercase text-fog">
              Persona o squadra
            </span>
            <select
              value={form.personale_id}
              disabled={editing}
              required
              onChange={(event) => setField("personale_id", event.target.value)}
              className={inputClass}
            >
              <option value="">Seleziona persona</option>
              {personale
                .filter((item) => item.attivo || item.id === form.personale_id)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nome} ·{" "}
                    {item.tipo === "interno" ? "interno" : "subappalto"}
                  </option>
                ))}
            </select>
          </label>

          <label className="sm:col-span-2">
            <span className="font-display text-[10px] uppercase text-fog">
              Ruolo nel cantiere
            </span>
            <input
              value={form.ruolo_in_cantiere}
              onChange={(event) =>
                setField("ruolo_in_cantiere", event.target.value)
              }
              placeholder="Muratore, elettricista, impresa edile..."
              className={inputClass}
            />
          </label>

          <label>
            <span className="font-display text-[10px] uppercase text-fog">
              Dal
            </span>
            <input
              type="date"
              required
              value={form.data_da}
              onChange={(event) => setField("data_da", event.target.value)}
              className={inputClass}
            />
          </label>
          <label>
            <span className="font-display text-[10px] uppercase text-fog">
              Al
            </span>
            <input
              type="date"
              min={form.data_da}
              value={form.data_a}
              onChange={(event) => setField("data_a", event.target.value)}
              className={inputClass}
            />
          </label>
          <label className="sm:col-span-2">
            <span className="font-display text-[10px] uppercase text-fog">
              Stato
            </span>
            <select
              value={form.stato}
              onChange={(event) => setField("stato", event.target.value)}
              className={inputClass}
            >
              <option value="assegnato">Assegnato</option>
              <option value="in_corso">In cantiere</option>
              <option value="concluso">Concluso</option>
            </select>
          </label>
          <label className="sm:col-span-2">
            <span className="font-display text-[10px] uppercase text-fog">
              Note
            </span>
            <textarea
              rows={2}
              value={form.note}
              onChange={(event) => setField("note", event.target.value)}
              className={inputClass}
            />
          </label>
          <div className="sm:col-span-2 flex justify-end">
            <button
              type="submit"
              disabled={save.isPending}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-5 font-display text-xs uppercase text-white disabled:opacity-50"
            >
              {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Salva assegnazione
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
