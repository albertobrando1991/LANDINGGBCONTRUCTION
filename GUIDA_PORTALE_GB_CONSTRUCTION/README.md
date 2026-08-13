# Manuale operativo del portale GB Construction

Guida stilizzata da consegnare al **titolare** e allo **staff**.

Allineata ai flussi attuali (agosto 2026). Spiega, in italiano semplice, le tre aree del sistema:

1. sito pubblico (configuratore → dettagli skippabili → contatto → stima → render €300 opzionali → prenota)
2. dashboard staff (Oggi, Inbox, Pipeline, Preventivi EdilOS, Prezzario, Computi, Cantieri, Personale, SAL, Campo, AI Architect, Report)
3. area riservata del committente (scelta pagamento dal preventivo, poi documenti / SAL / varianti)

## Come aprirla

Dopo il deploy, il link pubblico è:

**https://gbconstruction.it/manuale**

Si apre dal telefono come una pagina normale. Il link è anche nel footer del sito, in Area riservata e in fondo al menu della dashboard.

In locale, dopo `npm start` del frontend: `http://localhost:3000/manuale`

Per aggiornare la copia sul sito dopo una modifica alla guida:

```
node scripts/publish-manuale.cjs
```

La cartella di lavoro resta `GUIDA_PORTALE_GB_CONSTRUCTION/index.html`. Le immagini arrivano da `GB_CONSTRUCTION_SCREENSHOTS_PRESENTAZIONE`.

## PDF selezionabile (consigliato per il telefono)

Il file è già pronto:

`GUIDA_PORTALE_GB_CONSTRUCTION/Manuale_Portale_GB_Construction.pdf`

È un PDF vero, non una scansione: il testo si seleziona, si cerca e si copia. Mandalo su WhatsApp o Drive e si apre da cellulare.

Per rigenerarlo dopo una modifica alla guida:

```
node scripts/export-guida-pdf.cjs
```

Oppure dal browser: Stampa (`Ctrl + P`) → **Salva come PDF** → attiva “Grafica di sfondo”.

## Come usarla in formazione

Tempo consigliato: **50–70 minuti**.

1. Copertina e “tre mondi” (5 minuti)
2. Giornata tipo (5 minuti)
3. Sito pubblico, facendo scorrere il sito vero (10 minuti)
4. Dashboard sezione per sezione, con uno di voi collegato (25 minuti)
5. Render personalizzati: richiesta da €300 sul sito, lavorazione solo da staff (5 minuti)
6. Invito portale dal lead (pagamento) e dal cantiere (documenti) (10 minuti)
7. Percorso dal lead alla consegna (5 minuti)

Lasciare la guida aperta sul telefono o sul PC dello staff per la prima settimana.

## Cosa non è

Non è una presentazione commerciale e non è un manuale tecnico. Per la vendita resta `PRESENTAZIONE_CLIENTE_GB_CONSTRUCTION.md`.

Non descrive più la vecchia AI pubblica che generava da sola 2D/3D/render in pagina. Quel flusso è stato sostituito.
