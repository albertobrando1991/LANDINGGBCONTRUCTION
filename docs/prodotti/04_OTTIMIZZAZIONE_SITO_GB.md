# Ottimizzazione del sito GB Construction

Data: 7 ottobre 2026. Interventi sul codice locale, branch `main`, base `b4f294d`. Nessun commit, push o deploy eseguito. La preview Vercel non contiene automaticamente queste modifiche; il dominio principale resta sospeso per scelta del proprietario.

> Questo rapporto fotografa il lavoro locale prima della richiesta di commit e push. Per il successivo trasferimento selettivo a `develop`, vedere [05 ? Release preview](05_RELEASE_PREVIEW.md).

## Interventi realizzati

I percorsi seguenti sono relativi alla radice del repository.

| Problema affrontato | Intervento | File |
| --- | --- | --- |
| Il pulsante nel dettaglio di un pacchetto lasciava aperta la finestra mentre scorreva il contenuto sottostante | Chiusura del dialogo prima dello spostamento, focus sul configuratore; alla chiusura ordinaria il focus torna al pulsante di apertura | `frontend/src/landing/Packages.jsx`, `frontend/src/lib/scroll.js` |
| Tornando ai passaggi precedenti si rischiava di ricreare i componenti e perdere le scelte | Configuratore e dettagli restano montati; la fase inattiva è nascosta. Un solo contenitore stabile con ancoraggio `configuratore` | `frontend/src/landing/Landing.jsx`, `frontend/src/landing/Configurator.jsx` |
| Attesa introduttiva artificiale di circa 2,3 secondi | Rimossa la schermata `LoadingScreen` dal percorso della landing. Il caricamento reale degli asset della sequenza animata resta presente | `frontend/src/landing/Landing.jsx` |
| La sequenza iniziale richiedeva molto scorrimento prima delle sezioni utili | Altezza ridotta da 1250svh a 450svh su mobile e da 1100vh a 650vh su desktop; invito alla stima subito disponibile | `frontend/src/landing/ImmersiveHero.jsx` |
| Prima schermata poco esplicita su attività e territorio; testo sovrapposto a immagini chiare | Titolo su ristrutturazioni a Napoli e in Campania, breve spiegazione, pulsante diretto e sfondo scurito durante il messaggio iniziale | `frontend/src/landing/ImmersiveHero.jsx` |
| Le proposte dipendevano dalle immagini per comunicare il contenuto | Titoli e sintesi anche in HTML, riprendendo le descrizioni già presenti nel configuratore; descrizione accessibile del dialogo | `frontend/src/landing/Packages.jsx` |
| Il menu Servizi conduceva al configuratore; i progetti non avevano un accesso diretto dal menu | Servizi conduce alle soluzioni; aggiunta voce Progetti con ancoraggio dedicato | `frontend/src/landing/Navbar.jsx`, `frontend/src/landing/SocialProof.jsx` |
| Il menu mobile chiuso poteva lasciare controlli raggiungibili da tastiera | Attributo `hidden`, focus all'apertura, navigazione Tab contenuta nel menu aperto e restituzione del focus alla chiusura | `frontend/src/landing/Navbar.jsx` |
| Un errore nel recupero delle disponibilità appariva come assenza di appuntamenti | Stati distinti per errore e calendario vuoto, pulsante Riprova e collegamento WhatsApp esistente come alternativa | `frontend/src/landing/BookingModal.jsx` |
| Promesse statiche non collegate a dati aggiornati | Rimossa la promessa di completamento in 60 secondi; sostituita la disponibilità settimanale fissa con “Sopralluoghi gratuiti su appuntamento” | `frontend/src/landing/Configurator.jsx`, `frontend/src/landing/Footer.jsx` |
| Il titolo impostato dal marchio non conservava il riferimento locale del documento HTML | Allineamento del titolo a “GB Construction — Ristrutturazioni a Napoli e in Campania” | `frontend/src/brand/identity.js` |

