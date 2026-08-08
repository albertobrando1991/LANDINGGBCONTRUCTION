# Google Stitch integration

La suite ufficiale Google Stitch è installata globalmente in Codex:

- `stitch-design`
- `stitch-build`
- `stitch-utilities`

Il server MCP `stitch` usa il proxy locale in `.stitch/mcp/server.mjs` e legge la chiave esclusivamente dal `.env` ignorato da Git.

## Attivazione

1. Accedere a [Google Stitch](https://stitch.withgoogle.com/).
2. Aprire **Stitch settings > API key > Create key**.
3. Inserire la chiave nel `.env` locale:

   ```dotenv
   STITCH_API_KEY=la_chiave_generata
   ```

4. Riavviare Codex per caricare il nuovo MCP.
5. Verificare chiedendo: `Elenca i miei progetti Stitch`.

## Prima sincronizzazione

Creare o selezionare il progetto **GB Construction — Document & Portal System**, quindi:

1. applicare `.stitch/DESIGN.md` come design system;
2. usare `.stitch/PROMPT.md` per generare le sei schermate iniziali;
3. caricare `backend/assets/document-cover.jpg` e il logo GB soltanto dopo aver verificato il progetto di destinazione;
4. confrontare le schermate Stitch con PDF e applicazione prima di riportare modifiche nel codice.

Non inserire mai la chiave in `frontend`, `DESIGN.md`, `PROMPT.md`, GitHub o nei log.
