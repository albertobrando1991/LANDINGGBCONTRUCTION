# Proposta commerciale - GB Construction Lead Engine

Documento di lavoro per offerta commerciale in Italia, mercato Campania.
Stime aggiornate a giugno 2026. Importi indicati IVA esclusa, salvo diversa indicazione.

## 1. Sintesi del prodotto

Il progetto non e un semplice sito vetrina. E una piattaforma commerciale per impresa di ristrutturazioni composta da:

- landing pubblica immersiva con video, cantieri, prove sociali e CTA WhatsApp;
- configuratore preventivo in 6 step;
- motore predittivo con 3 pacchetti commerciali: Essenziale, Premium, Luxury;
- dataset interno con 86 voci di capitolato e 18 coefficienti economici;
- acquisizione lead con deduplica email, tracking, score e timeline;
- dashboard staff con login, ruoli, Lead Inbox, scheda lead, pipeline, sopralluoghi, preventivi, cantieri e report;
- AI Architect con upload planimetria, analisi tecnica, concept 2D, approvazione staff, top-down/render, report PDF e quality gate;
- integrazione Meta Lead Ads via webhook;
- notifiche email SMTP per staff e cliente;
- suggerimenti AI commerciali su lead e insight report.

Valore commerciale: il sito lavora come funnel + mini CRM verticale per ristrutturazioni in Campania. Serve a ridurre lead generici, qualificare richieste, alzare la percezione del brand e velocizzare la risposta commerciale.

## 2. Stato tecnico rilevato

Stack:

- frontend React + Tailwind + Framer Motion + shadcn/ui;
- backend FastAPI Python;
- database MongoDB;
- auth JWT con cookie httpOnly;
- deploy previsto: Vercel frontend, Railway backend, MongoDB Atlas/Railway DB;
- asset pubblici locali: circa 885 MB, soprattutto video e frame cantieri.

Verifiche eseguite:

- build frontend: compilazione riuscita;
- test backend: 53 test passati su 78 raccolti; i fallimenti riguardano soprattutto test di integrazione che tentano login su credenziali/API esistenti e creazione lead con email gia usata. Prima del go-live serve collaudo ambiente pulito e reset/seed credenziali.

Punti forti:

- prodotto molto superiore a una landing standard;
- UX coerente con settore construction premium;
- dashboard CRM gia articolata;
- motore preventivi concreto, con voci e coefficienti;
- AI Architect gia integrato con provider, fallback e report;
- integrazione Meta Lead Ads gia predisposta.

Punti da chiudere prima della consegna:

- configurazione produzione completa di dominio, CORS, SMTP, API AI, Meta token;
- revisione credenziali admin e seed utenti;
- privacy/cookie policy e testi GDPR;
- collaudo lead reali da landing, Meta e AI Architect;
- ottimizzazione asset/video o spostamento media pesanti su storage/CDN se il traffico cresce;
- definizione di limiti mensili AI per evitare costi non controllati.

## 3. Costi vivi stimati

Cambio indicativo giugno 2026: 1 EUR circa 1,16 USD, quindi 1 USD circa 0,86 EUR.
Per prudenza commerciale, arrotondare sempre per eccesso e considerare IVA.

### Scenario produzione snello

Adatto ai primi mesi, con traffico locale e lead moderati.

- Vercel Pro frontend: circa 20 USD/mese, quindi 17-20 EUR/mese.
- Railway backend: piano Hobby/Pro e consumo risorse, stimabile 10-35 EUR/mese per backend FastAPI leggero.
- MongoDB Atlas: Flex 8-30 USD/mese oppure M10 dedicato da circa 56,94 USD/mese se si vuole assetto piu production-grade.
- Dominio e DNS: 10-30 EUR/anno se non gia disponibili.
- Email SMTP: 0-15 EUR/mese se si usa posta esistente; 10-25 EUR/mese se serve servizio transazionale esterno.
- Cloudflare R2 per file AI/render, opzionale in fase 1: spesso 0-5 EUR/mese con uso contenuto; utile per non tenere upload/render sul filesystem del backend.

Stima totale costi vivi senza AI pesante: 40-90 EUR/mese.

### Costi AI

Dipendono dai volumi:

