const FASE_NON_CLASSIFICATA = 99;
const NOME_NON_CLASSIFICATA = "Da classificare";

export function isVoceDaClassificare(voce) {
  const fase = String(voce?.fase || "").trim();
  const hasOrdine =
    voce?.fase_ordine !== undefined &&
    voce?.fase_ordine !== null &&
    voce?.fase_ordine !== "";
  const ordine = hasOrdine ? Number(voce.fase_ordine) : null;
  return (
    !fase ||
    (hasOrdine && ordine === FASE_NON_CLASSIFICATA) ||
    fase.toLocaleLowerCase("it-IT") ===
      NOME_NON_CLASSIFICATA.toLocaleLowerCase("it-IT")
  );
}

export function vociDaClassificare(voci = [], ids = null) {
  if (Array.isArray(ids)) {
    const idSet = new Set(ids.map(String));
    return voci.filter((voce) => idSet.has(String(voce.id)));
  }
  return voci.filter(isVoceDaClassificare);
}

function totaleVoce(voce) {
  if (voce.totale !== undefined && voce.totale !== null)
    return Number(voce.totale);
  return Number(voce.qta || 0) * Number(voce.prezzo_unitario || 0);
}

/**
 * Raggruppa le voci per fase conservando l'indice originale di ogni voce,
 * necessario al riordino che ragiona sulla lista piatta.
 */
export function raggruppaVociPerFase(voci) {
  const gruppi = new Map();
  voci.forEach((voce, index) => {
    const daClassificare = isVoceDaClassificare(voce);
    const ordineOriginale = Number(voce.fase_ordine);
    const ordine = daClassificare
      ? FASE_NON_CLASSIFICATA
      : Number.isFinite(ordineOriginale)
        ? ordineOriginale
        : 0;
    const fase = daClassificare ? NOME_NON_CLASSIFICATA : voce.fase;
    const corrente = gruppi.get(fase) || {
      fase,
      fase_ordine: ordine,
      voci: [],
      totale: 0,
      posizione: index,
    };
    gruppi.set(fase, {
      ...corrente,
      voci: [
        ...corrente.voci,
        { ...voce, __index: index, __posizione: corrente.voci.length + 1 },
      ],
      totale: corrente.totale + totaleVoce(voce),
    });
  });

  const elenco = [...gruppi.values()].sort(
    (a, b) => a.fase_ordine - b.fase_ordine || a.posizione - b.posizione,
  );
  const complessivo = elenco.reduce(
    (somma, gruppo) => somma + gruppo.totale,
    0,
  );
  return elenco.map((gruppo) => ({
    ...gruppo,
    totale: Math.round(gruppo.totale * 100) / 100,
    incidenza: complessivo
      ? Math.round((gruppo.totale / complessivo) * 1000) / 10
      : 0,
  }));
}

export function moveVoceIds(voci, fromIndex, delta) {
  const toIndex = fromIndex + delta;
  if (toIndex < 0 || toIndex >= voci.length) {
    return voci.map((voce) => voce.id);
  }
  const ids = voci.map((voce) => voce.id);
  const [moved] = ids.splice(fromIndex, 1);
  ids.splice(toIndex, 0, moved);
  return ids;
}
