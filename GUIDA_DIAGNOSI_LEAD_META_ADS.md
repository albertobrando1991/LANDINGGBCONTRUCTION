# 🔍 Guida alla Diagnosi e Risoluzione: Lead Meta Ads non Ricevuti nella Dashboard

> **Progetto:** EdilOS / GB Construction  
> **Modulo:** Integrazione Webhook Meta Lead Ads  
> **Endpoint Backend:** `POST /api/webhooks/meta` e `GET /api/integrations/meta/status`  
> **Data:** 11 Agosto 2026  

---

## 🛠️ Checklist di Diagnosi in 6 Passaggi

Se le inserzioni di Meta Lead Ads (Facebook / Instagram) generano contatti ma questi non appaiono nella dashboard di GB Construction, la causa è quasi sempre riconducibile a uno dei 6 punti elencati di seguito.

---

### 1. Inoltro URL Webhook in Vercel (`vercel.json`) — *[GIÀ CORRETTO]*
* **Causa**: Se su Meta Business Manager è stato inserito l'URL senza il prefisso `/api/` (es. `https://gbconstruction.it/webhooks/meta`), Vercel restituisce la pagina HTML del frontend React invece di inoltrare la richiesta al backend Python (`api.gbconstruction.it`).
* **Soluzione Applicata**: Abbiamo aggiornato `vercel.json` aggiungendo la regola di rewrite:
  ```json
  {
    "source": "/webhooks/:path*",
    "destination": "https://api.gbconstruction.it/api/webhooks/:path*"
  }
  ```
* **URL Callback da inserire su Meta**:
  `https://gbconstruction.it/api/webhooks/meta`  
  *(Verify Token: `gb_construction_meta_2026`)*

---

### 2. Sottoscrizione al Modulo `leadgen` sulla Pagina Facebook
* **Causa**: Ricevere la spunta verde di verifica sul Webhook nell'App Meta NON è sufficiente se l'App non è iscritta agli eventi della Pagina Facebook specifica.
* **Come Risolvere**:
  1. Vai su **Meta App Dashboard → Webhooks → Oggetto: Page**.
  2. Assicurati che l'evento **`leadgen`** sia spuntato e sottoscritto.
  3. Vai su **Meta Business Manager → Impostazioni del Business → Integrazioni → Accesso ai Lead**.
  4. Verifica che l'App GB Construction abbia l'assegnazione per accedere ai lead della Pagina Facebook di GB Construction.

---

### 3. Verificare i Permessi del `META_PAGE_ACCESS_TOKEN`
* **Causa**: Quando arriva una notifica di Lead Ads, Meta invia solo l'ID del lead (`leadgen_id`). Il backend chiama poi le Meta Graph API per scaricare nome, telefono ed email. Se il token di pagina non ha i permessi necessari, la chiamata fallisce.
* **Come Risolvere**:
  1. Vai su **[Meta Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken)**.
  2. Incolla il valore di `META_PAGE_ACCESS_TOKEN`.
  3. Verifica che siano presenti i permessi:
     * `leads_retrieval`
     * `pages_show_list`
     * `pages_read_engagement` / `pages_manage_ads`
  4. Verifica che il token non sia scaduto.

---

### 4. Modalità Sviluppo vs Production (Development vs Live)
* **Causa**: Se l'App Meta è in modalità **Sviluppo (Development Mode)**, Meta accetta ed invia solo i lead creati da utenti registrati come Admin/Tester dell'App. I lead reali degli utenti esterni vengono ignorati.
* **Come Risolvere**:
  1. In alto nella Meta App Dashboard, imposta lo switch da **In Sviluppo** a **Live / In Produzione**.
  2. Completa la richiesta di *Accesso Avanzato (Advanced Access)* per la funzionalità `leads_retrieval`.

---

### 5. Recupero degli Eventi Falliti nella Dashboard
* **Funzionalità Backend**: Il backend salva tutti gli eventi webhook ricevuti nel database PostgreSQL/Supabase. Se un evento fallisce (es. per token temporaneamente scaduto), il backend memorizza l'evento come `status: "failed"`.
* **Come Riprovare**:
  È possibile rielaborare tutti i lead falliti chiamando l'endpoint di backend:
  `POST https://api.gbconstruction.it/api/integrations/meta/retry-failed`

---

### 6. Test d'Invio Istantaneo tramite lo Strumento Ufficiale Meta
Per verificare subito se la pipeline dal webhook alla dashboard funziona:
1. Accedi allo **[Strumento di Test per le Inserzioni Lead di Meta](https://developers.facebook.com/tools/lead-ads-testing)**.
2. Seleziona la Pagina Facebook ed il Modulo Lead.
3. Clicca su **Crea Lead (Create Lead)**.
4. Clicca su **Traccia Stato (Track Status)**:
   * Se vedi `STATUS: 200 OK` e `HTTP status code: 200`, apri la dashboard di GB Construction: **il lead apparirà immediatamente nella Inbox dei Lead!**

---

> 📄 **File della guida salvato nel workspace:**  
> [GUIDA_DIAGNOSI_LEAD_META_ADS.md](file:///c:/Users/alber/Desktop/LANDINGGBCONTRUCTION/GUIDA_DIAGNOSI_LEAD_META_ADS.md)
