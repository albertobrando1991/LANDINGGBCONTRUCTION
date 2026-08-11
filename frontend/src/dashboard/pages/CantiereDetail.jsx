import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarDays,
  FileStack,
  HardHat,
  LayoutDashboard,
  MapPin,
  UsersRound,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import client, { formatApiErrorDetail } from "@/lib/api";
import CantiereDocuments from "@/dashboard/CantiereDocuments";
import CantierePersonale from "@/dashboard/CantierePersonale";
import CantierePortalAccess from "@/dashboard/CantierePortalAccess";
import CantierePresenze from "@/dashboard/CantierePresenze";
import { CantiereCard } from "@/dashboard/pages/Cantieri";

const SECTIONS = [
  { id: "overview", label: "Panoramica", Icon: LayoutDashboard },
  { id: "presenze", label: "Presenze", Icon: CalendarDays },
  { id: "squadra", label: "Squadra", Icon: UsersRound },
  { id: "documenti", label: "Documenti e cliente", Icon: FileStack },
];

const SECTION_IDS = new Set(SECTIONS.map((item) => item.id));

function sectionPath(cantiereId, section) {
  const base = `/dashboard/cantieri/${encodeURIComponent(cantiereId)}`;
  return section === "overview" ? base : `${base}/${section}`;
}

