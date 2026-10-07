# Presenza e Gestione — dossier di prodotto

Data: 7 ottobre 2026. Stato: proposta da validare commercialmente; non è un listino già pubblicato né una certificazione di prontezza del software.

## Pubblicazione della preview

Gli interventi al sito sono stati adattati al branch `develop`, conservandone i flussi e senza importare dashboard o backend da `main`. Il rapporto 04 descrive il collaudo locale iniziale; la nota [05 ? Release preview](05_RELEASE_PREVIEW.md) distingue il pacchetto effettivamente pubblicato.

## Decisione proposta

Due offerte: **Presenza**, sito di presentazione e contatto; **Gestione**, lo stesso sito collegato al lavoro interno. Primo mercato: imprese edili e studi tecnici. La versione gestionale per professionisti va validata su incarichi reali prima di venderla come soluzione completa.

| Documento | Contenuto |
| --- | --- |
| [Business e offerta](01_BUSINESS_E_OFFERTA.md) | Destinatari, problemi, pacchetti, limiti, vendita, assistenza, upgrade e validazione |
| [Modello economico](02_MODELLO_ECONOMICO.md) | Prezzi proposti, costi, margini, scenari, capacità produttiva, investimento e fonti |
| [Simulatore economico](simulatore-economico.html) | File HTML autonomo: modificare ipotesi e confrontare i risultati; aprire nel browser |
| [Architettura e sviluppo](03_ARCHITETTURA_E_SVILUPPO.md) | Stato osservato, componenti, isolamento, configurazione, migrazioni, collaudo e roadmap |
| [Ottimizzazione del sito GB](04_OTTIMIZZAZIONE_SITO_GB.md) | Modifiche locali, verifiche e limiti rispetto alla pubblicazione |

I prezzi di lavoro sono **1.900 euro + 99 euro/mese** per Presenza e **4.900 euro + 349 euro/mese** per Gestione. Importi al netto delle imposte applicabili, senza consumi AI inclusi. Sono ipotesi costruite sui costi, non prezzi ricavati da una ricerca di disponibilità a pagare.

## Confini rispetto ai materiali precedenti

Il documento di giugno `PRODOTTO_LANDING_CRM_AI_REPLICABILE.md` resta conservato come materiale precedente. Per questa proposta non si adottano le sue ipotesi di costi azzerati, margine dell'80%, profitto puro dal secondo anno o MongoDB come database corrente. Il codice locale usa React/CRA, FastAPI e Supabase/Postgres; il tempo di assistenza continua a essere un costo anche dopo l'avvio.

Questo dossier non autorizza spese, invii commerciali o pubblicazioni. Le nuove configurazioni di prodotto sono specifiche di sviluppo, non funzioni già implementate. L'ottimizzazione del sito attuale è separata dalla realizzazione dei due pacchetti.