- suggerimenti commerciali/report testuali: pochi centesimi per uso con modelli mini;
- analisi planimetria con vision: tipicamente 0,05-0,60 EUR per job, variabile per modello e dimensione file;
- generazione immagini/render: molto variabile. Stima prudente 0,30-2,00 EUR per job con 2D/top-down/render, se ben limitato;
- con 50 job AI/mese: budget prudente 30-100 EUR/mese;
- con 150 job AI/mese: budget prudente 100-300 EUR/mese.

Regola commerciale consigliata: includere nel canone solo una soglia AI limitata e fatturare extra oltre soglia, oppure far pagare le chiavi API direttamente al cliente.

### Advertising

Budget Meta/Google non incluso. In Campania per ristrutturazioni il costo lead reale puo oscillare molto per qualita campagna, zona e offerta. Consiglio di separare sempre:

- gestione tecnica sito/CRM;
- gestione campagne;
- budget ads pagato direttamente dal cliente.

## 4. Valutazione economica del sito

Un sito aziendale professionale in Italia nel 2026 si colloca spesso tra 1.500 e 8.000 EUR; una web app custom con CRM e funzioni avanzate puo superare ampiamente questi valori. Questo progetto, pero, va venduto in Campania con posizionamento competitivo, quindi conviene non prezzarlo come enterprise puro.

Valore tecnico reale se sviluppato da zero:

- landing custom + configuratore: 2.500-4.500 EUR;
- backend + database + auth: 2.000-3.500 EUR;
- dashboard CRM: 3.000-5.000 EUR;
- motore preventivi con voci/capitoli: 1.500-3.000 EUR;
- AI Architect + report + render + workflow: 4.000-8.000 EUR;
- integrazioni Meta/email/deploy/collaudo: 1.500-3.000 EUR.

Valore pieno teorico: 14.500-27.000 EUR.

Prezzo realistico e competitivo per venderlo al cliente locale: 6.900-9.800 EUR.

Sotto i 5.000 EUR si rischia di venderlo come sito vetrina, perdendo margine e svalutando CRM/AI.
Sopra i 12.000 EUR puo diventare piu difficile da chiudere in Campania, salvo cliente gia convinto o pagamento dilazionato.

## 5. Offerta consigliata

### Opzione consigliata: Avvio Completo

Prezzo una tantum: 7.900 EUR + IVA.

Include:

- consegna e personalizzazione piattaforma GB Construction;
- deploy frontend/backend/database;
- configurazione dominio e sottodominio API;
- configurazione SMTP;
- configurazione utenti staff;
- dashboard CRM e pipeline;
- motore preventivi con tre pacchetti;
- AI Architect attivo con soglia di sicurezza;
- report PDF preliminare;
- collegamento Meta Lead Ads se il cliente fornisce accessi Business Manager;
- collaudo finale con 10 lead test;
- mini formazione staff da 90 minuti;
- 30 giorni di assistenza post go-live.

Esclusi:

- budget pubblicitario;
- canoni cloud/AI oltre soglia;
- produzione nuovi video/foto;
- pratiche privacy legali redatte da avvocato/DPO;
- modifiche strutturali non previste.

Margine previsto:

- costi vivi primo mese: circa 50-150 EUR;
- lavoro operativo residuo prima consegna: 20-35 ore;
- prezzo orario implicito netto: adeguato e sostenibile.

## 6. Alternative commerciali

### Opzione Entry - Lancio rapido

4.900 EUR + IVA.

Include landing, configuratore, lead, dashboard base, deploy e SMTP.
AI Architect consegnato in modalita limitata o demo, senza render avanzati garantiti.

Quando usarla: cliente molto sensibile al prezzo.
Rischio: margine piu basso e rischio di aspettative alte sull'AI.

### Opzione Premium AI

9.800 EUR + IVA.

Include tutto Avvio Completo piu:

- ottimizzazione asset/video;
- setup storage R2;
- setup cost cap AI;
- template email piu curati;
- collaudo Meta completo;
- 20 job AI inclusi nel primo mese;
- 2 sessioni formazione staff.

Quando usarla: cliente interessato davvero alla parte AI e lead management.

### Cessione sorgente e diritti estesi

Se il cliente chiede proprieta piena del codice sorgente e riuso esclusivo:

