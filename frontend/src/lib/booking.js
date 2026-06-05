// Apertura globale del calendario sopralluoghi: ogni bottone "Prenota sopralluogo"
// chiama openBooking(); un singolo <BookingModal/> montato nella pagina ascolta l'evento.
export const BOOKING_EVENT = "gb:open-booking";

export function openBooking(detail = {}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(BOOKING_EVENT, { detail }));
}
