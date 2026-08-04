import { useEffect } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

const COMPANY = {
  name: "GB Construction S.R.L.S.",
  address: "Via San Giacomo 35, 80013 Casalnuovo di Napoli (NA)",
  vat: "09965211213",
  email: "info@gbconstruction.it",
};

function Section({ title, children }) {
  return (
    <section className="space-y-3">
      <h2 className="font-display text-xl font-semibold uppercase tracking-wide text-ink md:text-2xl">
        {title}
      </h2>
      <div className="space-y-3 font-body text-sm leading-7 text-fog md:text-base">
        {children}
      </div>
    </section>
  );
}

function PrivacyPolicy() {
  return (
    <>
      <Section title="1. Titolare del trattamento">
        <p>
          Il titolare del trattamento è {COMPANY.name}, P.IVA {COMPANY.vat}, con
          sede in {COMPANY.address}. Per richieste relative ai dati personali
          puoi scrivere a{" "}
          <a className="underline" href={`mailto:${COMPANY.email}`}>
            {COMPANY.email}
          </a>
          .
        </p>
      </Section>

      <Section title="2. Dati trattati">
        <p>
          Il sito tratta i dati che scegli di fornire nei moduli di preventivo,
          richiamo e sopralluogo: nome, email, telefono, città, indirizzo
          dell’immobile, informazioni sul progetto e messaggi liberi.
        </p>
        <p>
          Se utilizzi AI Architect possono essere trattati anche planimetrie,
          immagini, preferenze progettuali e output tecnici collegati alla
          richiesta. Ti chiediamo di rimuovere dai file dati personali non
          necessari.
        </p>
        <p>
          Per la sicurezza e il funzionamento del servizio vengono inoltre
          trattati dati tecnici come indirizzo IP, log, tipo di browser, URL di
          provenienza e parametri di campagna.
        </p>
      </Section>

      <Section title="3. Finalità e basi giuridiche">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            rispondere alle richieste e predisporre stime, preventivi e
            sopralluoghi;
          </li>
          <li>
            eseguire misure precontrattuali e servizi richiesti
            dall’interessato;
          </li>
          <li>
            gestire il rapporto con clienti, cantieri e comunicazioni operative;
          </li>
          <li>
            proteggere il sito da abusi e garantire sicurezza e continuità;
          </li>
          <li>adempiere a obblighi legali, amministrativi e fiscali;</li>
          <li>
            inviare comunicazioni promozionali solo quando è stato espresso un
            consenso valido.
          </li>
        </ul>
      </Section>

      <Section title="4. Destinatari e fornitori">
        <p>
          I dati possono essere trattati da personale autorizzato e da fornitori
          necessari al servizio, tra cui hosting, database, posta elettronica,
          assistenza tecnica e, quando richiesto, servizi di intelligenza
          artificiale. Tali soggetti operano secondo accordi e istruzioni
          coerenti con il GDPR.
        </p>
        <p>
          I dati non vengono venduti. Possono essere comunicati ad autorità o
          professionisti quando previsto dalla legge o necessario per tutelare
          un diritto.
        </p>
      </Section>

      <Section title="5. Trasferimenti e conservazione">
        <p>
          Alcuni fornitori tecnologici possono trattare dati fuori dallo Spazio
          Economico Europeo. In questi casi il trasferimento avviene usando le
          garanzie previste dal GDPR, incluse decisioni di adeguatezza o
          clausole contrattuali standard quando applicabili.
        </p>
        <p>
          I dati vengono conservati per il tempo necessario alla finalità per
          cui sono stati raccolti e agli obblighi di legge. Le richieste non
          trasformate in rapporto contrattuale vengono riesaminate e cancellate
          o anonimizzate quando non sono più necessarie.
        </p>
      </Section>

      <Section title="6. Diritti dell’interessato">
        <p>
          Puoi chiedere accesso, rettifica, cancellazione, limitazione,
          portabilità o opposizione al trattamento e revocare un consenso senza
          pregiudicare i trattamenti già effettuati. Puoi inoltre proporre
          reclamo al Garante per la protezione dei dati personali.
        </p>
      </Section>

      <Section title="7. Sicurezza, minori e aggiornamenti">
        <p>
          GB Construction adotta misure tecniche e organizzative proporzionate
          al rischio. I servizi non sono destinati a minori di 16 anni. Questa
          informativa può essere aggiornata quando cambiano funzioni, fornitori
          o obblighi normativi; la versione pubblicata sul sito è quella
          applicabile.
        </p>
      </Section>
    </>
  );
}

