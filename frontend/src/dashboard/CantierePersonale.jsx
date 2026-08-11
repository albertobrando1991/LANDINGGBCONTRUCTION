import { useState } from "react";
import { MessageCircle, Phone, Plus, UsersRound } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  assegnazioneMatchesCantiere,
  formatRuoloLabel,
  isAssegnazioneAttiva,
} from "@/lib/personale";
import { buildWhatsappUrl, normalizeWhatsappPhone } from "@/lib/whatsapp";
import PersonaleAssignmentEditor from "@/dashboard/PersonaleAssignmentEditor";

export default function CantierePersonale({
  cantiere,
  assegnazioni = [],
  personale = [],
}) {
  const { user } = useAuth();
  const [editor, setEditor] = useState(null);
  const canManage = ["owner", "admin"].includes(user?.role);
  const active = assegnazioni.filter(
    (item) =>
      assegnazioneMatchesCantiere(item, cantiere?.id) &&
      isAssegnazioneAttiva(item),
  );

  return (
    <section className="rounded-2xl border border-stroke bg-bg/60 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 font-display text-[10px] uppercase tracking-[0.18em] text-brand">
            <UsersRound className="h-4 w-4" /> Squadra assegnata
          </p>
          <p className="mt-1 text-xs text-fog">
            {active.length
              ? `${active.length} risorse operative`
              : "Nessuna persona assegnata"}
          </p>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={() => setEditor({})}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-brand/40 px-3 font-display text-[10px] uppercase text-brand"
          >
            <Plus className="h-4 w-4" /> Assegna
          </button>
        )}
      </header>

      {active.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {active.map((item) => {
            const whatsapp = buildWhatsappUrl(
              item.telefono,
              item.personale_nome,
            );
            const phone = normalizeWhatsappPhone(item.telefono);
            return (
              <article
                key={item.id}
                className="rounded-xl border border-stroke bg-surface p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-display text-xs uppercase text-ink">
                      {item.personale_nome}
                    </p>
                    <p className="mt-1 text-[10px] text-fog">
                      {formatRuoloLabel(
                        item.personale_tipo,
                        item.ruolo_in_cantiere || item.personale_ruolo,
                      )}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full border border-brand/30 bg-brand/10 px-2 py-1 text-[9px] uppercase text-brand">
                    {item.stato === "in_corso" ? "In cantiere" : "Assegnato"}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
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
                      onClick={() => setEditor(item)}
                      className="min-h-10 rounded-lg border border-stroke px-3 text-[10px] uppercase text-fog"
                    >
                      Modifica
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {editor && (
        <PersonaleAssignmentEditor
          cantieri={[cantiere]}
          personale={personale}
          initialCantiereId={cantiere?.id}
          assignment={editor.id ? editor : null}
          onClose={() => setEditor(null)}
        />
      )}
    </section>
  );
}