Le modifiche preesistenti alla personalizzazione del marchio in Landing e Navbar sono state preservate. Gli altri file già modificati nel workspace, compresi Campo, TenantContext e configurazione Supabase, non fanno parte di questo intervento.

## Verifiche completate

- **20 test superati in 5 suite**: `LandingFlow.test.jsx`, `Output.test.jsx`, `RenderRequest.test.jsx`, `homeVideoPosters.test.js`, `network.test.js`.
- La nuova suite `frontend/src/landing/LandingFlow.test.jsx` verifica conservazione delle scelte, chiusura del dialogo prima del passaggio alla stima, errore del calendario con tentativo successivo e calendario vuoto. Usa il dialogo Radix reale e risposte API simulate; non effettua prenotazioni reali.
- Build di produzione con `CI=true` completata senza errori di compilazione o lint. Il processo segnala una deprecazione Node di `fs.F_OK`, non un errore applicativo.
- `npm run check:release --prefix frontend` superato: bundle principale compresso **175.520 byte**, inferiore al limite configurato di **184.320 byte**; superati anche i controlli automatici esistenti su metadati, dati strutturati, robots, sitemap e manifest.
- `git diff --check` superato. Git segnala la normale conversione LF/CRLF prevista dal workspace.
- Controllo browser della build locale: prima schermata e sezioni, finestra dei pacchetti, focus sul configuratore, menu mobile e accesso a Progetti, errore del calendario con alternativa di contatto. Nessun invio di moduli o modifica di dati cliente.
- Nella viewport mobile osservata di 355 × 767 CSS pixel non è comparso scorrimento orizzontale. La sequenza iniziale misurava circa 3.453 pixel, coerenti con 4,5 altezze di viewport. La leggibilità del messaggio iniziale è stata ricontrollata dopo l'aggiunta dello sfondo scuro.

Comando usato per le suite mirate, dalla cartella `frontend`:

```powershell
$env:CI='true'
npm.cmd test -- --watchAll=false --runInBand --runTestsByPath src/landing/LandingFlow.test.jsx src/landing/Output.test.jsx src/landing/RenderRequest.test.jsx src/landing/homeVideoPosters.test.js src/lib/network.test.js
```

## Limiti e passaggi ancora necessari

Queste verifiche attestano gli interventi descritti, non la prontezza commerciale dell'intero gestionale.

1. **Preview e backend reale:** dopo una futura pubblicazione in ambiente di prova, verificare l'intero percorso dalla richiesta alla sua ricezione, alla notifica e alla comparsa in dashboard. Il server statico locale non espone il backend: ha permesso di verificare lo stato di errore del calendario, non una prenotazione riuscita reale.
2. **Velocità:** non è stato misurato un miglioramento percentuale dei Core Web Vitals. Servono misure sul deploy effettivo e su rete/dispositivi rappresentativi. Il budget JavaScript superato non certifica da solo LCP, INP o tempi di caricamento delle immagini della sequenza.
3. **SEO locale e vecchio sito:** il titolo e i controlli statici sono verificati. Restano da riconciliare gli URL del vecchio sito, gli eventuali redirect e le future pagine servizio/località prima della riattivazione del dominio. Non è stato svolto un nuovo confronto completo con il vecchio sito in questo intervento.
4. **Contenuti commerciali:** quantità di cantieri/clienti, testimonianze e riferimenti ai bonus già presenti richiedono conferma del titolare prima della consegna; non sono stati inventati o aggiornati con nuove affermazioni.
5. **Dashboard:** permessi, accesso agli allegati, gestione utenti, coerenza degli indicatori e altri punti dell'audit precedente rimangono nel piano di stabilizzazione. Non sono stati dichiarati risolti modificando il sito pubblico.
6. **Prodotti replicabili:** Presenza e Gestione sono definiti nei documenti del dossier. Configurazione dei moduli, provisioning, importazione, quote e separazione applicativa descritti nella proposta tecnica sono ancora lavoro da realizzare.

La sospensione del dominio principale è una decisione commerciale del proprietario, non un difetto da correggere con un deploy automatico.