function CookiePolicy() {
  return (
    <>
      <Section title="1. Cosa usa questo sito">
        <p>
          La versione corrente del sito non installa intenzionalmente cookie di
          profilazione o pubblicità. Utilizza tecnologie strettamente necessarie
          al funzionamento, alla sicurezza e alla misurazione della provenienza
          di una richiesta quando l’utente decide di inviarla.
        </p>
      </Section>

      <Section title="2. Cookie di autenticazione staff">
        <p>
          L’area riservata usa cookie HTTP-only denominati{" "}
          <code>access_token</code>e <code>refresh_token</code>. Servono
          esclusivamente a mantenere la sessione autenticata e sono protetti con
          attributi Secure e SameSite. La durata massima prevista è
          rispettivamente 12 ore e 7 giorni; vengono rimossi al logout.
        </p>
      </Section>

      <Section title="3. Memoria di sessione del browser">
        <p>
          Il sito può usare <code>sessionStorage</code> per conservare, fino
          alla chiusura della scheda, parametri UTM, URL di provenienza e
          identificativi di campagna. Queste informazioni vengono collegate alla
          richiesta solo se compili e invii volontariamente un modulo.
        </p>
      </Section>

      <Section title="4. Risorse e servizi esterni">
        <p>
          I caratteri web possono essere caricati da Google Fonts; la richiesta
          tecnica può comunicare al fornitore indirizzo IP e informazioni del
          browser. I link verso WhatsApp, Instagram e Facebook attivano i
          servizi esterni solo quando li selezioni e sono soggetti alle
          rispettive informative.
        </p>
      </Section>

      <Section title="5. Gestione delle preferenze">
        <p>
          Puoi eliminare cookie e dati del sito dalle impostazioni del browser o
          impedire il salvataggio futuro. Il blocco dei cookie strettamente
          necessari può impedire l’accesso all’area staff. Prima di introdurre
          strumenti di analisi o marketing non essenziali, il sito dovrà
          richiedere il consenso e aggiornare questa informativa.
        </p>
      </Section>

      <Section title="6. Contatti">
        <p>
          Per domande sulla presente informativa scrivi a{" "}
          <a className="underline" href={`mailto:${COMPANY.email}`}>
            {COMPANY.email}
          </a>
          .
        </p>
      </Section>
    </>
  );
}

export default function LegalPage({ kind }) {
  const isPrivacy = kind === "privacy";
  const title = isPrivacy ? "Privacy Policy" : "Cookie Policy";

  useEffect(() => {
    document.title = `${title} | GB Construction`;
    window.scrollTo(0, 0);
  }, [title]);

  return (
    <main className="min-h-screen bg-bg px-6 py-10 text-ink md:py-16">
      <article className="mx-auto max-w-4xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 font-display text-xs font-semibold uppercase tracking-[0.18em] text-brand hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Torna al sito
        </Link>

        <header className="mb-12 mt-10 border-b border-stroke pb-8">
          <p className="mb-3 font-display text-xs font-semibold uppercase tracking-[0.28em] text-brand">
            GB Construction
          </p>
          <h1 className="font-display text-4xl font-bold uppercase tracking-tight md:text-6xl">
            {title}
          </h1>
          <p className="mt-4 font-body text-sm text-fog">
            Ultimo aggiornamento tecnico: 4 agosto 2026.
          </p>
        </header>

        <div className="space-y-10">
          {isPrivacy ? <PrivacyPolicy /> : <CookiePolicy />}
        </div>

        <footer className="mt-14 border-t border-stroke pt-6 font-body text-xs text-fog">
          {COMPANY.name} · P.IVA {COMPANY.vat} · {COMPANY.address}
        </footer>
      </article>
    </main>
  );
}
