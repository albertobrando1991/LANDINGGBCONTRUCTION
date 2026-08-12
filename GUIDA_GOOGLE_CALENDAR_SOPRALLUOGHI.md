# Google Calendar aziendale - Sopralluoghi

## Configurazione scelta

- Account e calendario unico: `gbconstructionsrls@gmail.com`
- Fuso orario: `Europe/Rome`
- Il CRM conserva slot, prenotazione, lead e pipeline.
- Google Calendar blocca gli impegni aziendali e mostra gli eventi condivisi.

Gli slot liberi vengono creati come eventi privati e trasparenti. Quando il
cliente prenota, lo stesso evento diventa occupato e contiene i dati necessari
allo staff. L'ID Google e deterministico, quindi un retry non crea duplicati.

## Autorizzazione una tantum

1. Creare o selezionare un progetto in Google Cloud Console.
2. Abilitare **Google Calendar API**.
3. Configurare la schermata consenso OAuth e aggiungere
   `gbconstructionsrls@gmail.com` come utente di test durante la configurazione.
4. Creare un client OAuth 2.0. Per ottenere il refresh token si puo usare un
   redirect controllato dell'applicazione oppure Google OAuth 2.0 Playground
   configurato con il proprio client ID e client secret.
5. Autorizzare esclusivamente questi scope:
   - `https://www.googleapis.com/auth/calendar.events`
   - `https://www.googleapis.com/auth/calendar.freebusy`
6. Scambiare il codice OAuth e conservare il `refresh_token`.
7. Prima dell'uso continuativo portare la schermata consenso in **Produzione**:
   i refresh token di un'app esterna lasciata in modalita Test possono scadere
   dopo sette giorni.

Non inserire client secret o refresh token in file Git, ticket o chat.

## Variabili protette Railway

Impostare sul servizio backend:

```text
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_ID=gbconstructionsrls@gmail.com
GOOGLE_CALENDAR_TIMEZONE=Europe/Rome
GOOGLE_CALENDAR_CLIENT_ID=<oauth-client-id>
GOOGLE_CALENDAR_CLIENT_SECRET=<oauth-client-secret>
GOOGLE_CALENDAR_REFRESH_TOKEN=<oauth-refresh-token>
GOOGLE_CALENDAR_TIMEOUT_SECONDS=10
```

Riavviare il backend dopo la configurazione. La pagina **Sopralluoghi** mostra
il badge `Google Calendar collegato` quando tutte le variabili sono presenti.
Premere una volta **Sincronizza agenda** per portare su Google anche tutti gli
slot futuri gia presenti nel CRM.

## Comportamento e sicurezza

- Una fascia occupata su Google non viene mostrata nella landing.
- La disponibilita viene ricontrollata prima del claim atomico dello slot.
- Se Google non risponde, una nuova prenotazione non viene accettata alla cieca.
- Gli eventi sono `private` e gli slot liberi non contengono dati cliente.
- Google non invia un secondo invito email: la conferma resta gestita dal CRM.
- Se l'integrazione e disabilitata, il calendario interno continua a funzionare.

## Verifica dopo il deploy

1. Aprire Dashboard > Sopralluoghi e verificare il badge verde.
2. Creare uno slot futuro e controllare l'evento trasparente su Google Calendar.
3. Inserire manualmente un evento Google sovrapposto e verificare che lo slot
   non sia prenotabile dalla landing.
4. Prenotare uno slot di prova e verificare evento privato, indirizzo e dati CRM.
5. Segnare il sopralluogo come completato e verificare il titolo aggiornato.
6. Eliminare uno slot libero e verificare la rimozione da Google.
