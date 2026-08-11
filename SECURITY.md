# Sicurezza

## Perimetro di produzione

- Sito pubblico: `https://gbconstruction.it` e `https://www.gbconstruction.it`.
- Applicazione web: `https://app.gbconstruction.it`.
- API: `https://api.gbconstruction.it`.
- Nessun dominio o sottodominio `.alantis.it` è autorizzato per hosting, tenant routing o CORS.

## Configurazione obbligatoria

In produzione il backend rifiuta l'avvio se `JWT_SECRET` non contiene almeno 32 caratteri casuali, se le credenziali amministratore sono mancanti/deboli o se `ENABLE_DEMO_SEED=true`.

Gli account generici creati dalle vecchie routine di seed (`staff@gbconstruction.it` e `operations@gbconstruction.it`) vengono disabilitati. Gli utenti operativi vanno creati dalla dashboard con credenziali personali.

AI Architect e un modulo esclusivamente interno: il frontend pubblico non lo importa e il backend richiede sempre una sessione `admin`, `staff` o `operations` per route, report e file AI. Il servizio cliente "Render personalizzati" usa un intake e un endpoint separati e non avvia automaticamente la pipeline AI.

In produzione `APP_PUBLIC_URL` deve puntare a `https://app.gbconstruction.it`, così i link dashboard nelle email restano nell'applicazione. `CORS_ORIGINS` deve includere sito pubblico, `www` e applicazione; `MAIL_LOGO_URL` deve usare l'asset servito dall'app.

Sul piano Railway Hobby le email vengono inviate tramite API HTTPS Resend: configurare `RESEND_API_KEY` (oppure l'alias storico `API_RESEND`), `MAIL_FROM_EMAIL=info@gbconstruction.it` e `LEAD_NOTIFICATION_EMAIL=info@gbconstruction.it`. Il dominio mittente deve risultare verificato in Resend con SPF e DKIM. Quando la chiave Resend è presente, il backend usa esclusivamente Resend e non tenta SMTP dopo un errore, evitando possibili invii duplicati. SMTP cPanel resta disponibile come fallback per gli ambienti che ne consentono l'uscita.

## Verifiche automatiche

```bash
cd backend
python -m pytest tests -q

cd ../frontend
npm test -- --watchAll=false
npm run build
npm run check:release
npm run audit:runtime
```

`audit:runtime` blocca ogni nuova vulnerabilità nelle dipendenze distribuite al browser. L'unica eccezione corrente è [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) in React Router: riguarda esclusivamente RSC Mode e le server actions. Questo sito usa `BrowserRouter` dichiarativo, non abilita RSC e non espone action React Router. L'eccezione va rimossa appena esiste una release corretta compatibile.

Le segnalazioni della toolchain CRA (`react-scripts`, dev server e strumenti di build) non fanno parte del bundle statico servito in produzione; `react-scripts` è classificato come `devDependency`.

## Segnalazioni

Inviare le segnalazioni a `info@gbconstruction.it` senza includere dati personali o credenziali reali.
