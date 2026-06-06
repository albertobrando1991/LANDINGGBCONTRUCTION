import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Mail, X, Paperclip, Loader2, Send, AlertTriangle, CheckCircle2 } from "lucide-react";
import client, { formatApiErrorDetail } from "@/lib/api";
import { EMAIL_COMPOSE_EVENT } from "@/lib/emailCompose";

const MAX_ATTACH_BYTES = 15 * 1024 * 1024;

const EMPTY = { leadId: null, email: "", nome: "" };

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Modal compose email staff: ascolta EMAIL_COMPOSE_EVENT, invia dall'email
// ufficiale (SMTP/Zimbra) via POST multipart /leads/{leadId}/email.
export default function EmailComposeModal() {
  const [target, setTarget] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [configured, setConfigured] = useState(null);
  const fileInputRef = useRef(null);
  const qc = useQueryClient();

  useEffect(() => {
    const handler = (e) => {
      const detail = e.detail || {};
      setTarget({
        leadId: detail.leadId || null,
        email: detail.email || "",
        nome: detail.nome || "",
      });
      setTo(detail.email || "");
      setSubject("");
      setBody("");
      setFiles([]);
      setError("");
      setDone(false);
      setOpen(true);
      client
        .get("/email/status")
        .then((res) => setConfigured(Boolean(res.data?.configured)))
        .catch(() => setConfigured(null));
    };
    window.addEventListener(EMAIL_COMPOSE_EVENT, handler);
    return () => window.removeEventListener(EMAIL_COMPOSE_EVENT, handler);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && !sending && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, sending]);

  if (!open) return null;

  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  const oversized = files.find((f) => f.size > MAX_ATTACH_BYTES);
  const canSend =
    !sending && to.trim() && subject.trim() && body.trim() && !oversized && target.leadId;

  const addFiles = (fileList) => {
    const incoming = Array.from(fileList || []);
    if (!incoming.length) return;
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const merged = [...prev];
      incoming.forEach((f) => {
        const key = `${f.name}:${f.size}`;
        if (!seen.has(key)) {
          seen.add(key);
          merged.push(f);
        }
      });
      return merged;
    });
  };

  const removeFile = (idx) =>
    setFiles((prev) => prev.filter((_, i) => i !== idx));

  const handleSend = async () => {
    if (!canSend) return;
    setSending(true);
    setError("");
    try {
      const form = new FormData();
      form.append("subject", subject.trim());
      form.append("body", body.trim());
      form.append("to", to.trim());
      files.forEach((f) => form.append("attachments", f, f.name));
      await client.post(`/leads/${target.leadId}/email`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDone(true);
      toast.success("Email inviata al cliente");
      qc.invalidateQueries({ queryKey: ["lead", target.leadId] });
      setTimeout(() => setOpen(false), 1200);
    } catch (err) {
      setError(formatApiErrorDetail(err?.response?.data?.detail) || "Invio email non riuscito.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={() => !sending && setOpen(false)}
      />
      <div className="relative w-full max-w-lg bg-surface border border-stroke rounded-2xl shadow-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 h-14 border-b border-stroke">
          <div className="flex items-center gap-2 font-display uppercase text-sm text-ink">
            <Mail className="w-4 h-4 text-brand" /> Email al cliente
          </div>
          <button
            onClick={() => !sending && setOpen(false)}
            className="text-fog hover:text-ink disabled:opacity-40"
            disabled={sending}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          {configured === false && (
            <div className="flex items-start gap-2 bg-warning/10 border border-warning/30 rounded-xl px-3 py-2 text-warning text-xs font-body">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              Email ufficiale (SMTP/Zimbra) non configurata: l'invio fallirà finché non viene impostata in Impostazioni.
            </div>
          )}

          <div>
            <label className="block font-display uppercase text-[10px] text-fog mb-1">Destinatario</label>
            <input
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="cliente@email.it"
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-sm text-ink placeholder:text-fog outline-none focus:border-brand"
            />
            {target.nome && (
              <p className="mt-1 font-body text-[11px] text-fog">Lead: {target.nome}</p>
            )}
          </div>

          <div>
            <label className="block font-display uppercase text-[10px] text-fog mb-1">Oggetto</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Oggetto della mail"
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-sm text-ink placeholder:text-fog outline-none focus:border-brand"
            />
          </div>

          <div>
            <label className="block font-display uppercase text-[10px] text-fog mb-1">Messaggio</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={7}
              placeholder="Scrivi il messaggio…"
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-sm text-ink placeholder:text-fog outline-none focus:border-brand resize-y"
            />
          </div>

          <div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 font-display uppercase text-[10px] text-brand hover:text-ink"
            >
              <Paperclip className="w-3.5 h-3.5" /> Aggiungi allegato
            </button>
            {files.length > 0 && (
              <ul className="mt-2 space-y-1">
                {files.map((f, i) => (
                  <li
                    key={`${f.name}:${f.size}:${i}`}
                    className={`flex items-center justify-between gap-2 bg-bg border rounded-lg px-3 py-1.5 text-xs font-body ${
                      f.size > MAX_ATTACH_BYTES ? "border-red-500/50 text-red-400" : "border-stroke text-fog"
                    }`}
                  >
                    <span className="truncate">{f.name}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span>{formatBytes(f.size)}</span>
                      <button onClick={() => removeFile(i)} className="hover:text-ink">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {oversized && (
              <p className="mt-1 font-body text-[11px] text-red-400">
                Allegato oltre 15 MB: rimuovilo per inviare.
              </p>
            )}
            {files.length > 0 && !oversized && (
              <p className="mt-1 font-body text-[11px] text-fog">
                {files.length} allegati · {formatBytes(totalBytes)}
              </p>
            )}
          </div>

          {error && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-xl px-3 py-2 text-red-400 text-xs font-body">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /> {error}
            </div>
          )}
          {done && (
            <div className="flex items-center gap-2 bg-success/10 border border-success/30 rounded-xl px-3 py-2 text-success text-xs font-body">
              <CheckCircle2 className="w-4 h-4 shrink-0" /> Email inviata.
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-stroke">
          <button
            onClick={() => !sending && setOpen(false)}
            disabled={sending}
            className="font-display uppercase text-xs text-fog hover:text-ink px-4 py-2 disabled:opacity-40"
          >
            Annulla
          </button>
          <button
            onClick={handleSend}
            disabled={!canSend}
            className="inline-flex items-center gap-2 font-display uppercase text-xs bg-brand text-white rounded-xl px-4 py-2 hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {sending ? "Invio…" : "Invia"}
          </button>
        </div>
      </div>
    </div>
  );
}
