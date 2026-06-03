import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import client, { formatApiErrorDetail } from "@/lib/api";
import { Avatar } from "@/dashboard/Avatar";

export default function Settings() {
  const qc = useQueryClient();
  const { data: staff = [] } = useQuery({ queryKey: ["staff"], queryFn: async () => (await client.get("/staff")).data });
  const { data: coef = {} } = useQuery({ queryKey: ["coef"], queryFn: async () => (await client.get("/coefficienti")).data });
  const { data: voci = [] } = useQuery({ queryKey: ["voci"], queryFn: async () => (await client.get("/voci")).data });
  const { data: metaStatus = {} } = useQuery({
    queryKey: ["meta-status"],
    queryFn: async () => (await client.get("/integrations/meta/status")).data,
    refetchInterval: 30000,
  });

  const [form, setForm] = useState({ nome: "", email: "", password: "", role: "staff" });
  const createStaff = useMutation({
    mutationFn: (b) => client.post("/staff", b),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["staff"] }); setForm({ nome: "", email: "", password: "", role: "staff" }); toast.success("Utente creato"); },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });
  const retryMeta = useMutation({
    mutationFn: () => client.post("/integrations/meta/retry-failed"),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["meta-status"] });
      toast.success(`${res.data.queued || 0} eventi Meta rimessi in coda`);
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  return (
    <div className="space-y-5">
      <h1 className="font-display font-bold uppercase text-3xl text-ink">Impostazioni</h1>
      <Tabs defaultValue="azienda">
        <TabsList className="bg-surface border border-stroke flex-wrap h-auto">
          <TabsTrigger value="azienda">Azienda</TabsTrigger>
          <TabsTrigger value="staff">Staff</TabsTrigger>
          <TabsTrigger value="meta">Meta Ads</TabsTrigger>
          <TabsTrigger value="motore">Motore predittivo</TabsTrigger>
          <TabsTrigger value="voci">Voci standard</TabsTrigger>
        </TabsList>

        <TabsContent value="azienda" className="mt-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Ragione sociale" value="GB Construction S.R.L.S." />
            <Field label="Sede" value="Via San Giacomo 35, 80013 Casalnuovo di Napoli (NA)" />
            <Field label="Telefono" value="+39 389 658 4125" />
            <Field label="Email" value="info@gbconstruction.it" />
            <Field label="Social" value="@gbconstructionsrl" />
            <Field label="Zone operative" value="Napoli e tutta la Campania" />
          </div>
        </TabsContent>

        <TabsContent value="staff" className="mt-5 space-y-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Team</h3>
            <div className="space-y-2">
              {staff.map((u) => (
                <div key={u.id} className="flex items-center gap-3 bg-bg border border-stroke rounded-xl px-3 py-2">
                  <Avatar name={u.name} photo={u.photo} size={36} />
                  <div className="flex-1"><div className="font-display uppercase text-xs text-ink">{u.name}</div><div className="font-body text-[11px] text-fog">{u.email}</div></div>
                  <span className="font-display uppercase text-[10px] bg-brand/15 text-brand px-3 py-1 rounded-full">{u.role}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Aggiungi utente</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input data-testid="staff-nome" placeholder="Nome" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} className="bg-bg border border-stroke rounded-xl px-4 py-2.5 text-ink text-sm focus:outline-none focus:border-brand" />
              <input data-testid="staff-email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="bg-bg border border-stroke rounded-xl px-4 py-2.5 text-ink text-sm focus:outline-none focus:border-brand" />
              <input data-testid="staff-password" type="password" placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="bg-bg border border-stroke rounded-xl px-4 py-2.5 text-ink text-sm focus:outline-none focus:border-brand" />
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger className="bg-bg border-stroke text-ink"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="staff">Staff</SelectItem><SelectItem value="operations">Operations</SelectItem><SelectItem value="admin">Admin</SelectItem></SelectContent>
              </Select>
            </div>
            <button data-testid="staff-create" onClick={() => createStaff.mutate(form)} disabled={!form.nome || !form.email || !form.password}
              className="mt-4 bg-brand text-white rounded-full px-6 py-2.5 font-display uppercase text-xs tracking-wider hover:scale-105 transition-transform disabled:opacity-50">Crea utente</button>
          </div>
        </TabsContent>

        <TabsContent value="meta" className="mt-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6 space-y-5">
            <div>
              <h3 className="font-display font-semibold uppercase text-sm text-ink">Integrazione Meta Lead Ads</h3>
              <p className="font-body text-xs text-fog mt-1">Webhook: /api/webhooks/meta</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <StatusPill label="Verify token" active={metaStatus.configured?.verify_token} />
              <StatusPill label="App secret" active={metaStatus.configured?.app_secret} />
              <StatusPill label="Page token" active={metaStatus.configured?.page_access_token} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Field label="Versione Graph" value={metaStatus.graph_version || "v23.0"} />
              <Field label="Lead Meta importati" value={String(metaStatus.meta_leads || 0)} />
              <Field label="Eventi falliti" value={String(metaStatus.failed_events || 0)} />
            </div>
            {metaStatus.last_event && (
              <div className="bg-bg border border-stroke rounded-xl px-4 py-3">
                <div className="font-display uppercase text-[10px] text-fog mb-1">Ultimo evento</div>
                <div className="font-body text-xs text-ink">
                  {metaStatus.last_event.leadgen_id || "-"} · {metaStatus.last_event.status || "-"}
                </div>
              </div>
            )}
            <button onClick={() => retryMeta.mutate()} disabled={retryMeta.isPending || !metaStatus.failed_events}
              className="bg-brand text-white rounded-full px-5 py-2 font-display uppercase text-xs tracking-wider hover:scale-105 transition-transform disabled:opacity-50">
              Ritenta eventi falliti
            </button>
          </div>
        </TabsContent>

        <TabsContent value="motore" className="mt-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Coefficienti GB</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(coef).map(([key, val]) => (
                <div key={key} className="bg-bg border border-stroke rounded-xl px-3 py-2">
                  <div className="font-display uppercase text-[10px] text-fog">{key.replace(/_/g, " ")}</div>
                  <div className="font-display font-bold text-brand">{val}</div>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="voci" className="mt-5">
          <div className="bg-surface border border-stroke rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-stroke font-display uppercase text-xs text-ink">{voci.length} voci standard</div>
            <div className="max-h-[500px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface">
                  <tr className="text-left font-display uppercase text-[10px] text-fog border-b border-stroke">
                    <th className="px-4 py-2">ID</th><th className="px-4 py-2">Categoria</th><th className="px-4 py-2">Voce</th><th className="px-4 py-2">U.M.</th><th className="px-4 py-2">PU Premium</th><th className="px-4 py-2">PU Luxury</th>
                  </tr>
                </thead>
                <tbody>
                  {voci.map((v) => (
                    <tr key={v.id} className="border-b border-stroke/50">
                      <td className="px-4 py-2 font-body text-xs text-fog">{v.id}</td>
                      <td className="px-4 py-2 font-body text-xs text-fog">{v.categoria}</td>
                      <td className="px-4 py-2 font-body text-xs text-ink">{v.voce}</td>
                      <td className="px-4 py-2 font-body text-xs text-fog">{v.u_m}</td>
                      <td className="px-4 py-2 font-display text-xs text-brand">€{v.pu_premium}</td>
                      <td className="px-4 py-2 font-display text-xs text-gold">€{v.pu_luxury}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div className="font-display uppercase text-[10px] text-fog mb-1">{label}</div>
      <div className="bg-bg border border-stroke rounded-xl px-4 py-2.5 text-ink text-sm">{value}</div>
    </div>
  );
}

function StatusPill({ label, active }) {
  return (
    <div className="bg-bg border border-stroke rounded-xl px-4 py-3">
      <div className="font-display uppercase text-[10px] text-fog mb-1">{label}</div>
      <span className={`font-display uppercase text-[10px] px-3 py-1 rounded-full ${
        active ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"
      }`}>
        {active ? "Configurato" : "Mancante"}
      </span>
    </div>
  );
}
