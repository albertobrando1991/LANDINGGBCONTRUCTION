# Analisi costi AI e pacchetti crediti - GB Construction

Aggiornato: 2026-06-08  
Valuta commerciale: EUR + IVA  
Tasso prudenziale usato per stime provider in USD: 1 USD ~= 0,87 EUR. Le soglie commerciali sotto non sono un ribaltamento al centesimo del costo API: includono variabilita dei provider, retry, fallback, assistenza, manutenzione e valore del servizio.

## 1. Obiettivo

Definire un modello di abbonamento mensile con:

- canone base a partire da 200 EUR/mese + IVA;
- gestione/manutenzione mensile inclusa;
- crediti AI mensili inclusi, non cumulabili e azzerati a fine ciclo;
- pacchetti crediti acquistabili separatamente, cumulabili e con scadenza consigliata;
- prezzo dei crediti coerente con il consumo reale delle funzioni AI presenti nella piattaforma.

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

- `AI_RENDER_MAX_ROOMS=4`: massimo 4 render ambiente per job.
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
| Render ambienti completo | dopo approvazione | fino a 4 immagini/edit | 0,60-1,40 EUR | 1,40-2,80 EUR |
| Testo consigli/report | fine job o download report | 1 Claude text o fallback locale | 0,01-0,06 EUR | 0,05-0,15 EUR |
| PDF report | locale | nessuna API AI se advice gia presente | ~0 EUR | ~0 EUR |

## 5. Costo per scenari

| Scenario | Chiamate esterne previste | Costo vivo normale | Costo prudenziale da usare per margine |
|---|---:|---:|---:|
| Azione staff semplice: suggerimento lead | 1 text | <0,01 EUR | 0,02 EUR |
| Report dashboard | 1 text | <0,01 EUR | 0,02 EUR |
| AI Architect preliminare: analisi + concept 2D, senza render | 1 vision + 1 image | 0,20-0,70 EUR | 0,80-1,80 EUR |
| Approvazione + render completi | 1 top-down + fino a 4 render + 1 testo | 0,80-2,20 EUR | 2,50-5,00 EUR |
| AI Architect completo da zero a report | 1 vision + 6 immagini max + 1 testo | 1,10-3,00 EUR | 3,00-7,00 EUR |
| Rigenerazione 2D | 1 image | 0,15-0,35 EUR | 0,35-0,70 EUR |
| Rigenerazione singolo render | 1 image | 0,15-0,35 EUR | 0,35-0,70 EUR |
| Rigenerazione pacchetto render | 1 top-down + fino a 4 render + testo | 0,80-2,20 EUR | 2,50-5,00 EUR |

Conclusione tecnica: il costo provider puro e' basso rispetto al valore commerciale del lead/progetto. Il rischio reale non e' il costo unitario singolo, ma l'uso incontrollato: molti utenti che caricano planimetrie, rigenerazioni ripetute, fallback multipli o campagne marketing con alto traffico. Per questo serve un sistema a crediti con soglie chiare.

## 6. Definizione credito consigliata

Consiglio di definire commercialmente:

1 credito AI = 1 EUR + IVA di valore listino.

Motivo: e' semplice da spiegare, permette fatturazione chiara e mantiene margine sufficiente anche se i provider cambiano prezzi o se alcune richieste richiedono fallback/retry.

I crediti non vanno presentati come "costo API", ma come unita di utilizzo delle funzioni AI della piattaforma.

## 7. Canone mensile base

### Piano Base - Manutenzione + AI Starter

Prezzo: 200 EUR/mese + IVA

Include:

- gestione tecnica ordinaria mensile;
- monitoraggio base funzionamento sito/piattaforma;
- piccoli interventi ordinari entro un limite mensile da specificare nel contratto, consigliato 1 ora/mese;
- 30 crediti AI mensili inclusi;
- crediti inclusi non cumulabili: si azzerano a fine ciclo;
- crediti inclusi consumati prima dei pacchetti acquistati.

Razionale:

- 30 crediti coprono molti usi staff leggeri;
- coprono circa 1 AI Architect preliminare al mese;
- non coprono un flusso completo con render professionali, che deve richiedere un pacchetto crediti separato.

Clausola da inserire:

"Il canone include una dotazione mensile di crediti AI non cumulabili. I crediti inclusi non utilizzati entro la fine del periodo di fatturazione non vengono riportati al mese successivo. I crediti acquistati tramite pacchetti separati restano disponibili fino alla loro scadenza."

## 8. Tariffario consumo crediti

| Azione AI | Crediti consigliati | Note |
|---|---:|---|
| Suggerimento prossima azione lead | 1 | uso staff leggero |
| Insight AI report/dashboard | 2 | uso staff leggero |
| Re-analisi AI dati lead/report complesso | 3 | se in futuro si aggiungono analisi piu lunghe |
| AI Architect preliminare: analisi planimetria + concept 2D | 25 | adatto come output iniziale lead |
| Approvazione + pacchetto render completo | 45 | top-down + fino a 4 render + testo/report |
| AI Architect completo da zero a report/render | 70 | scenario end-to-end |
| Rigenerazione 2D | 15 | una nuova immagine/edit |
| Rigenerazione singolo render | 12 | una nuova immagine/edit |
| Rigenerazione pacchetto render | 40 | top-down + fino a 4 render |
| Download/rigenerazione report PDF con advice mancante | 5 | solo se genera testo AI nuovo |