export default function CantiereDetail() {
  const { id, section } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const activeSection = SECTION_IDS.has(section) ? section : "overview";
  const needsTeam = activeSection === "presenze" || activeSection === "squadra";

  const cantiereQuery = useQuery({
    queryKey: ["cantieri", "detail", id],
    queryFn: async () => (await client.get(`/cantieri/${id}`)).data,
  });
  const staffQuery = useQuery({
    queryKey: ["staff"],
    queryFn: async () => (await client.get("/staff")).data,
    enabled: activeSection === "overview",
  });
  const personaleQuery = useQuery({
    queryKey: ["personale"],
    queryFn: async () => (await client.get("/personale")).data,
    enabled: needsTeam,
  });
  const assegnazioniQuery = useQuery({
    queryKey: ["personale-assegnazioni"],
    queryFn: async () => (await client.get("/personale/assegnazioni")).data,
    enabled: needsTeam,
  });

  const staffNames = useMemo(
    () => (staffQuery.data || []).map((item) => item.name).filter(Boolean),
    [staffQuery.data],
  );

  const persistCantiere = async (cantiereId, body) => {
    try {
      const { data } = await client.patch(`/cantieri/${cantiereId}`, body);
      qc.setQueryData(["cantieri", "detail", cantiereId], data);
      await qc.invalidateQueries({ queryKey: ["cantieri"] });
      return data;
    } catch (error) {
      toast.error(
        formatApiErrorDetail(
          error?.response?.data?.detail ||
            error?.message ||
            "Aggiornamento non riuscito",
        ),
      );
      throw error;
    }
  };

  const deleteCantiere = async (cantiereId) => {
    try {
      await client.delete(`/cantieri/${cantiereId}`);
      await qc.invalidateQueries({ queryKey: ["cantieri"] });
      toast.success("Cantiere eliminato");
      navigate("/dashboard/cantieri", { replace: true });
    } catch (error) {
      toast.error(
        formatApiErrorDetail(
          error?.response?.data?.detail ||
            error?.message ||
            "Eliminazione non riuscita",
        ),
      );
    }
  };

  if (cantiereQuery.isLoading) {
    return (
      <div className="rounded-2xl border border-stroke bg-surface p-8 font-display text-sm uppercase text-fog animate-pulse">
        Caricamento cantiere…
      </div>
    );
  }

  if (cantiereQuery.isError || !cantiereQuery.data) {
    return (
      <div className="space-y-4 rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-300">
        <p>Impossibile aprire il cantiere richiesto.</p>
        <Link
          to="/dashboard/cantieri"
          className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-red-400/40 px-4 font-display text-[10px] uppercase"
        >
          <ArrowLeft className="h-4 w-4" /> Torna ai cantieri
        </Link>
      </div>
    );
  }

  const cantiere = cantiereQuery.data;
  const teamLoading =
    needsTeam && (personaleQuery.isLoading || assegnazioniQuery.isLoading);
  const teamError =
    needsTeam && (personaleQuery.isError || assegnazioniQuery.isError);

  return (
    <div className="space-y-5">
      <header className="rounded-2xl border border-stroke bg-surface p-5">
        <Link
          to="/dashboard/cantieri"
          className="inline-flex min-h-10 items-center gap-2 text-xs text-fog hover:text-brand"
        >
          <ArrowLeft className="h-4 w-4" /> Tutti i cantieri
        </Link>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand/15 text-brand">
              <HardHat className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <p className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
                Scheda cantiere
              </p>
              <h1 className="mt-1 truncate font-display text-2xl font-bold uppercase text-ink">
                {cantiere.cliente}
              </h1>
              <p className="mt-1 flex min-w-0 items-center gap-1 text-xs text-fog">
                <MapPin className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">
                  {cantiere.indirizzo || "Indirizzo da completare"}
                </span>
              </p>
            </div>
          </div>
          <span className="rounded-full border border-brand/30 bg-brand/10 px-3 py-1 font-display text-[10px] uppercase text-brand">
            {Number(cantiere.avanzamento || 0)}% completato
          </span>
        </div>
      </header>

      <nav
        aria-label="Sezioni del cantiere"
        className="grid grid-cols-2 gap-2 rounded-2xl border border-stroke bg-surface p-2 lg:grid-cols-4"
      >
        {SECTIONS.map(({ id: sectionId, label, Icon }) => {
          const active = activeSection === sectionId;
          return (
            <Link
              key={sectionId}
              to={sectionPath(cantiere.id, sectionId)}
              aria-current={active ? "page" : undefined}
              className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-xl px-3 text-center font-display text-[10px] uppercase transition ${
                active
                  ? "bg-brand text-white"
                  : "text-fog hover:bg-bg hover:text-ink"
              }`}
            >
              <Icon className="h-4 w-4" /> {label}
            </Link>
          );
        })}
      </nav>

      {activeSection === "overview" && (
        <CantiereCard
          cantiere={cantiere}
          staffNames={staffNames}
          saving={false}
          deleting={false}
          canDelete={user?.role === "admin"}
          onSave={persistCantiere}
          onAtomicSave={persistCantiere}
          onDelete={deleteCantiere}
          onComplete={(cantiereId) =>
            void persistCantiere(cantiereId, {
              stato: "completato",
              avanzamento: 100,
            })
          }
        />
      )}

      {teamLoading && (
        <div className="rounded-2xl border border-stroke bg-surface p-6 text-sm text-fog animate-pulse">
          Caricamento squadra…
        </div>
      )}
      {teamError && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-sm text-red-300">
          Impossibile caricare personale e assegnazioni.
        </div>
      )}

      {!teamLoading && !teamError && activeSection === "presenze" && (
        <CantierePresenze
          cantiere={cantiere}
          personale={personaleQuery.data || []}
          assegnazioni={assegnazioniQuery.data || []}
          standalone
        />
      )}

      {!teamLoading && !teamError && activeSection === "squadra" && (
        <CantierePersonale
          cantiere={cantiere}
          personale={personaleQuery.data || []}
          assegnazioni={assegnazioniQuery.data || []}
        />
      )}

      {activeSection === "documenti" && (
        <div className="space-y-4 rounded-2xl border border-stroke bg-surface p-5">
          <div>
            <h2 className="font-display text-sm uppercase text-ink">
              Archivio e accesso cliente
            </h2>
            <p className="mt-1 text-xs text-fog">
              Foto, documenti operativi e condivisioni restano fuori dalla
              panoramica del cantiere.
            </p>
          </div>
          <CantiereDocuments cantiereId={cantiere.id} />
          <CantierePortalAccess cantiereId={cantiere.id} />
        </div>
      )}
    </div>
  );
}
