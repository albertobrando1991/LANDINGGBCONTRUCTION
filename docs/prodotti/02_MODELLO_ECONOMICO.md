# Modello economico — ipotesi verificabili

Data di consultazione delle fonti: 7 ottobre 2026. Valori aziendali ipotetici in euro, al netto delle imposte applicabili. Nessuna fattura cloud, costo del personale o dato di vendita dell'utente è stato fornito. Non è una previsione di utile.

Aprire [il simulatore](simulatore-economico.html) per modificare prezzi, ore, costo orario, acquisizione, assistenza, infrastruttura e numero di clienti. Le ipotesi restano locali al browser; non vengono inviate o salvate automaticamente.

## 1. Prezzi di lavoro

| | Presenza | Gestione |
| --- | ---: | ---: |
| Avvio | 1.900 | 4.900 |
| Canone mensile | 99 | 349 |
| Primo anno, 12 mesi interi | 3.088 | 9.088 |
| Anni successivi, 12 mesi interi | 1.188 | 4.188 |

Prezzi costruiti a partire dal costo del servizio e da validare con offerte pilota. Non sono medie di mercato. Il primo anno qui comprende dodici mensilità complete: un cliente acquisito a ottobre non genera dodici mesi di ricavi nello stesso anno solare.

## 2. Costo di consegna e acquisizione

Costo interno assunto: **40 euro/ora**, comprendente il costo operativo del lavoro impiegato nella consegna. Non è una tariffa di vendita. Nelle ore sono compresi preparazione, configurazione, test, revisioni e formazione del pacchetto standard, non lo sviluppo iniziale del prodotto comune.

| | Presenza | Gestione |
| --- | ---: | ---: |
| Ore per avvio | 26 | 64 |
| Lavoro diretto | 1.040 | 2.560 |
| Altri costi diretti di avvio | 60 | 140 |
| Totale consegna | 1.100 | 2.700 |
| Acquisizione per cliente pagante (CAC) | 250 | 600 |
| Contributo dell'avvio dopo consegna e CAC | **550** | **1.600** |
| Contributo / ricavo di avvio | 28,9% | 32,7% |

CAC = spesa commerciale attribuibile / nuovi clienti paganti; include tempo commerciale e spese del canale, senza duplicarli nei costi fissi. Misurare le ore: con 15 ore extra Presenza perde 600 euro e il contributo dell'avvio diventa negativo. Revisioni senza limite rendono inaffidabile il prezzo standard.

## 3. Costo ricorrente per cliente

| Voce mensile ipotizzata | Presenza | Gestione |
| --- | ---: | ---: |
| Infrastruttura, email, storage, quota dominio/monitoraggio | 20 | 100 |
| Assistenza ordinaria | 0,5 h × 40 = 20 | 1,5 h × 40 = 60 |
| Riserva manutenzione e imprevisti per cliente | 10 | 25 |
| Costo diretto mensile | **50** | **185** |
| Canone | 99 | 349 |
| Contributo mensile | **49** | **164** |
| Contributo / canone | **49,5%** | **47,0%** |

Non è utile netto: mancano costi fissi generali, imposte e recupero dell'investimento iniziale. La riserva per manutenzione ordinaria non sostituisce il budget per sviluppare nuovi moduli. Presenza presuppone allocazione di servizi condivisi ammessi dal fornitore; se si richiedono account e servizi totalmente dedicati, va usato un costo più alto.

Contributo primo anno per cliente (avvio dopo CAC + 12 contributi mensili): Presenza **1.138 euro**, Gestione **3.568 euro**. Non sottrarre il CAC una seconda volta e non confondere questo valore con cassa o utile.

## 4. Tariffe esterne verificate e traduzione nel budget