Regola commerciale consigliata:

- se il provider fallisce e l'utente non riceve un output utile, non scalare crediti al cliente;
- loggare comunque il costo interno del tentativo fallito;
- se viene consegnato un fallback locale/deterministico valido, scalare una tariffa ridotta solo se dichiarato nel contratto, ad esempio 5-10 crediti;
- per semplicita iniziale, scalare solo output consegnati e approvati dal sistema.

## 9. Pacchetti crediti acquistabili

| Pacchetto | Prezzo | Costo medio credito | Uso tipico |
|---|---:|---:|---|
| Starter 100 | 100 EUR + IVA | 1,00 EUR | 1 job completo AI Architect + usi staff |
| Growth 250 | 230 EUR + IVA | 0,92 EUR | 3 job completi circa, oppure molti preliminari |
| Pro 500 | 425 EUR + IVA | 0,85 EUR | uso continuativo con campagne attive |
| Scale 1000 | 800 EUR + IVA | 0,80 EUR | alto traffico o uso commerciale intenso |

Regole pacchetti:

- i pacchetti sono cumulabili;
- scadenza consigliata: 12 mesi dalla data di acquisto;
- consumo dei crediti: prima i 30 crediti mensili inclusi, poi i crediti pacchetto con scadenza piu vicina;
- saldo crediti visibile in area admin;
- invio alert a 20%, 10% e 0% del saldo pacchetto;
- blocco preventivo delle azioni AI costose se il saldo non basta.

## 10. Esempi di consumo per il cliente

Esempio A - mese leggero:

- 12 suggerimenti lead = 12 crediti;
- 3 insight report = 6 crediti;
- totale = 18 crediti;
- coperto dal piano base.

Esempio B - 1 lead con planimetria preliminare:

- AI Architect preliminare = 25 crediti;
- 5 suggerimenti staff = 5 crediti;
- totale = 30 crediti;
- coperto dal piano base, senza accumulo residuo.

Esempio C - 1 progetto completo con render:

- AI Architect preliminare = 25 crediti;
- approvazione + render completi = 45 crediti;
- totale = 70 crediti;
- il piano base copre 30 crediti, servono 40 crediti da pacchetto.

Esempio D - campagna con 5 progetti completi:

- 5 x 70 crediti = 350 crediti;
- consigliato pacchetto Pro 500 a 425 EUR + IVA;
- restano 150 crediti per rigenerazioni, staff e report.

## 11. Margine atteso

Con il tariffario sopra:

- costo vivo prudenziale per job completo: 3-7 EUR;
- ricavo crediti listino per job completo: 70 crediti, quindi 70 EUR prima di eventuale sconto pacchetto;
- ricavo reale con pacchetto Pro 500: 70 x 0,85 = 59,50 EUR;
- margine lordo indicativo su provider: molto alto, ma corretto perche copre manutenzione, controllo, instabilita provider, assistenza cliente, evoluzioni e valore commerciale del lead.

Il punto da non vendere al cliente e': "paghi le API".  
Il punto da vendere e': "hai un sistema AI controllato, con costi prevedibili e senza rischio di consumo illimitato".

## 12. Requisiti tecnici prima di vendere i crediti

Nel codice attuale sono presenti funzioni AI e fallback, ma non risulta ancora un sistema completo di ledger crediti. Prima di contrattualizzare i pacchetti serve implementare:

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
  - 25 crediti al completamento di analisi + 2D;
  - 45 crediti quando vengono approvati/generati i render;
- in caso di errore provider senza output consegnato, non scalare crediti commerciali, ma registrare il costo interno.

## 13. Clausole commerciali da inserire

Testo consigliato:

"Le funzionalita AI della piattaforma consumano crediti in base alla tipologia di elaborazione richiesta. I crediti inclusi nel canone mensile sono utilizzabili solo nel mese di competenza e non sono cumulabili. I pacchetti crediti acquistati separatamente sono cumulabili e validi per 12 mesi dalla data di acquisto. Il fornitore si riserva di aggiornare il listino crediti in caso di variazioni rilevanti dei costi dei provider AI, previo preavviso scritto."

"Le elaborazioni AI hanno natura preliminare e di supporto commerciale/progettuale. Planimetrie, render, suggerimenti e report non sostituiscono verifiche tecniche, rilievi, pratiche edilizie, computi metrici o validazioni professionali."

## 14. Raccomandazione finale

La proposta piu coerente e':

- vendita sito/piattaforma con importo fisso separato;
- canone base 200 EUR/mese + IVA con 30 crediti AI inclusi non cumulabili;
- tariffario AI a crediti, con AI Architect preliminare a 25 crediti e job completo a 70 crediti;
- pacchetti da 100, 250, 500 e 1000 crediti;
- ledger tecnico obbligatorio prima del go-live commerciale del sistema crediti.

Questo modello mantiene basso l'ingresso mensile, evita l'effetto "AI illimitata", protegge dai picchi di utilizzo e rende naturale l'acquisto di pacchetti quando la piattaforma genera piu lead o piu richieste progettuali.
