"""GB Construction - Motore predittivo (7 fasi).

Calcola le tre soluzioni Essenziale / Premium / Luxury a partire
dalla configurazione del cliente, applicando trigger + formule sulle
86 voci standard e i coefficienti GB.
"""
from typing import Any, Dict, List
from predictive_data import COEFFICIENTI, voci_as_dicts


def _normalize_flags(inp: Dict[str, Any]) -> Dict[str, Any]:
    """FASE 1-2: normalizzazione input -> namespace flag per le formule."""
    ambienti = inp.get("ambienti", []) or []
    livello = inp.get("livello", "premium")
    return {
        "mq": float(inp.get("mq", 80) or 80),
        "bagni": int(inp.get("bagni", 1) or 0),
        "camere": int(inp.get("camere", 2) or 0),
        "cucina": bool(inp.get("cucina", True)),
        "soggiorno": bool(inp.get("soggiorno", "Soggiorno" in ambienti or True)),
        "ingresso": bool(inp.get("ingresso", "Ingresso" in ambienti)),
        "balconi": bool(inp.get("balconi", "Balconi/Terrazzi" in ambienti)),
        "redistribuzione": bool(inp.get("redistribuzione", livello in ("premium", "luxury"))),
        "rifacimento_elettrico": bool(inp.get("rifacimento_elettrico", True)),
        "rifacimento_idrico": bool(inp.get("rifacimento_idrico", True)),
        "rifacimento_termico": bool(inp.get("rifacimento_termico", livello != "essenziale")),
        "controsoffitto": bool(inp.get("controsoffitto", livello in ("premium", "luxury"))),
        "clima": inp.get("clima", "predisposizione" if livello != "essenziale" else "no"),
        "infissi": inp.get("infissi", "completo" if livello == "luxury" else "parziale"),
        "forniture_incluse": bool(inp.get("forniture_incluse", livello == "luxury")),
        "livello": livello,
        "coef": COEFFICIENTI,
    }


def _safe_eval(expr: str, ns: Dict[str, Any]) -> Any:
    if expr is None or str(expr).strip() == "":
        return 0
    try:
        return eval(expr, {"__builtins__": {}}, ns)  # noqa: S307 - controlled internal use
    except Exception:
        return 0


def _compute_voci(flags: Dict[str, Any], pu_field: str) -> List[Dict[str, Any]]:
    """FASE 3-4: per ogni voce applica trigger + formula quantità."""
    voci = voci_as_dicts()
    attive = []
    for v in voci:
        if not bool(_safe_eval(v["trigger"], flags)):
            continue
        qty = float(_safe_eval(v["formula_quantita"], flags) or 0)
        if qty <= 0:
            continue
        pu = v.get(pu_field) or v.get("pu_premium") or 0
        totale = round(qty * pu, 2)
        attive.append({
            "id": v["id"],
            "categoria": v["categoria"],
            "voce": v["voce"],
            "u_m": v["u_m"],
            "quantita": round(qty, 2),
            "pu": pu,
            "totale": totale,
        })
    return attive


def _package_from_voci(flags: Dict[str, Any], pu_field: str, mq_band: tuple) -> Dict[str, Any]:
    voci = _compute_voci(flags, pu_field)
    subtotale = sum(v["totale"] for v in voci)
    imprevisti = subtotale * COEFFICIENTI["imprevisti"]
    totale = subtotale + imprevisti

    # Clamp di sicurezza sul costo/mq dentro la banda storica GB
    mq = max(flags["mq"], 1)
    cost_mq = totale / mq
    band_min, band_max = mq_band
    if cost_mq < band_min:
        scale = (band_min * mq) / totale if totale else 1
        totale *= scale
        subtotale *= scale
        imprevisti *= scale
        for v in voci:
            v["totale"] = round(v["totale"] * scale, 2)
    elif cost_mq > band_max:
        scale = (band_max * mq) / totale if totale else 1
        totale *= scale
        subtotale *= scale
        imprevisti *= scale
        for v in voci:
            v["totale"] = round(v["totale"] * scale, 2)

    range_basso = totale * (1 + COEFFICIENTI["range_low"])
    range_alto = totale * (1 + COEFFICIENTI["range_high"])
    return {
        "subtotale": round(subtotale),
        "imprevisti": round(imprevisti),
        "totale": round(totale),
        "range_basso": round(range_basso / 100) * 100,
        "range_alto": round(range_alto / 100) * 100,
        "costo_mq": round(totale / mq),
        "voci": voci,
        "n_voci": len(voci),
    }


