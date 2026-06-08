# Analisi costi AI e pacchetti crediti - GB Construction

Aggiornato: 2026-06-08  
Valuta commerciale: EUR + IVA  
Tasso prudenziale usato per stime provider in USD: 1 USD ~= 0,87 EUR.
Revisione pricing: il margine desiderato sui consumi AI deve essere circa 50% sul costo vivo provider, non un margine premium. I crediti diventano quindi una copertura controllata dei costi AI, non una voce ad alto profitto.

## 1. Obiettivo

Definire un modello di abbonamento mensile con:

- canone base a partire da 200 EUR/mese + IVA;
- gestione/manutenzione mensile inclusa;
- crediti AI mensili inclusi, non cumulabili e azzerati a fine ciclo;
- pacchetti crediti acquistabili separatamente, cumulabili e con scadenza consigliata;
- prezzo dei crediti coerente con il consumo reale delle funzioni AI presenti nella piattaforma;
- margine massimo indicativo del 50% rispetto al costo AI vivo del provider.

## 2. Fonti prezzi e assunzioni

Fonti verificate:

- OpenAI API pricing: https://developers.openai.com/api/docs/pricing
- OpenAI GPT-4o model page: https://developers.openai.com/api/docs/models/gpt-4o
- OpenAI image generation guide: https://developers.openai.com/api/docs/guides/image-generation
- Anthropic pricing: https://claude.com/pricing
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Fal GPT Image 2 pricing: https://fal.ai/models/openai/gpt-image-2/edit
- OpenRouter pricing/FAQ: https://openrouter.ai/pricing

Prezzi rilevanti al 2026-06-08:

| Provider/modello | Uso nel progetto | Prezzo provider rilevante |
|---|---:|---:|
| OpenAI `gpt-4o` | suggerimenti lead e insight dashboard | 2,50 USD/1M token input, 10,00 USD/1M token output |
| Anthropic Claude Sonnet 4/4.6 | analisi vision e testo report, se API Claude diretta e' attiva | 3 USD/1M token input, 15 USD/1M token output |
| Anthropic Claude Opus 4.8 via OpenRouter | fallback/route vision, se configurato | 5 USD/1M token input, 25 USD/1M token output |
| Google Gemini 2.5 Pro via OpenRouter | fallback vision, se configurato | da 1,25 USD/1M input e 10 USD/1M output sotto 200k token |
| OpenAI `gpt-image-2` | generazione/edits immagini 2D, top-down e render | image input 8 USD/1M token, image output 30 USD/1M token, text input 5 USD/1M token |
| Fal `openai/gpt-image-2` | fallback o alternativa immagini | tabella per immagine; high quality ~0,151 USD a 1024x768 e ~0,178 USD a 1024x1536 |

Nota: OpenAI `gpt-image-2` e' tariffato a token immagine/testo, quindi il costo esatto varia per dimensione, qualita, numero di reference image e output token. Per il progetto assumo immagini `high` a `1536x1024` con 1-4 immagini riferimento: costo vivo normale stimato 0,15-0,35 EUR per immagine, costo prudenziale 0,35-0,70 EUR quando si includono retry, fallback, variabilita e arrotondamenti.

## 3. Provider realmente usati dal codice

Dalla verifica del backend:

- `backend/ai_service.py` usa OpenAI Chat Completions per:
  - suggerimento prossima azione lead;
  - insight report dashboard.
- `backend/ai_architect_service.py` usa:
  - Anthropic diretto per analisi vision e testo, quando presente una chiave Claude;
  - OpenRouter come fallback vision;
  - OpenAI Images `gpt-image-2` per immagini se `AI_IMAGE_PROVIDER=openai`;
  - Fal come fallback immagini se configurato;
  - rendering locale/deterministico quando il provider immagini non e' disponibile o quando serve una safe visual.

Impostazioni operative rilevanti:

- `AI_RENDER_MAX_ROOMS_PUBLIC=2`: massimo 2 render ambiente per job pubblico/utente finale.
- `AI_RENDER_MAX_ROOMS_STAFF=4`: massimo 4 render ambiente per job interno staff.
- `AI_ARCHITECT_REQUIRE_REVIEW=true`: i render costosi partono dopo revisione/approvazione, non subito al caricamento.
- `LAYOUT_REGENERATION_LIMIT=1`: la rigenerazione 2D lato utente e' limitata a 1.
- Cache analisi planimetria per file hash: se la stessa planimetria e' gia stata analizzata, la chiamata vision puo non ripetersi.

## 4. Mappa funzioni AI e consumo reale