| Fornitore | Dato osservato nella pagina ufficiale | Trattamento nel modello |
| --- | --- | --- |
| Vercel | Pro da 20 USD/mese; Hobby destinato a uso personale non commerciale | Piano commerciale per il servizio venduto; considerare seat e consumi. Non moltiplicare automaticamente un piano team per ogni sito. [Fonte](https://vercel.com/pricing) |
| Supabase | Pro da 25 USD/mese; 10 USD di credito compute, un'istanza Micro; backup giornalieri con conservazione di 7 giorni indicati nel piano | Il conto effettivo dipende da organizzazioni, progetti e risorse; non equivale a database illimitati a 25 USD. [Fonte](https://supabase.com/pricing) |
| Railway | Pro con minimo mensile di 20 USD e 20 USD di credito d'uso; consumi ulteriori a pagamento | Non sommare due volte minimo e credito. Il backend sempre attivo può superare il minimo. [Fonte](https://railway.com/pricing) |
| Resend | Pro 20 USD/mese per 50.000 email; Free 3.000 email/mese e limite giornaliero | Opzione di recapito da valutare, non prova del provider oggi configurato. Contare domini, volumi e quote per cliente. [Fonte](https://resend.com/pricing) |

Esempio con tutti e quattro i piani a pagamento interamente dedicati a un singolo cliente: minimi indicativi **85 USD/mese**, prima degli extra e delle altre spese. Non è la fattura attuale di GB e non costituisce una conversione in euro. Il budget di 100 euro per Gestione è una riserva di pianificazione da confrontare con cambio, imposte effettivamente sostenute, backup dei file, monitoraggio, traffico e consumi. I prezzi dei fornitori possono cambiare.

Per Presenza non occorre necessariamente il backend gestionale completo né un database operativo dedicato: questa separazione deve essere sviluppata. Il budget di 20 euro non descrive l'architettura attuale installata integralmente per ogni sito.

## 5. Sensibilità all'assistenza e al cloud

| Prodotto / scenario | Cloud | Ore supporto | Riserva | Costo totale | Contributo mensile |
| --- | ---: | ---: | ---: | ---: | ---: |
| Presenza, efficiente | 15 | 0,25 | 8 | 33 | 66 |
| Presenza, base | 20 | 0,50 | 10 | 50 | 49 |
| Presenza, prudente | 35 | 1,50 | 15 | 110 | **-11** |
| Gestione, efficiente | 70 | 0,75 | 20 | 120 | 229 |
| Gestione, base | 100 | 1,50 | 25 | 185 | 164 |
| Gestione, prudente | 160 | 3,00 | 35 | 315 | **34** |

Presenza a 99 euro non sostiene 90 minuti mensili di assistenza con cloud più costoso. Le leve sono standardizzazione, formazione, un perimetro editoriale chiaro o un adeguamento del canone. Gestione rimane positiva nello scenario prudente, ma con poco spazio per i costi generali.

Soglia di prezzo per contributo desiderato: `canone minimo = costo diretto / (1 - percentuale desiderata)`. A costo base, il 50% richiede 100 euro per Presenza e 370 euro per Gestione. Un ricarico del 50% sul costo non produce un margine del 50% sul prezzo.

## 6. Portafoglio e pareggio operativo

Costi fissi aggiuntivi assunti: **1.800 euro/mese** per amministrazione, strumenti comuni e lavoro continuativo sul prodotto non già imputato ai singoli clienti. Da sostituire con un budget reale; non includere qui una seconda volta le stesse ore di assistenza e acquisizione.

| Clienti attivi Presenza / Gestione | Ricavi ricorrenti mensili | Costi diretti | Contributo | Dopo 1.800 di costi fissi |
| --- | ---: | ---: | ---: | ---: |
| 5 / 2 | 1.193 | 620 | 573 | -1.227 |
| 10 / 5 | 2.735 | 1.425 | 1.310 | -490 |
| 20 / 10 | 5.470 | 2.850 | 2.620 | 820 |

Pareggio dei soli ricavi ricorrenti: 37 clienti Presenza oppure 11 Gestione. Con mix di due Presenza ogni Gestione, servono 14 Presenza + 7 Gestione: contributo 1.834 euro/mese. Queste soglie escludono imposte, nuovi costi commerciali e recupero dell'investimento iniziale.

Il ricavo di setup può finanziare la crescita, ma non va contato nel ricavo ricorrente mensile né usato per fingere un pareggio stabile.

## 7. Capacità produttiva

Dieci avvii Presenza e cinque Gestione richiedono **580 ore di consegna**, oltre a vendita e sviluppo comune. A 80 ore mensili effettivamente disponibili per onboarding sono oltre sette mesi di lavoro, non quindici consegne immediate.

Trenta clienti nel mix 20/10 richiedono nel caso base **25 ore mensili di supporto ordinario**, oltre a riserva manutenzione e attività centrali. Misurare picchi e incidenti: la media non garantisce reperibilità.

Obiettivo operativo iniziale: non più di due avvii contemporanei senza capacità aggiuntiva; registrare ore per cliente e motivo del ticket. È una proposta organizzativa, non un limite tecnico già implementato.

## 8. Investimento residuo e cassa

Stima iniziale dopo questa ottimizzazione locale, da raffinare sulle attività tecniche:

| Attività comune | Ore stimate |
| --- | ---: |
| Separazione Presenza, contenuti/configurazione e form autonomo | 32–56 |
| Consolidamento Gestione: accessi, documenti, stati e flussi | 80–136 |
| Provisioning, aggiornamenti, backup, export e collaudi | 40–64 |
| Demo, materiali commerciali e manuali dei due pacchetti | 16–24 |
| Totale comune | **168–280** |

A 40 euro/ora: 6.720–11.200 euro. Con riserva del 25%: **8.400–14.000 euro**. Eventuale adattamento ulteriore per studi tecnici: 48–80 ore, fuori da questo totale e subordinato alla validazione. Queste sono stime di sviluppo, non preventivi di terzi né ore già consuntivate.

Riserva di tre mesi dei costi fissi ipotizzati: 5.400 euro. Fabbisogno indicativo prima degli anticipi clienti: **13.800–19.400 euro**, senza doppio conteggio del lavoro comune già compreso nell'investimento. Domini, campagne straordinarie, imposte e costi non inclusi vanno aggiunti.

Anticipo del 50% del setup: 950 euro Presenza, 2.450 Gestione; è inferiore al costo di consegna base (1.100/2.700). Occorre capitale circolante anche prima di considerare CAC e ritardi. Una formula «zero avvio» richiederebbe finanziare esplicitamente questi costi e il rischio di abbandono: non è inclusa nel lancio.

## 9. Extra e AI

AI fuori dal canone standard. Prima di venderla a consumo misurare costo per richiesta completata, tentativi falliti, rigenerazioni, storage, revisione umana e assistenza. Formula: `prezzo = costo completo / (1 - margine obiettivo)`, con quote, limiti e avvisi implementati lato server. Non attribuire ai crediti un valore monetario basato solo sui token.

Nuove pagine, produzioni media, importazioni complesse e integrazioni hanno un preventivo separato in ore e costi esterni. L'upgrade standard da Presenza a Gestione è proposto a 3.000 euro solo se il sito viene riutilizzato e il perimetro coincide con quello definito.

## 10. Dati da raccogliere nei piloti

Ore effettive di consegna/revisione, costo cloud attribuibile, supporto mensile per cliente, fatture provider, tempo commerciale, clienti paganti per canale, mancati pagamenti e abbandoni. Sostituire ogni ipotesi del simulatore con i dati disponibili; ricalcolare il listino dopo i primi tre avvii e almeno un ciclo mensile di assistenza.
