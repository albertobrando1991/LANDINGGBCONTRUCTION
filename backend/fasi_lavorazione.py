"""Classificazione deterministica delle voci di computo in fasi di lavorazione.

Nessuna AI, nessun prezzo: la fase deriva dalla famiglia del prezzario ufficiale
(Campania 2026) e, quando la famiglia manca o e generica, da regole testuali
esplicite. Se nulla corrisponde la voce resta "Da classificare": mai indovinare.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

FASE_NON_CLASSIFICATA = 99

# Ordine cronologico di cantiere: guida sia il PDF sia il quadro economico.
FASI: tuple[tuple[int, str], ...] = (
    (5, "Allestimento cantiere e sicurezza"),
    (10, "Indagini e diagnostica"),
    (15, "Demolizioni e rimozioni"),
    (20, "Scavi e movimenti terra"),
    (25, "Strutture e opere murarie"),
    (30, "Coperture e impermeabilizzazioni"),
    (35, "Impianto idrico-sanitario e scarichi"),
    (40, "Impianto antincendio"),
    (45, "Impianto elettrico e speciali"),
    (50, "Ascensori e sollevamento"),
    (55, "Impianto termico e climatizzazione"),
    (60, "Massetti, sottofondi e isolamenti"),
    (65, "Intonaci, cartongesso e controsoffitti"),
    (70, "Pavimenti e rivestimenti"),
    (75, "Serramenti e opere da vetraio"),
    (80, "Tinteggiature e finiture"),
    (85, "Restauro artistico e arredi"),
    (90, "Opere esterne e urbanizzazioni"),
    (92, "Pulizie e consegna"),
    (95, "Noli, trasporti e smaltimenti"),
    (96, "Manodopera in economia"),
    (97, "Forniture e materiali"),
    (FASE_NON_CLASSIFICATA, "Da classificare"),
)

NOME_FASE: dict[int, str] = dict(FASI)
ORDINE_FASE: dict[str, int] = {nome: ordine for ordine, nome in FASI}

# Macro-famiglia del prezzario Campania (testo prima del primo " - ").
MACRO_FASE: dict[str, int] = {
    "OPERE PROVVISIONALI": 5,
    "SONDAGGI E PROVE": 10,
    "OPERE EDILI": 25,
    "RECUPERO": 25,
    "IMPIANTI IDRICO-SANITARI": 35,
    "IMPIANTI DI DISTRIBUZIONE FLUIDI": 35,
    "IMPIANTI ELETTRICI": 45,
    "IMPIANTI DI RISCALDAMENTO E CONDIZIONAMENTO AMBIENTALE": 55,
    "EDILIZIA OSPEDALIERA": 80,
    "RESTAURO": 85,
    "URBANIZZAZIONI": 90,
    "URBANIZZAZIONE": 90,
    "PAESAGGIO NATURALE ED URBANO": 90,
    "ATTREZZATURE": 95,
    "TRASPORTI E MOVIMENTAZIONI": 95,
    "MANO D'OPERA": 96,
    "MATERIALI": 97,
}

# Famiglie il cui contenuto e trasversale: il testo della voce vale piu della famiglia.
MACRO_GENERICHE = frozenset({"MATERIALI", "ATTREZZATURE", "MANO D'OPERA"})

# Solo le famiglie in cui il default della macro sarebbe sbagliato.
FAMIGLIA_FASE: dict[str, int] = {
    "OPERE EDILI - BONIFICA DA ORDIGNI BELLICI": 15,
    "OPERE EDILI - SCAVI E RINTERRI": 20,
    "OPERE EDILI - COPERTURE E OPERE DA LATTONIERE": 30,
    "OPERE EDILI - IMPERMEABILIZZAZIONI": 30,
    "OPERE EDILI - CONDOTTI, CANNE FUMARIE, COMIGNOLI, ASPIRATORI": 30,
    "OPERE EDILI - OPERE DI SOTTOFONDO E MALTE": 60,
    "OPERE EDILI - ISOLAMENTI TERMICI E ACUSTICI": 60,
    "OPERE EDILI - INTONACI": 65,
    "OPERE EDILI - PARETI A SECCO ED ANTINCENDIO": 65,
    "OPERE EDILI - CONTROSOFFITTI": 65,
    "OPERE EDILI - PAVIMENTI": 70,
    "OPERE EDILI - RIVESTIMENTI": 70,
    "OPERE EDILI - MARMI, PIETRE NATURALI E RICOMPOSTE": 70,
    "OPERE EDILI - PORTE, INFISSI, PORTE TAGLIAFUOCO": 75,
    "OPERE EDILI - OPERE DA VETRAIO": 75,
    "OPERE EDILI - OPERE DA PITTORE": 80,
    "RECUPERO - SCAVI, DEMOLIZIONI, RIMOZIONI, TAGLI, CAROTAGGI": 15,
    "RECUPERO - BONIFICA E SMALTIMENTO DI AMIANTO": 15,
    "RECUPERO - RIPARAZIONI DI PORTE ED INFISSI": 75,
    "IMPIANTI DI DISTRIBUZIONE FLUIDI - IMPIANTI ANTINCENDIO": 40,
    "IMPIANTI DI DISTRIBUZIONE FLUIDI - DISTRIBUZIONE AERAULICA": 55,
    "IMPIANTI DI DISTRIBUZIONE FLUIDI - ISOLAMENTI": 55,
    "IMPIANTI ELETTRICI - ASCENSORI": 50,
    "EDILIZIA OSPEDALIERA - PAVIMENTI": 70,
    "EDILIZIA OSPEDALIERA - RIVESTIMENTI MURALI E PARASPIGOLI": 70,
    "RESTAURO - ANALISI PRELIMINARI, CONOSCITIVI E DOCUMENTALI": 10,
    "RESTAURO - DEMOLIZIONI, TAGLI, RIMOZIONI": 15,
    "RESTAURO - MOVIMENTI DI TERRA IN AREE ARCHEOLOGICHE": 20,
    "RESTAURO - CONGLOMERATI": 25,
    "RESTAURO - CONSOLIDAMENTI STATICI": 25,
    "RESTAURO - RESTAURO DI SOLAI E VOLTE": 25,
    "RESTAURO - RESTAURO DI SUPERFICI E PARAMENTI MURARI": 25,
    "RESTAURO - RESTAURO DI TETTI E MANTI DI COPERTURA": 30,
    "RESTAURO - MALTE": 60,
    "RESTAURO - RESTAURO DI SUPERFICI INTONACATE": 65,
    "RESTAURO - RESTAURO DI PAVIMENTI, RIVESTIMENTI, PIETRE NATURALI, MOSAICI": 70,
    "RESTAURO - RESTAURO DI INFISSI": 75,
    "RESTAURO - OPERE DA PITTORE CONNESSE CON GLI INTERVENTI DI RESTAURO": 80,
    "RESTAURO - RESTAURO DI STUCCHI, AFFRESCHI, DECORAZIONI PITTORICHE": 80,
}

# Segnali descrittivi forti che devono vincere sui termini accessori presenti
# nelle descrizioni estese PriMus.
REGOLE_TESTO_PRIORITARIE: tuple[tuple[int, str], ...] = (
    (80, r"tinteggiatur|idropittur|pittura lavabile|fissativ"),
    (45, r"punto presa(?:\s+tv)?|presa sip|punto ethernet"),
    (70, r"posa in opera (?:di )?rivestim\w*"),
)

# Regole testuali per le voci senza famiglia utile (import ACCA, voci libere).
# Ordinate dalla piu specifica alla piu generica: vince la prima che corrisponde.
REGOLE_TESTO: tuple[tuple[int, str], ...] = (
    (5, r"pontegg|trabattell|cavallett|allestiment[oi] del cantiere|recinzione di cantiere|"
        r"oneri (?:della |per la )?sicurezza|apprestament|baraccament"),
    (10, r"\bsondagg|carotagg|prova di laboratorio|indagine (?:geofisica|strutturale)|"
         r"diagnostic|termografi"),
    (15, r"demoliz|rimozion|smontagg|scrostatur|spicconatur|scarnitur|amiant|sverniciatur"),
    (20, r"\bscav[oi]\b|rinterr|reinterr|sbancament|movimento di terra|livellamento del terreno"),
    (25, r"calcestruzz|cemento armato|casseform|\barmatur|pilastr|\btrav[ei]\b|solai|solaio|"
         r"muratur|tramezzatur|architrav|cordol|fondazion|consolidament|cerchiatur|"
         r"assistenza muraria|chiusura tracc|"
         r"micropal|carpenteri"),
    (30, r"guain|impermeabilizz|copertur|lattonier|canna fumaria|comignol|grond|pluvial|"
         r"manto di copertura|\btegol|\bcoppi"),
    (35, r"idraulic|idrico|idro-sanitar|sanitar|scarich|\bscarico\b|tubazion|adduzion|"
         r"\blavabo|\bbidet|piatto doccia|\bvaso\b|cassetta di scarico|"
         r"miscelator|rubinett|\bsifon|\bboiler|scaldacqua|autoclave|contatore idrico|"
         r"montaggio bagno|addolcitor"),
    (40, r"antincendi|\bidrant|sprinkler|estintor|\bnaspo|rivelazione incendi"),
    (45, r"elettric|punto luce|punto presa|quadro (?:elettrico|generale)|\bcav[oi]\b|cavidott|"
         r"corrugat|canalin|interruttor|\bprese\b|citofon|videocitofon|fotovoltaic|"
         r"messa a terra|\btvcc\b|antifurt|domotic|illuminazion|\blampad|plafonier|"
         r"cablagg|centralin|presa sip|ethernet|farett|apparecchi illuminanti"),
    (50, r"ascensor|montascale|piattaforma elevatrice|montacarich"),
    (55, r"climatizz|condizionat|\bsplit\b|caldaia|pompa di calore|radiator|termosifon|"
         r"termoarredo|fan.?coil|ventilconvettor|aeraulic|canalizzat|\bvmc\b|"
         r"ricambio d.aria|riscaldament|pannelli radianti|termoconvettor|bruciator|"
         r"cronotermostat|\btermostat|valvole termostatic"),
    (60, r"massett|sottofond|caldana|vespaio|isolament|cappotto|coibent|barriera al vapore"),
    (65, r"intonac|rasatur|cartongess|controsoffitt|parete a secco|lastre in gesso|stuccatur"),
    (70, r"paviment|rivestim\w*|piastrell|battiscop|\bgres\b|parquet|\bmarmo|"
         r"\bsogli[ae]\b|davanzal|mosaic|klinker|listell"),
    (75, r"serrament|\binfiss|\bport[ea]\b|portoncin|finestr|persian|tapparell|avvolgibil|"
         r"zanzarier|\bvetr[oai]|blindat|cassonett|controtelai"),
    (80, r"tinteggiat|pittur|verniciat|idropittur|\bstucco\b|decorazion|smalt(?:o|atur)|"
         r"velatur|\bprimer\b|fissativ"),
    (90, r"giardin|\bverde\b|piantumaz|aiuol|marciapied|asfalt|bitumat|\bpozzett|fognatur|"
         r"acquedott|pubblica illuminazion|arredo urbano|recinzion|cancell|massicciat"),
    (92, r"puliz|sgomber|consegna dell.immobile"),
    (95, r"trasporto|conferiment|discaric|smaltiment|\bnolo\b|noleggi|\bnoli\b"),
    (96, r"\boperai|manodoper|mano d.opera|in economia"),
)

_REGOLE_COMPILATE: tuple[tuple[int, re.Pattern[str]], ...] = tuple(
    (ordine, re.compile(pattern, re.IGNORECASE)) for ordine, pattern in REGOLE_TESTO
)
_REGOLE_PRIORITARIE_COMPILATE: tuple[tuple[int, re.Pattern[str]], ...] = tuple(
    (ordine, re.compile(pattern, re.IGNORECASE))
    for ordine, pattern in REGOLE_TESTO_PRIORITARIE
)


def _macro(super_categoria: str) -> str:
    return super_categoria.split(" - ")[0].strip().upper()


def _da_famiglia(super_categoria: Optional[str]) -> Optional[int]:
    famiglia = str(super_categoria or "").strip().upper()
    if not famiglia:
        return None
    if famiglia in FAMIGLIA_FASE:
        return FAMIGLIA_FASE[famiglia]
    return MACRO_FASE.get(_macro(famiglia))


def _da_testo(testo: str) -> Optional[int]:
    for ordine, pattern in _REGOLE_PRIORITARIE_COMPILATE:
        if pattern.search(testo):
            return ordine
    for ordine, pattern in _REGOLE_COMPILATE:
        if pattern.search(testo):
            return ordine
    return None


def classifica(
    *,
    super_categoria: Optional[str] = None,
    categoria: Optional[str] = None,
    sub_categoria: Optional[str] = None,
    descrizione: Optional[str] = None,
) -> tuple[int, str]:
    """Ritorna (ordine, nome) della fase. Cascata famiglia -> testo -> non classificata."""
    contesto = " ".join(str(value) for value in (categoria, sub_categoria) if value)
    descrizione_pulita = str(descrizione or "")
    testo = " ".join(value for value in (contesto, descrizione_pulita) if value)
    famiglia = str(super_categoria or "").strip().upper()
    fase_famiglia = _da_famiglia(famiglia)
    generica = (
        not famiglia
        or _macro(famiglia) in MACRO_GENERICHE
        or fase_famiglia is None
    )

    if generica:
        # Negli import ACCA la categoria puo essere disallineata rispetto alla
        # riga corrente. La descrizione della lavorazione e il segnale piu
        # specifico e deve vincere sul contesto ereditato dal PDF.
        ordine = _da_testo(descrizione_pulita) or _da_testo(contesto) or fase_famiglia
    else:
        ordine = fase_famiglia or _da_testo(testo)

    if ordine is None:
        ordine = _da_testo(f"{famiglia} {testo}") or FASE_NON_CLASSIFICATA
    return ordine, NOME_FASE[ordine]


def classifica_voce(voce: dict) -> tuple[int, str]:
    """Adattatore sul dizionario di una voce di computo o di prezzario."""
    return classifica(
        super_categoria=voce.get("super_categoria"),
        categoria=voce.get("categoria"),
        sub_categoria=voce.get("sub_categoria"),
        descrizione=voce.get("descrizione"),
    )


def normalizza_fase(nome: Optional[str]) -> tuple[int, str]:
    """Valida una fase scelta a mano; solleva ValueError se non e in catalogo."""
    pulito = str(nome or "").strip()
    if pulito not in ORDINE_FASE:
        raise ValueError(f"Fase non riconosciuta: {pulito or '(vuota)'}")
    return ORDINE_FASE[pulito], pulito


def _totale(voce: dict) -> float:
    if voce.get("totale") is not None:
        return round(float(voce["totale"]), 2)
    return round(float(voce.get("qta") or 0) * float(voce.get("prezzo_unitario") or 0), 2)


def _chiave_fase(voce: dict) -> tuple[int, str]:
    ordine = voce.get("fase_ordine")
    nome = voce.get("fase")
    if ordine is None and not nome:
        return FASE_NON_CLASSIFICATA, NOME_FASE[FASE_NON_CLASSIFICATA]
    if ordine is None:
        ordine = ORDINE_FASE.get(str(nome), FASE_NON_CLASSIFICATA)
    ordine = int(ordine)
    return ordine, str(nome or NOME_FASE.get(ordine, NOME_FASE[FASE_NON_CLASSIFICATA]))


def raggruppa_per_fase(voci: Iterable[dict]) -> list[dict]:
    """Gruppi ordinati per fase con subtotale e incidenza percentuale."""
    gruppi: dict[int, dict[str, Any]] = {}
    for posizione, voce in enumerate(voci):
        ordine, nome = _chiave_fase(voce)
        gruppo = gruppi.setdefault(
            ordine,
            {"fase_ordine": ordine, "fase": nome, "voci": [], "totale": 0.0, "_pos": posizione},
        )
        gruppo["voci"] = [*gruppo["voci"], voce]
        gruppo["totale"] = round(gruppo["totale"] + _totale(voce), 2)

    complessivo = round(sum(gruppo["totale"] for gruppo in gruppi.values()), 2)
    ordinati = sorted(
        gruppi.values(), key=lambda gruppo: (gruppo["fase_ordine"], gruppo["_pos"])
    )
    return [
        {
            "fase": gruppo["fase"],
            "fase_ordine": gruppo["fase_ordine"],
            "n_voci": len(gruppo["voci"]),
            "totale": gruppo["totale"],
            "incidenza": (
                round(gruppo["totale"] / complessivo * 100, 1) if complessivo else 0.0
            ),
            "voci": gruppo["voci"],
        }
        for gruppo in ordinati
    ]


def raggruppa_per_area(
    voci: Iterable[dict], *, senza_area: str = "Tutto l'immobile"
) -> list[dict]:
    """Stesso quadro economico letto per ambiente invece che per fase."""
    gruppi: dict[str, dict[str, Any]] = {}
    for posizione, voce in enumerate(voci):
        nome = str(voce.get("area") or "").strip() or senza_area
        gruppo = gruppi.setdefault(
            nome, {"area": nome, "voci": [], "totale": 0.0, "_pos": posizione}
        )
        gruppo["voci"] = [*gruppo["voci"], voce]
        gruppo["totale"] = round(gruppo["totale"] + _totale(voce), 2)

    complessivo = round(sum(gruppo["totale"] for gruppo in gruppi.values()), 2)
    ordinati = sorted(gruppi.values(), key=lambda gruppo: gruppo["_pos"])
    return [
        {
            "area": gruppo["area"],
            "n_voci": len(gruppo["voci"]),
            "totale": gruppo["totale"],
            "incidenza": (
                round(gruppo["totale"] / complessivo * 100, 1) if complessivo else 0.0
            ),
            "voci": gruppo["voci"],
        }
        for gruppo in ordinati
    ]


def fasi_presenti(voci: Iterable[dict]) -> set[int]:
    return {_chiave_fase(voce)[0] for voce in voci}
