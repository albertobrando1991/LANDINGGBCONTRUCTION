import {
  useEffect,
  useState,
  useCallback,
  useRef,
  useLayoutEffect,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Calendar, Clock, X, Check, Loader2, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { BOOKING_EVENT } from "@/lib/booking";

const WEEKDAYS = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];
const MONTHS = [
  "gennaio",
  "febbraio",
  "marzo",
  "aprile",
  "maggio",
  "giugno",
  "luglio",
  "agosto",
  "settembre",
  "ottobre",
  "novembre",
  "dicembre",
];

function formatDay(iso) {
  const d = new Date(`${iso}T00:00:00`);
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export default function BookingModal() {
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const previousFocusRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [ctx, setCtx] = useState({});
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);
  const [form, setForm] = useState({
    nome: "",
    email: "",
    telefono: "",
    indirizzo: "",
  });

  const loadSlots = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get("/public/sopralluoghi/slots");
      setSlots(data || []);
    } catch {
      setSlots([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handler = (event) => {
      const detail = event.detail || {};
      setCtx(detail);
      setForm({
        nome: detail.nome || "",
        email: detail.email || "",
        telefono: detail.telefono || "",
        indirizzo: detail.indirizzo || "",
      });
      setSelected(null);
      setDone(null);
      setOpen(true);
      loadSlots();
    };
    window.addEventListener(BOOKING_EVENT, handler);
    return () => window.removeEventListener(BOOKING_EVENT, handler);
  }, [loadSlots]);

  const close = () => setOpen(false);

  useLayoutEffect(() => {
    if (!open) return undefined;

    previousFocusRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = dialogRef.current.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus?.();
    };
  }, [open]);

  const grouped = slots.reduce((acc, slot) => {
    (acc[slot.date] = acc[slot.date] || []).push(slot);
    return acc;
  }, {});
  const days = Object.keys(grouped).sort();

  const canBook =
    selected &&
    form.nome.trim().length >= 2 &&
    /.+@.+\..+/.test(form.email) &&
    form.telefono.trim().length >= 6;

  const book = async () => {
    if (!canBook) return;
    setSubmitting(true);
    try {
      const { data } = await client.post("/public/sopralluoghi/book", {
        slot_id: selected.id,
        nome: form.nome,
        email: form.email,
        telefono: form.telefono,
        indirizzo: form.indirizzo,
        lead_id: ctx.leadId || undefined,
      });
      setDone(data.slot);
      toast.success("Sopralluogo prenotato!");
    } catch (err) {
      if (err.response?.status === 409) {
        toast.error(
          "Quello slot è appena stato preso. Scegli un altro orario.",
        );
        setSelected(null);
        loadSlots();
      } else {
        toast.error(
          formatApiErrorDetail(err.response?.data?.detail) ||
            "Prenotazione non riuscita.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-6"
        >
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={close}
            aria-hidden="true"
          />
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="booking-dialog-title"
            tabIndex={-1}
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            className="relative w-full max-w-2xl max-h-[92vh] overflow-y-auto bg-surface border border-stroke rounded-t-3xl sm:rounded-3xl p-6 md:p-8"
            style={{
              paddingBottom: "max(1.5rem, env(safe-area-inset-bottom))",
            }}
          >
            <button
              ref={closeButtonRef}
              type="button"
              onClick={close}
              aria-label="Chiudi prenotazione sopralluogo"
              className="absolute top-3 right-3 inline-flex h-11 w-11 items-center justify-center rounded-full text-fog hover:text-ink touch-manipulation sm:top-4 sm:right-4"
            >
              <X className="w-5 h-5" />
            </button>

            {done ? (
              <div
                className="text-center py-8"
                role="status"
                aria-live="polite"
              >
                <div className="w-16 h-16 rounded-full bg-success/20 border-2 border-success flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-success" />
                </div>
                <h3
                  id="booking-dialog-title"
                  className="font-display font-bold uppercase text-2xl text-ink"
                >
                  Sopralluogo prenotato
                </h3>
                <p className="font-body text-fog mt-2">
                  {formatDay(done.date)} · {done.start}–{done.end}
                </p>
                <p className="font-body text-sm text-fog mt-3">
                  Ti contatteremo per confermare. A presto!
                </p>
                <button
                  type="button"
                  onClick={close}
                  className="mt-6 bg-brand text-white rounded-full px-8 py-3 font-display font-semibold uppercase tracking-wider"
                >
                  Chiudi
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-2">
                  <Calendar className="w-6 h-6 text-brand" />
                  <h3
                    id="booking-dialog-title"
                    className="font-display font-bold uppercase text-2xl text-ink"
                  >
                    Prenota il sopralluogo gratuito
                  </h3>
                </div>
                <p className="font-body text-sm text-fog mb-5">
                  Scegli un giorno e un orario tra le disponibilità del nostro
                  team.
                </p>

                {loading ? (
                  <div
                    className="py-10 text-center text-fog font-display uppercase text-sm animate-pulse"
                    role="status"
                    aria-live="polite"
                  >
                    Carico le disponibilità…
                  </div>
                ) : days.length === 0 ? (
                  <div className="py-8 text-center">
                    <p className="font-body text-fog">
                      Al momento non ci sono slot disponibili. Lascia i tuoi
                      dati nel preventivo: ti ricontattiamo per fissare il
                      sopralluogo.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {days.map((day) => (
                      <div key={day}>
                        <p className="font-display font-semibold uppercase text-xs text-ink mb-2">
                          {formatDay(day)}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {grouped[day].map((slot) => {
                            const active = selected?.id === slot.id;
                            return (
                              <button
                                type="button"
                                key={slot.id}
                                onClick={() => setSelected(slot)}
                                aria-pressed={active}
                                aria-label={`${formatDay(day)}, dalle ${slot.start} alle ${slot.end}`}
                                className={`font-display font-semibold text-sm rounded-full px-4 py-2 border inline-flex items-center gap-2 transition-all ${
                                  active
                                    ? "bg-brand text-white border-brand"
                                    : "bg-bg text-ink border-stroke hover:border-brand"
                                }`}
                              >
                                <Clock className="w-3.5 h-3.5" /> {slot.start}–
                                {slot.end}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                      <label htmlFor="booking-name" className="sr-only">
                        Nome e cognome
                      </label>
                      <input
                        id="booking-name"
                        type="text"
                        autoComplete="name"
                        required
                        value={form.nome}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, nome: e.target.value }))
                        }
                        placeholder="Nome e cognome *"
                        className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                      />
                      <label htmlFor="booking-phone" className="sr-only">
                        Telefono o WhatsApp
                      </label>
                      <input
                        id="booking-phone"
                        type="tel"
                        autoComplete="tel"
                        required
                        value={form.telefono}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, telefono: e.target.value }))
                        }
                        placeholder="Telefono / WhatsApp *"
                        className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                      />
                      <label htmlFor="booking-email" className="sr-only">
                        Email
                      </label>
                      <input
                        id="booking-email"
                        type="email"
                        autoComplete="email"
                        required
                        value={form.email}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, email: e.target.value }))
                        }
                        placeholder="Email *"
                        className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                      />
                      <label htmlFor="booking-address" className="sr-only">
                        Indirizzo dell'immobile
                      </label>
                      <input
                        id="booking-address"
                        type="text"
                        autoComplete="street-address"
                        value={form.indirizzo}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, indirizzo: e.target.value }))
                        }
                        placeholder="Indirizzo immobile"
                        className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                      />
                    </div>

                    <p className="font-body text-xs leading-relaxed text-fog">
                      Prenotando dichiari di aver letto la{" "}
                      <a
                        href="/privacy-policy"
                        className="underline hover:text-ink"
                      >
                        Privacy Policy
                      </a>
                      .
                    </p>

                    <button
                      type="button"
                      onClick={book}
                      disabled={!canBook || submitting}
                      className="w-full bg-brand text-white rounded-full py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {submitting ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <>
                          Conferma prenotazione{" "}
                          <ArrowRight className="w-5 h-5" />
                        </>
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
