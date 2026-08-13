import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock3,
  Loader2,
  MailPlus,
  RefreshCw,
  UserRoundCheck,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";

const PAYMENT_LABELS = {
  sal: "Pagamento a SAL",
  scaglionato_fisso: "Pagamento scaglionato",
  due_tranche: "Pagamento in due tranche",
};

export default function LeadPortalAccess({ leadId, email }) {
  const queryClient = useQueryClient();
  const queryKey = ["lead-portal-access", leadId];
  const portal = useQuery({
    queryKey,
    queryFn: async () => (await client.get(`/leads/${leadId}/portale`)).data,
    enabled: Boolean(leadId),
  });
  const invite = useMutation({
    mutationFn: () => client.post(`/leads/${leadId}/portale/invita`),
    onSuccess: ({ data }) => {
      queryClient.setQueryData(queryKey, data);
      queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
      toast.success(
        data.invited
          ? "Invito all'area cliente inviato"
          : "Email di accesso inviata nuovamente",
      );
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });

  const data = portal.data;
  const recipient = data?.cliente_email || email;

  return (
    <section
      data-testid="lead-portal-access"
      className="mt-4 rounded-xl border border-stroke bg-bg p-3"
    >
      <div className="flex items-start gap-2">
        <UserRoundCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
        <div className="min-w-0 flex-1">
          <div className="font-display text-[10px] uppercase tracking-wider text-ink">
            Area personale cliente
          </div>
          <p className="mt-1 font-body text-[11px] leading-4 text-fog">
            Invia l'accesso al preventivo per consentire al cliente di scegliere
            o confermare la modalit&agrave; di pagamento.
          </p>
        </div>
      </div>

      {portal.isLoading ? (
        <div className="mt-3 inline-flex items-center gap-2 font-body text-[11px] text-fog">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifica accesso...
        </div>
      ) : portal.isError ? (
        <p className="mt-3 font-body text-[11px] text-danger">
          Stato area cliente non disponibile
          {portal.error?.response?.data?.detail
            ? `: ${formatApiErrorDetail(portal.error.response.data.detail)}`
            : "."}
        </p>
      ) : !data?.available ? (
        <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 font-body text-[11px] text-amber-300">
          Crea prima un preventivo collegato al lead per poter inviare
          l'accesso.
        </div>
      ) : (
        <>
          <div className="mt-3 flex flex-wrap gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-1 font-display text-[9px] uppercase ${
                data.accesso_attivo
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-amber-500/10 text-amber-300"
              }`}
            >
              {data.accesso_attivo ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Clock3 className="h-3 w-3" />
              )}
              {data.accesso_attivo ? "Accesso collegato" : "Accesso da inviare"}
            </span>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-1 font-display text-[9px] uppercase ${
                data.pagamento_confermato
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-amber-500/10 text-amber-300"
              }`}
            >
              {data.pagamento_confermato ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Clock3 className="h-3 w-3" />
              )}
              {data.pagamento_confermato
                ? PAYMENT_LABELS[data.modalita_pagamento] ||
                  "Pagamento confermato"
                : "Pagamento da confermare"}
            </span>
          </div>

          <div className="mt-3 font-body text-[10px] text-fog min-w-0 break-all">
            Preventivo {data.numero_preventivo || "collegato"}
            {recipient ? ` - ${recipient}` : ""}
          </div>
          <button
            type="button"
            data-testid="lead-portal-invite"
            onClick={() => invite.mutate()}
            disabled={!recipient || invite.isPending}
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 font-display text-[10px] uppercase tracking-wider text-white transition hover:brightness-110 disabled:opacity-40"
          >
            {invite.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : data.accesso_attivo ? (
              <RefreshCw className="h-4 w-4" />
            ) : (
              <MailPlus className="h-4 w-4" />
            )}
            {data.accesso_attivo
              ? "Reinvia email di accesso"
              : "Invia email di accesso"}
          </button>
        </>
      )}
    </section>
  );
}
