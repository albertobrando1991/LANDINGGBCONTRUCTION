import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  Loader2,
  MessageCircle,
  Phone,
  Plus,
  UserRoundCog,
  X,
} from "lucide-react";
import { toast } from "sonner";
import client, { extractErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  assegnazioneMatchesCantiere,
  filterPersonale,
  formatRuoloLabel,
  isAssegnazioneAttiva,
} from "@/lib/personale";
import { buildWhatsappUrl, normalizeWhatsappPhone } from "@/lib/whatsapp";
import PersonaleAssignmentEditor from "@/dashboard/PersonaleAssignmentEditor";

const inputClass =
  "mt-1 w-full rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-brand";

function currency(value) {
  return Number(value || 0).toLocaleString("it-IT", {
    style: "currency",
    currency: "EUR",
  });
}

function PersonaleForm({ fornitori, pending, onClose, onSubmit }) {
  return (
    <section className="rounded-2xl border border-brand/40 bg-surface p-5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
            Anagrafica operativa
          </p>
          <h2 className="mt-1 font-display text-xl uppercase text-ink">
            Nuova persona o squadra
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Chiudi modulo personale"
          className="min-h-11 min-w-11 rounded-full border border-stroke text-fog"
        >
          <X className="mx-auto h-5 w-5" />
        </button>
      </header>
      <form onSubmit={onSubmit} className="mt-5 grid gap-4 md:grid-cols-2">
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Tipo
          </span>
          <select name="tipo" className={inputClass}>
            <option value="interno">Interno</option>
            <option value="subappaltatore">Subappaltatore</option>
          </select>
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Nome
          </span>
          <input name="nome" required minLength={2} className={inputClass} />
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Ruolo
          </span>
          <input
            name="ruolo"
            placeholder="Muratore, impresa..."
            className={inputClass}
          />
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Fornitore collegato
          </span>
          <select name="fornitore_id" className={inputClass}>
            <option value="">Nessun collegamento</option>
            {fornitori
              .filter((item) => item.attivo)
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.ragione_sociale}
                </option>
              ))}
          </select>
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Telefono
          </span>
          <input name="telefono" inputMode="tel" className={inputClass} />
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Email
          </span>
          <input name="email" type="email" className={inputClass} />
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Costo giornaliero
          </span>
          <input
            name="costo_giornaliero"
            type="number"
            min="0"
            step="0.01"
            className={inputClass}
          />
        </label>
        <label>
          <span className="font-display text-[10px] uppercase text-fog">
            Costo orario
          </span>
          <input
            name="costo_orario"
            type="number"
            min="0"
            step="0.01"
            className={inputClass}
          />
        </label>
        <label className="md:col-span-2">
          <span className="font-display text-[10px] uppercase text-fog">
            Note
          </span>
          <textarea name="note" rows={2} className={inputClass} />
        </label>
        <div className="md:col-span-2 flex justify-end">
          <button
            type="submit"
            disabled={pending}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-5 font-display text-xs uppercase text-white disabled:opacity-50"
          >
            {pending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Salva anagrafica
          </button>
        </div>
      </form>
    </section>
  );
}