| Funzione | Dove avviene | Chiamate AI esterne | Costo vivo normale stimato | Costo prudenziale |
|---|---|---:|---:|---:|
| Suggerisci prossima azione lead | dashboard staff | 1 OpenAI text | <0,01 EUR | <0,02 EUR |
| Insight report funnel | dashboard staff | 1 OpenAI text | <0,01 EUR | <0,02 EUR |
| Analisi planimetria AI Architect | upload planimetria | 1 Claude vision o fallback OpenRouter | 0,05-0,35 EUR | 0,40-1,20 EUR |
| Concept 2D / pulizia planimetria | dopo analisi | 1 immagine/edit OpenAI o Fal | 0,15-0,35 EUR | 0,35-0,70 EUR |
| Top-down 3D | dopo approvazione | 1 immagine/edit | 0,15-0,35 EUR | 0,35-0,70 EUR |
| Render singolo ambiente | dopo approvazione | 1 immagine/edit | 0,15-0,35 EUR | 0,35-0,70 EUR |
| Render ambienti completo utente | dopo approvazione | fino a 2 immagini/edit | 0,30-0,70 EUR | 0,70-1,40 EUR |
| Render ambienti completo staff | uso interno dashboard | fino a 4 immagini/edit | 0,60-1,40 EUR | 1,40-2,80 EUR |
| Testo consigli/report | fine job o download report | 1 Claude text o fallback locale | 0,01-0,06 EUR | 0,05-0,15 EUR |
| PDF report | locale | nessuna API AI se advice gia presente | ~0 EUR | ~0 EUR |

## 5. Costo per scenari

Per il listino a margine 50% uso un costo vivo di riferimento, non il massimo prudenziale. Se il ledger rileva costi reali superiori, il sistema deve aggiornare il consumo o segnalare anomalia.

| Scenario | Chiamate esterne previste | Costo vivo riferimento | Prezzo crediti con +50% |
|---|---:|---:|---:|
| Azione staff semplice: suggerimento lead | 1 text | 0,003 EUR | 0,005 EUR |
| Report dashboard | 1 text | 0,007 EUR | 0,010 EUR |
| AI Architect preliminare: analisi + concept 2D, senza render | 1 vision + 1 image | 0,600 EUR | 0,900 EUR |
| Approvazione + render completi utente | 1 top-down + fino a 2 render + 1 testo | 0,955 EUR | 1,450 EUR |
| AI Architect completo utente da zero a report | 1 vision + 4 immagini max + 1 testo | 1,555 EUR | 2,350 EUR |
| Approvazione + render completi staff | 1 top-down + fino a 4 render + 1 testo | 1,650 EUR | 2,500 EUR |
| AI Architect completo staff da zero a report | 1 vision + 6 immagini max + 1 testo | 2,250 EUR | 3,400 EUR |
| Rigenerazione 2D | 1 image | 0,300 EUR | 0,450 EUR |
| Rigenerazione singolo render | 1 image | 0,300 EUR | 0,450 EUR |
| Rigenerazione pacchetto render | 1 top-down + fino a 4 render + testo | 1,650 EUR | 2,500 EUR |

Conclusione tecnica: il costo provider puro e' basso, ma la funzione AI Architect puo essere usata spesso anche dallo staff. Per questo il prezzo a crediti non deve essere premium: deve coprire costo vivo + circa 50% di margine, con saldo, soglie e blocchi per evitare consumo illimitato.

## 6. Definizione credito consigliata

Il modello precedente `1 credito = 1 EUR` e' troppo alto per una logica cost-plus 50%. Per rispettare il vincolo di margine serve usare micro-crediti.

Nuova definizione consigliata:

- 1 credito AI = 0,001 EUR + IVA;
- 1.000 crediti AI = 1 EUR + IVA;
- consumo crediti = costo vivo stimato x 1,5, convertito in crediti;
- arrotondamento consigliato: ai 5 o 10 crediti piu vicini per azioni leggere, ai 50 crediti piu vicini per immagini/render.

Formula:

Crediti scalati = costo_provider_EUR x 1,5 x 1.000

Esempio:

- costo provider stimato: 0,30 EUR;
- prezzo con margine 50%: 0,45 EUR;
- crediti da scalare: 450 crediti.

Questa scala permette di prezzare anche suggerimenti e insight da pochi millesimi senza creare margini eccessivi.

## 7. Canone mensile base

### Piano Base - Manutenzione + AI Starter

Prezzo: 200 EUR/mese + IVA

Include:

- gestione tecnica ordinaria mensile;
- monitoraggio base funzionamento sito/piattaforma;
- piccoli interventi ordinari entro un limite mensile da specificare nel contratto, consigliato 1 ora/mese;
- 30.000 crediti AI mensili inclusi, pari a 30 EUR di valore AI;
- crediti inclusi non cumulabili: si azzerano a fine ciclo;
- crediti inclusi consumati prima dei pacchetti acquistati.

Razionale:

