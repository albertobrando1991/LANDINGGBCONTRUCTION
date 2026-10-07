# Pacchetto di rilascio preview

Data: 7 ottobre 2026. Destinazione autorizzata: `origin/develop` e preview privata Vercel. Nessuna promozione a `main` o produzione.

## Trasferimento selettivo

Il lavoro locale iniziale era basato su `main` (`b4f294d`). La preview usa invece `develop` (`135c89d` prima di questo intervento). Il pacchetto è stato preparato in un worktree separato, partendo da `origin/develop`, per preservare le modifiche locali preesistenti ed evitare di importare cambiamenti estranei del backend e della dashboard.

Sono inclusi gli interventi su calendario, configuratore, pacchetti, menu, hero, footer, ancoraggio Progetti e gestione dello scorrimento. Il titolo locale SEO è applicato direttamente in `Landing.jsx`, perché il modulo `brand/identity.js` presente su `main` non esiste nella base `develop`. Logo, accesso Staff e flusso AI già presenti su `develop` sono conservati.

Il dossier e il simulatore sono versionati in `docs/prodotti`: non vengono inseriti nella landing pubblica di GB Construction. Le specifiche dei due prodotti rimangono proposte da realizzare, con costi e prezzi da validare.

## Verifiche sul pacchetto destinato alla preview

- Installazione riproducibile con `npm ci --legacy-peer-deps` dal lockfile di `develop`.
- Suite `LandingFlow.test.jsx`: **4 test superati**, comprendenti conservazione delle scelte, dialogo dei pacchetti, errore del calendario e calendario vuoto.
- Build con `CI=true`: compilazione completata senza errori o warning di lint; deprecazione Node `fs.F_OK` segnalata dal tooling.
- `check:release`: superato, bundle principale **173.502 byte gzip**, budget **184.320 byte**; controlli statici su metadati, privacy analytics e asset di release superati.
- I 20 test e i valori riportati nel rapporto 04 appartengono al precedente collaudo locale su `main`: non sono presentati come suite eseguita su questa base `develop`.

## Procedura di pubblicazione

Il progetto Vercel `gb-construction` è sospeso, con autenticazione richiesta su tutti i deployment. La creazione della preview richiede una finestra temporanea di build protetta, seguita dal ripristino della pausa anche in caso di errore. Le protezioni di accesso non devono essere rimosse.

Il rilascio è concluso solo dopo aver verificato: SHA remoto di `develop`, deployment Vercel `READY` dello stesso SHA, alias della preview, funzionamento del percorso pacchetto → configuratore e produzione ancora sospesa. Lo stato effettivo di questi controlli viene riportato nella consegna del rilascio; questa nota descrive il pacchetto e la procedura, non anticipa l'esito del deploy.