def _categorie_riepilogo(voci: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for v in voci:
        c = agg.setdefault(v["categoria"], {"categoria": v["categoria"], "totale": 0, "voci": 0})
        c["totale"] += v["totale"]
        c["voci"] += 1
    out = sorted(agg.values(), key=lambda x: x["totale"], reverse=True)
    for c in out:
        c["totale"] = round(c["totale"])
    return out


def _generate_alerts(flags: Dict[str, Any], voci: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """FASE 7: alert tecnici per il sopralluogo."""
    alerts = []
    if flags["mq"] >= 120:
        alerts.append({"tipo": "warning", "testo": "Immobile ampio (>120 mq): verificare in sopralluogo lo stato di massetti e impianti esistenti."})
    if flags["bagni"] >= 3:
        alerts.append({"tipo": "info", "testo": "Più di 2 bagni: valutare il dimensionamento della colonna di scarico e della produzione ACS."})
    if flags["redistribuzione"]:
        alerts.append({"tipo": "warning", "testo": "Redistribuzione interna prevista: verificare la presenza di muri portanti e l'eventuale necessità di pratiche strutturali."})
    if flags["rifacimento_elettrico"]:
        alerts.append({"tipo": "info", "testo": "Rifacimento elettrico: necessaria nuova certificazione di conformità DM 37/08."})
    if flags["clima"] == "completo":
        alerts.append({"tipo": "info", "testo": "Climatizzazione completa: verificare posizione unità esterne e vincoli condominiali/facciata."})
    if flags["infissi"] == "completo":
        alerts.append({"tipo": "info", "testo": "Sostituzione infissi: possibile accesso a Ecobonus, verificare requisiti di trasmittanza."})
    if not alerts:
        alerts.append({"tipo": "info", "testo": "Nessuna criticità rilevante prevista. Sopralluogo per conferma misure e finiture."})
    return alerts


def calcola_preventivo(inp: Dict[str, Any]) -> Dict[str, Any]:
    flags = _normalize_flags(inp)
    mq = flags["mq"]

    # Essenziale: superficie x range €/mq
    ess_min = round(mq * COEFFICIENTI["essenziale_mq_min"] / 100) * 100
    ess_max = round(mq * COEFFICIENTI["essenziale_mq_max"] / 100) * 100

    # Premium: motore su PU premium
    premium = _package_from_voci(
        {**flags, "forniture_incluse": False},
        "pu_premium",
        (COEFFICIENTI["premium_mq_min"], COEFFICIENTI["premium_mq_max"]),
    )

    # Luxury: motore su PU luxury + forniture attive
    luxury = _package_from_voci(
        {**flags, "forniture_incluse": True},
        "pu_luxury",
        (COEFFICIENTI["luxury_mq_min"], COEFFICIENTI["luxury_mq_max"] + 260),
    )

    alerts = _generate_alerts(flags, premium["voci"])

    return {
        "input": {k: v for k, v in flags.items() if k != "coef"},
        "pacchetti": {
            "essenziale": {
                "range_basso": ess_min,
                "range_alto": ess_max,
                "costo_mq": COEFFICIENTI["essenziale_mq_min"],
                "tempistiche": "60-90 giorni",
                "forniture": False,
            },
            "premium": {
                "range_basso": premium["range_basso"],
                "range_alto": premium["range_alto"],
                "costo_mq": premium["costo_mq"],
                "totale": premium["totale"],
                "tempistiche": "90-120 giorni",
                "forniture": False,
                "dettaglio": premium["voci"],
                "categorie": _categorie_riepilogo(premium["voci"]),
                "n_voci": premium["n_voci"],
            },
            "luxury": {
                "range_basso": luxury["range_basso"],
                "range_alto": luxury["range_alto"],
                "costo_mq": luxury["costo_mq"],
                "totale": luxury["totale"],
                "tempistiche": "120-150 giorni",
                "forniture": True,
                "dettaglio": luxury["voci"],
                "categorie": _categorie_riepilogo(luxury["voci"]),
                "n_voci": luxury["n_voci"],
            },
        },
        "alerts": alerts,
    }


def lead_score(inp: Dict[str, Any], has_files: bool = False) -> int:
    """Lead scoring 1-100 in base ai segnali di calore."""
    score = 40
    tempistiche = (inp.get("tempistiche") or "").lower()
    if "subito" in tempistiche:
        score += 25
    elif "3 mesi" in tempistiche:
        score += 15
    elif "6 mesi" in tempistiche:
        score += 8
    livello = inp.get("livello", "premium")
    if livello == "luxury":
        score += 15
    elif livello == "premium":
        score += 8
    mq = float(inp.get("mq", 80) or 80)
    if mq >= 150:
        score += 8
    elif mq >= 90:
        score += 4
    if has_files:
        score += 12
    if inp.get("redistribuzione"):
        score += 3
    return max(1, min(100, score))