- 30.000 crediti coprono uso staff frequente;
- coprono circa 12 AI Architect completi utente, 8-9 completi staff oppure oltre 30 preliminari al mese, in base al consumo reale;
- il valore AI incluso e' circa 30 EUR/mese, con costo vivo stimato intorno a 20 EUR/mese se utilizzato interamente;
- il canone resta sostenibile perche il margine principale rimane nella manutenzione, non nei crediti AI.

Clausola da inserire:

"Il canone include una dotazione mensile di crediti AI non cumulabili. I crediti inclusi non utilizzati entro la fine del periodo di fatturazione non vengono riportati al mese successivo. I crediti acquistati tramite pacchetti separati restano disponibili fino alla loro scadenza."

## 8. Tariffario consumo crediti

Il tariffario sotto usa un costo vivo di riferimento coerente con il codice attuale e applica circa +50%. Dove il costo reale cambia per token, file molto pesanti o fallback, il ledger deve registrare il costo effettivo e correggere il consumo.

| Azione AI | Costo vivo riferimento | Prezzo con +50% | Crediti consigliati |
|---|---:|---:|---:|
| Suggerimento prossima azione lead | 0,003 EUR | 0,005 EUR | 5 |
| Insight AI report/dashboard | 0,007 EUR | 0,010 EUR | 10 |
| Testo advice/report | 0,055 EUR | 0,080 EUR | 80 |
| Analisi vision planimetria | 0,300 EUR | 0,450 EUR | 450 |
| Generazione/edit immagine 2D | 0,300 EUR | 0,450 EUR | 450 |
| Top-down 3D | 0,300 EUR | 0,450 EUR | 450 |
| Render singolo ambiente | 0,300 EUR | 0,450 EUR | 450 |
| AI Architect preliminare: analisi + concept 2D | 0,600 EUR | 0,900 EUR | 900 |
| Approvazione + render completi utente: top-down + 2 ambienti | 0,955 EUR | 1,450 EUR | 1.450 |
| AI Architect completo utente da zero a report/render | 1,555 EUR | 2,350 EUR | 2.350 |
| Approvazione + render completi staff: top-down + 4 ambienti | 1,650 EUR | 2,500 EUR | 2.500 |
| AI Architect completo staff da zero a report/render | 2,250 EUR | 3,400 EUR | 3.400 |
| Rigenerazione 2D | 0,300 EUR | 0,450 EUR | 450 |
| Rigenerazione singolo render | 0,300 EUR | 0,450 EUR | 450 |
| Rigenerazione pacchetto render | 1,650 EUR | 2,500 EUR | 2.500 |

Nota importante: questi valori sono corretti per un uso frequente interno. Se si decide di vendere AI Architect al cliente finale come servizio premium separato, il prezzo commerciale puo essere diverso, ma non va confuso con il costo-crediti interno richiesto qui.

Regola commerciale consigliata:

- se il provider fallisce e l'utente non riceve un output utile, non scalare crediti al cliente;
- loggare comunque il costo interno del tentativo fallito;
- se viene consegnato un fallback locale/deterministico valido, scalare una tariffa ridotta solo se dichiarato nel contratto, ad esempio 100-200 crediti per un output grafico utile;
- per semplicita iniziale, scalare solo output consegnati e approvati dal sistema.

## 9. Pacchetti crediti acquistabili

| Pacchetto | Prezzo | Costo medio credito | Uso tipico |
|---|---:|---:|---|
| Mini 10.000 | 10 EUR + IVA | 0,001 EUR | circa 4 job completi utente oppure 11 preliminari |
| Starter 25.000 | 25 EUR + IVA | 0,001 EUR | circa 10 job completi utente oppure 27 preliminari |
| Growth 50.000 | 50 EUR + IVA | 0,001 EUR | circa 21 job completi utente oppure 55 preliminari |
| Pro 100.000 | 100 EUR + IVA | 0,001 EUR | circa 42 job completi utente oppure 111 preliminari |
| Scale 250.000 | 250 EUR + IVA | 0,001 EUR | alto utilizzo staff/campagne |

Non consiglio sconti progressivi sui pacchetti, perche il margine e' gia limitato al 50%. Eventuali sconti ridurrebbero troppo la copertura su retry, fallback e oscillazioni provider.

Regole pacchetti:

- i pacchetti sono cumulabili;
- scadenza consigliata: 12 mesi dalla data di acquisto;
- consumo dei crediti: prima i 30.000 crediti mensili inclusi, poi i crediti pacchetto con scadenza piu vicina;
- saldo crediti visibile in area admin;
- invio alert a 20%, 10% e 0% del saldo pacchetto;
- blocco preventivo delle azioni AI costose se il saldo non basta.

## 10. Esempi di consumo per il cliente

Esempio A - mese leggero:

- 100 suggerimenti lead = 500 crediti;
- 20 insight report = 200 crediti;
- totale = 700 crediti, cioe 0,70 EUR di valore AI;
- coperto dal piano base.

