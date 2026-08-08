import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FileClock, FileText, Mail, MessageCircle } from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";
import { preventivoGestibile } from "@/lib/preventivi";
import { buildWhatsappUrl } from "@/lib/whatsapp";
import { STATI } from "@/dashboard/leadMeta";
import NuovoPreventivoModal from "@/dashboard/NuovoPreventivoModal";
import PreventivoLifecycleModal from "@/dashboard/PreventivoLifecycleModal";

export default function Preventivi() {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedPreventivo, setSelectedPreventivo] = useState(null);
  const { data: list = [], isLoading } = useQuery({
    queryKey: ["preventivi"],
    queryFn: async () => (await client.get("/preventivi")).data,
    refetchInterval: 30000,
  });

  const openPreventivo = (preventivo) => {
    navigate(
      preventivo.source === "edilos"
        ? `/dashboard/computi/${preventivo.computo_id}`
        : `/dashboard/lead/${preventivo.id}`,
    );
  };

  const downloadPdf = async (preventivo) => {
    try {
      const response = await client.get(`/preventivi/${preventivo.id}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${preventivo.numero || "preventivo"}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(
        formatApiErrorDetail(error?.response?.data?.detail) ||
          "Download del PDF non riuscito.",
      );
    }
  };

  if (isLoading)
    return (
      <div className="animate-pulse font-display uppercase text-fog">
        Caricamento…
      </div>
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-3xl font-bold uppercase text-ink">
          Preventivi
        </h1>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="rounded-full bg-brand px-5 py-2 font-display text-xs uppercase tracking-wider text-white transition-transform hover:scale-105"
        >
          + Nuovo preventivo
        </button>
      </div>

      <NuovoPreventivoModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
      <PreventivoLifecycleModal
        preventivo={selectedPreventivo}
        onClose={() => setSelectedPreventivo(null)}
      />

      <div className="overflow-hidden rounded-2xl border border-stroke bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="border-b border-stroke text-left font-display text-[10px] uppercase tracking-wider text-fog">
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Città</th>
                <th className="px-4 py-3">Soluzione</th>
                <th className="px-4 py-3">Importo</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">Silenzio</th>
                <th className="px-4 py-3 text-right">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {list.map((preventivo) => {
                const whatsappUrl = buildWhatsappUrl(
                  preventivo.telefono,
                  preventivo.cliente,
                );
                const gestibile = preventivoGestibile(preventivo);
                const bozzaModificabile =
                  preventivo.stato_documento === "bozza" &&
                  preventivo.computo_stato !== "confermato";
                return (
                  <tr
                    key={`${preventivo.source || "legacy"}-${preventivo.id}`}
                    className="cursor-pointer border-b border-stroke/60 hover:bg-surface-2/50"
                    onClick={() => openPreventivo(preventivo)}
                    role="link"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (
                        event.target === event.currentTarget &&
                        (event.key === "Enter" || event.key === " ")
                      ) {
                        event.preventDefault();
                        openPreventivo(preventivo);
                      }
                    }}
                  >
                    <td className="px-4 py-3 font-display text-xs uppercase text-ink">
                      {preventivo.cliente}
                    </td>
                    <td className="px-4 py-3 font-body text-xs text-fog">
                      {preventivo.citta || "—"}
                    </td>
                    <td className="px-4 py-3 font-body text-xs capitalize text-fog">
                      {preventivo.livello}
                    </td>
                    <td className="px-4 py-3 font-display text-xs text-brand">
                      {formatEuro(preventivo.range_basso)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-1 font-display text-[10px] uppercase ${
                          bozzaModificabile
                            ? "bg-amber-500/15 text-amber-300"
                            : `${STATI[preventivo.status]?.bg || "bg-slate-500/20"} ${STATI[preventivo.status]?.color || "text-fog"}`
                        }`}
                      >
                        {bozzaModificabile
                          ? "Bozza modificabile"
                          : STATI[preventivo.status]?.label ||
                            preventivo.stato_documento ||
                            "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {[
                        "preventivo_inviato",
                        "follow_up",
                        "in_trattativa",
                      ].includes(preventivo.status) ? (
                        <span
                          className={`rounded-full px-2 py-0.5 font-display text-[10px] ${preventivo.giorni_silenzio > 10 ? "bg-red-500/20 text-red-400" : preventivo.giorni_silenzio >= 5 ? "bg-yellow-500/20 text-yellow-400" : "bg-emerald-500/20 text-emerald-400"}`}
                        >
                          {preventivo.giorni_silenzio}gg
                        </span>
                      ) : (
                        <span className="text-xs text-fog">—</span>
                      )}
                    </td>
                    <td
                      className="px-4 py-3"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <div className="flex items-center justify-end gap-3 text-fog">
                        {gestibile && !bozzaModificabile && (
                          <button
                            type="button"
                            onClick={() => setSelectedPreventivo(preventivo)}
                            aria-label={`Gestisci preventivo ${preventivo.numero || preventivo.cliente}`}
                            className="hover:text-brand"
                            title={
                              preventivo.stato_documento === "bozza"
                                ? "Invia preventivo"
                                : "Gestisci stato e storico"
                            }
                          >
                            {preventivo.stato_documento === "bozza" ? (
                              <Mail className="h-4 w-4" />
                            ) : (
                              <FileClock className="h-4 w-4" />
                            )}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() =>
                            gestibile
                              ? downloadPdf(preventivo)
                              : openPreventivo(preventivo)
                          }
                          aria-label={
                            gestibile
                              ? `Scarica PDF ${preventivo.numero || preventivo.cliente}`
                              : `Apri scheda ${preventivo.cliente}`
                          }
                          className="hover:text-ink"
                          title={gestibile ? "Scarica PDF" : "Apri scheda"}
                        >
                          <FileText className="h-4 w-4" />
                        </button>
                        {whatsappUrl ? (
                          <a
                            href={whatsappUrl}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`Scrivi a ${preventivo.cliente} su WhatsApp`}
                            className="hover:text-success"
                          >
                            <MessageCircle
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </a>
                        ) : (
                          <span className="opacity-30">
                            <MessageCircle className="h-4 w-4" />
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {list.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center font-body text-fog"
                  >
                    Nessun preventivo.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
