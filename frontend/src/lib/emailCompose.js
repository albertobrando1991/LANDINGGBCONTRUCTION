// Apertura globale del compose email staff: l'icona email di un lead chiama
// openEmailCompose({ leadId, email, nome }); un <EmailComposeModal/> montato
// nel layout dashboard ascolta l'evento e invia via email ufficiale (SMTP/Zimbra).
export const EMAIL_COMPOSE_EVENT = "gb:open-email";

export function openEmailCompose(detail = {}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EMAIL_COMPOSE_EVENT, { detail }));
}