export default function Personale() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const canManage = ["owner", "admin"].includes(user?.role);
  const [tipo, setTipo] = useState("");
  const [cantiereId, setCantiereId] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [assignmentEditor, setAssignmentEditor] = useState(null);

  const personaleQuery = useQuery({
    queryKey: ["personale"],
    queryFn: async () => (await client.get("/personale")).data,
  });
  const assignmentsQuery = useQuery({
    queryKey: ["personale-assegnazioni"],
    queryFn: async () => (await client.get("/personale/assegnazioni")).data,
  });
  const cantieriQuery = useQuery({
    queryKey: ["cantieri", "personale"],
    queryFn: async () =>
      (await client.get("/cantieri", { params: { stato: "tutti" } })).data,
  });
  const economicsQuery = useQuery({
    queryKey: ["economics", "personale-fornitori"],
    queryFn: async () => (await client.get("/economics")).data,
    enabled: canManage,
  });

  const create = useMutation({
    mutationFn: async (body) => (await client.post("/personale", body)).data,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["personale"] });
      setShowForm(false);
      toast.success("Anagrafica personale creata");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });
  const update = useMutation({
    mutationFn: async ({ id, body }) =>
      (await client.patch(`/personale/${id}`, body)).data,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["personale"] });
      toast.success("Anagrafica aggiornata");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });

  const assignments = useMemo(
    () => assignmentsQuery.data || [],
    [assignmentsQuery.data],
  );
  const visible = useMemo(() => {
    const filtered = filterPersonale(personaleQuery.data || [], {
      tipo,
      attivo: showInactive ? null : true,
    });
    if (!cantiereId) return filtered;
    const assignedIds = new Set(
      assignments
        .filter(
          (item) =>
            assegnazioneMatchesCantiere(item, cantiereId) &&
            isAssegnazioneAttiva(item),
        )
        .map((item) => item.personale_id),
    );
    return filtered.filter((item) => assignedIds.has(item.id));
  }, [assignments, cantiereId, personaleQuery.data, showInactive, tipo]);

  const submitPersonale = (event) => {
    event.preventDefault();
    const raw = Object.fromEntries(new FormData(event.currentTarget));
    const body = Object.fromEntries(
      Object.entries(raw).map(([key, value]) => [
        key,
        value === "" ? null : value,
      ]),
    );
    for (const field of ["costo_giornaliero", "costo_orario"]) {
      if (body[field] !== null) body[field] = Number(body[field]);
    }
    create.mutate(body);
  };

  const loading =
    personaleQuery.isLoading ||
    assignmentsQuery.isLoading ||
    cantieriQuery.isLoading;
  const failed =
    personaleQuery.isError || assignmentsQuery.isError || cantieriQuery.isError;

  if (loading) {
    return (
      <div className="py-16 text-center font-display uppercase tracking-widest text-fog">
        Caricamento personale...
      </div>
    );
  }
  if (failed) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 text-red-300">
        Impossibile caricare il personale e le assegnazioni.
      </div>
    );
  }

  const cantieri = cantieriQuery.data || [];
  const personale = personaleQuery.data || [];

  return (
    <div className="space-y-6" data-testid="personale-page">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[10px] uppercase tracking-[0.24em] text-brand">
            Gestione da remoto
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold uppercase text-ink">
            Personale e squadre
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-fog">
            Chi lavora dove, contatti rapidi e assegnazioni aggiornate per ogni
            cantiere.
          </p>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-4 font-display text-xs uppercase text-white"
          >
            <Plus className="h-4 w-4" /> Nuova anagrafica
          </button>
        )}
      </header>

      <section className="grid gap-3 rounded-2xl border border-stroke bg-surface p-4 md:grid-cols-3">
        <select
          aria-label="Filtra personale per tipo"
          value={tipo}
          onChange={(event) => setTipo(event.target.value)}
          className={inputClass}
        >
          <option value="">Interni e subappaltatori</option>
          <option value="interno">Solo interni</option>
          <option value="subappaltatore">Solo subappaltatori</option>
        </select>
        <select
          aria-label="Filtra personale per cantiere"
          value={cantiereId}
          onChange={(event) => setCantiereId(event.target.value)}
          className={inputClass}
        >
          <option value="">Tutti i cantieri</option>
          {cantieri.map((item) => (
            <option key={item.id} value={item.id}>
              {item.cliente}
            </option>
          ))}
        </select>
        <button
          type="button"
          aria-pressed={showInactive}
          onClick={() => setShowInactive((current) => !current)}
          className={`mt-1 min-h-11 rounded-xl border px-3 font-display text-[10px] uppercase ${showInactive ? "border-brand bg-brand/10 text-brand" : "border-stroke text-fog"}`}
        >
          {showInactive ? "Nascondi inattivi" : "Mostra inattivi"}
        </button>
      </section>

      {showForm && (
        <PersonaleForm
          fornitori={economicsQuery.data?.fornitori || []}
          pending={create.isPending}
          onClose={() => setShowForm(false)}
          onSubmit={submitPersonale}
        />
      )}

      <section className="grid gap-3 lg:grid-cols-2">
        {visible.map((item) => {
          const activeAssignments = assignments.filter(
            (assignment) =>
              assignment.personale_id === item.id &&
              isAssegnazioneAttiva(assignment),
          );
          const whatsapp = buildWhatsappUrl(item.telefono, item.nome);
          const phone = normalizeWhatsappPhone(item.telefono);
          return (
            <article
              key={item.id}
              className="rounded-2xl border border-stroke bg-surface p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-display uppercase text-ink">
                    {item.tipo === "interno" ? (
                      <UserRoundCog className="h-4 w-4 text-brand" />
                    ) : (
                      <BriefcaseBusiness className="h-4 w-4 text-brand" />
                    )}
                    <span className="truncate">{item.nome}</span>
                  </p>
                  <p className="mt-1 text-xs text-fog">
                    {formatRuoloLabel(item.tipo, item.ruolo)}
                    {item.fornitore ? ` · ${item.fornitore}` : ""}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2 py-1 text-[9px] uppercase ${item.attivo ? "border-emerald-500/30 text-emerald-300" : "border-stroke text-fog"}`}
                >
                  {item.attivo ? "Attivo" : "Inattivo"}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {phone && (
                  <a
                    href={`tel:+${phone}`}
                    className="inline-flex min-h-10 items-center gap-1 rounded-lg border border-stroke px-3 text-[10px] uppercase text-ink"
                  >
                    <Phone className="h-3.5 w-3.5" /> Chiama
                  </a>
                )}
                {whatsapp && (
                  <a
                    href={whatsapp}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-10 items-center gap-1 rounded-lg border border-emerald-500/30 px-3 text-[10px] uppercase text-emerald-300"
                  >
                    <MessageCircle className="h-3.5 w-3.5" /> WhatsApp
                  </a>
                )}
                {canManage && (
                  <button
                    type="button"
                    onClick={() =>
                      setAssignmentEditor({ personaleId: item.id })
                    }
                    className="min-h-10 rounded-lg border border-brand/30 px-3 text-[10px] uppercase text-brand"
                  >
                    Assegna a cantiere
                  </button>
                )}
              </div>

              <div className="mt-4 space-y-2 border-t border-stroke pt-3">
                {activeAssignments.map((assignment) => (
                  <button
                    key={assignment.id}
                    type="button"
                    disabled={!canManage}
                    onClick={() =>
                      canManage && setAssignmentEditor({ assignment })
                    }
                    className="flex w-full items-center justify-between gap-3 rounded-xl bg-bg px-3 py-2 text-left disabled:cursor-default"
                  >
                    <span className="min-w-0 truncate text-xs text-ink">
                      {assignment.cantiere_cliente || "Cantiere"}
                    </span>
                    <span className="shrink-0 text-[9px] uppercase text-brand">
                      {assignment.stato === "in_corso"
                        ? "In cantiere"
                        : "Assegnato"}
                    </span>
                  </button>
                ))}
                {!activeAssignments.length && (
                  <p className="text-xs text-fog">Nessun cantiere attivo.</p>
                )}
              </div>

              {canManage && (
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-stroke pt-3">
                  <div
                    data-testid={`personale-costs-${item.id}`}
                    className="text-[10px] text-fog"
                  >
                    Giorno: {currency(item.costo_giornaliero)} · Ora:{" "}
                    {currency(item.costo_orario)}
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      update.mutate({
                        id: item.id,
                        body: { attivo: !item.attivo },
                      })
                    }
                    className="text-[10px] uppercase text-brand"
                  >
                    {item.attivo ? "Disattiva" : "Riattiva"}
                  </button>
                </div>
              )}
            </article>
          );
        })}
        {!visible.length && (
          <p className="lg:col-span-2 py-12 text-center text-fog">
            Nessuna persona corrisponde ai filtri selezionati.
          </p>
        )}
      </section>

      {assignmentEditor && (
        <PersonaleAssignmentEditor
          cantieri={cantieri}
          personale={personale}
          assignment={assignmentEditor.assignment || null}
          initialCantiereId={cantiereId}
          initialPersonaleId={assignmentEditor.personaleId || ""}
          onClose={() => setAssignmentEditor(null)}
        />
      )}
    </div>
  );
}