Esempio B - uso interno staff frequente:

- 10 AI Architect preliminari = 9.000 crediti;
- 5 job completi utente = 11.750 crediti;
- 100 suggerimenti staff = 500 crediti;
- totale = 21.250 crediti;
- coperto dai 30.000 crediti mensili del piano base.

Esempio C - 1 progetto completo con render:

- AI Architect completo utente = 2.350 crediti;
- valore AI = 2,35 EUR;
- costo vivo provider stimato = circa 1,55 EUR;
- margine lordo stimato = circa 0,80 EUR, quindi circa 50%.

Esempio D - campagna con 20 progetti completi:

- 20 x 2.350 crediti = 47.000 crediti;
- il piano base copre 30.000 crediti;
- extra necessario = 17.000 crediti;
- consigliato pacchetto Starter 25.000 a 25 EUR + IVA.

## 11. Margine atteso

Con il tariffario sopra:

- costo vivo riferimento per job completo utente: circa 1,55 EUR;
- ricavo crediti per job completo utente: 2,35 EUR;
- margine lordo indicativo su provider: circa 0,80 EUR;
- margine percentuale indicativo: circa 51%.

Questo rispetta la richiesta: il credito non diventa una voce troppo onerosa. Il canone copre gestione e manutenzione; i pacchetti coprono principalmente il consumo AI vivo con un margine contenuto.

## 12. Requisiti tecnici prima di vendere i crediti

Nel codice attuale sono presenti funzioni AI e fallback, ma non risulta ancora un sistema completo di ledger crediti. Con un margine limitato al 50%, il ledger diventa obbligatorio: senza misurazione precisa si rischia di sovra-prezzare o sotto-prezzare.

Prima di contrattualizzare i pacchetti serve implementare:

- tabella/collection `ai_credit_balances`;
- tabella/collection `ai_credit_ledger`;
- tabella/collection `ai_usage_events`;
- tracciamento per ogni azione: user/staff, lead/job, funzione, provider, modello, timestamp, output consegnato, crediti scalati;
- tracciamento interno costo stimato: provider, modello, input token, output token, image count, costo stimato EUR;
- due bucket separati:
  - crediti mensili inclusi, con reset a fine ciclo;
  - crediti pacchetto, cumulabili e con scadenza;
- controllo saldo prima delle azioni costose;
- blocco o richiesta acquisto pacchetto se saldo insufficiente;
- pannello admin con saldo, storico movimenti, consumi per funzione e stima costo vivo.

Regola tecnica consigliata:

- per AI Architect completo scalare i crediti per step, non tutti all'inizio:
  - 900 crediti al completamento di analisi + 2D;
  - 1.450 crediti quando vengono approvati/generati i render pubblici con 2 ambienti;
  - 2.500 crediti quando vengono approvati/generati i render staff con 4 ambienti;
- in caso di errore provider senza output consegnato, non scalare crediti commerciali, ma registrare il costo interno.
- dove disponibile, usare il costo reale restituito dal provider invece della tariffa fissa;
- se il costo reale supera del 30% il riferimento, loggare l'anomalia e aggiornare la tabella.

## 13. Clausole commerciali da inserire

Testo consigliato:

"Le funzionalita AI della piattaforma consumano crediti in base alla tipologia di elaborazione richiesta. I crediti inclusi nel canone mensile sono utilizzabili solo nel mese di competenza e non sono cumulabili. I pacchetti crediti acquistati separatamente sono cumulabili e validi per 12 mesi dalla data di acquisto. Il fornitore si riserva di aggiornare il listino crediti in caso di variazioni rilevanti dei costi dei provider AI, previo preavviso scritto."

"Le elaborazioni AI hanno natura preliminare e di supporto commerciale/progettuale. Planimetrie, render, suggerimenti e report non sostituiscono verifiche tecniche, rilievi, pratiche edilizie, computi metrici o validazioni professionali."

## 14. Raccomandazione finale

La proposta piu coerente e':

- vendita sito/piattaforma con importo fisso separato;
- canone base 200 EUR/mese + IVA con 30.000 crediti AI inclusi non cumulabili;
- credito AI come micro-credito: 1.000 crediti = 1 EUR;
- tariffario AI a costo + circa 50%, con AI Architect preliminare a 900 crediti, job completo utente a 2.350 crediti e job completo staff a 3.400 crediti;
- pacchetti da 10.000, 25.000, 50.000, 100.000 e 250.000 crediti;
- ledger tecnico obbligatorio prima del go-live commerciale del sistema crediti.

Questo modello mantiene basso l'ingresso mensile, permette uso interno frequente dello staff, riduce il costo lead pubblico limitando i render utente a 2 ambienti, evita l'effetto "AI illimitata" e mantiene il margine sui provider vicino al 50%, senza trasformare i crediti AI in una voce troppo esosa.