- aggiungere 3.000-5.000 EUR;
- oppure specificare che il prezzo base include licenza d'uso e personalizzazione per GB Construction, non cessione completa di framework, componenti riutilizzabili e know-how.

## 7. Manutenzione mensile

### Piano Base

190 EUR/mese + IVA.

Include:

- monitoraggio uptime leggero;
- aggiornamenti sicurezza ordinari;
- backup/controllo database mensile;
- fino a 1 ora/mese di piccole modifiche;
- supporto via email/WhatsApp in orario lavorativo.

Esclusi costi cloud, AI e campagne.

Adatto se il cliente vuole spendere poco, ma non copre vera crescita operativa.

### Piano Standard consigliato

390 EUR/mese + IVA.

Include:

- tutto il Base;
- fino a 3 ore/mese di modifiche, testi, piccole sezioni, fix e assistenza;
- controllo lead/CRM e deliverability email;
- report mensile sintetico: lead, fonti, conversioni, problemi;
- assistenza su Meta webhook e integrazioni;
- gestione deploy e rollback;
- monitoraggio costi AI;
- priorita risposta entro 1 giorno lavorativo.

Costi vivi cloud/AI: esclusi o riaddebitati a consuntivo.

Questo e il piano consigliato: competitivo per Campania ma con margine corretto.

### Piano Growth

690 EUR/mese + IVA.

Include:

- tutto lo Standard;
- fino a 7 ore/mese di evolutive;
- ottimizzazione conversione landing;
- nuove sezioni/cantieri/testimonianze;
- supporto campagne e tracciamenti;
- call mensile strategica;
- report piu dettagliato.

Budget ads escluso.

## 8. Formula commerciale consigliata

Proposta da presentare:

- Setup e consegna piattaforma: 7.900 EUR + IVA.
- Manutenzione e gestione tecnica: 390 EUR/mese + IVA.
- Costi vivi cloud/AI: a carico cliente, stimati 60-180 EUR/mese nella fase iniziale.
- Budget advertising: escluso, pagato direttamente dal cliente.
- Durata minima manutenzione: 6 mesi.
- Pagamento setup: 40% acconto, 40% a messa online, 20% dopo collaudo entro 15 giorni.

Variante per chiudere piu facilmente:

- Setup scontato lancio: 6.900 EUR + IVA;
- vincolo manutenzione Standard 390 EUR/mese per almeno 12 mesi.

Questa formula protegge il margine: il cliente vede un prezzo iniziale piu accessibile, ma il valore viene recuperato sulla gestione.

## 9. Testo proposta breve per cliente

Oggetto: Proposta piattaforma digitale GB Construction

La soluzione proposta non e un semplice sito web, ma una piattaforma di acquisizione e gestione clienti pensata per imprese di ristrutturazione in Campania.

Il sistema include una landing ad alto impatto visivo, configuratore preventivo, raccolta lead, dashboard commerciale, pipeline CRM, gestione sopralluoghi/preventivi, report e modulo AI Architect per l'analisi preliminare delle planimetrie.

L'obiettivo e trasformare il traffico online in richieste qualificate, ridurre i tempi di risposta e dare allo staff uno strumento unico per seguire ogni cliente dal primo contatto al preventivo.

Investimento di avvio: 7.900 EUR + IVA.
Gestione tecnica mensile consigliata: 390 EUR/mese + IVA.

Sono esclusi budget pubblicitari, canoni di servizi terzi e consumi AI oltre soglia, che saranno rendicontati separatamente.

La proposta include messa online, configurazione tecnica, collaudo, formazione staff e 30 giorni di assistenza post go-live.

## 10. Fonti principali per costi vivi

- Vercel Pro: https://vercel.com/docs/plans/pro-plan
- Railway pricing: https://docs.railway.com/pricing
- MongoDB pricing: https://www.mongodb.com/pricing
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- OpenAI API pricing: https://openai.com/api/pricing/
- OpenAI GPT-4.1 mini: https://developers.openai.com/api/docs/models/gpt-4.1-mini
- Anthropic Sonnet pricing: https://www.anthropic.com/claude/sonnet
- fal pricing model: https://fal.ai/docs/documentation/model-apis/pricing

