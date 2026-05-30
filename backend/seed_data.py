"""GB Construction - Dati demo per la dashboard staff."""
from datetime import datetime, timezone, timedelta
from predictive_engine import calcola_preventivo, lead_score

CITTA = ["Napoli", "Caserta", "Salerno", "Pozzuoli", "Casoria", "Aversa",
         "Castellammare di Stabia", "Benevento", "Avellino", "Giugliano in Campania"]
STILI = ["Moderno minimal", "Classico elegante", "Industrial loft", "Contemporaneo caldo"]


def _iso(dt):
    return dt.isoformat()


def build_demo_leads():
    now = datetime.now(timezone.utc)
    seeds = [
        # nome, email, tel, citta, tipo, mq, livello, bagni, camere, tempistiche, stile, origine, status, owner, days_ago, has_files
        ("Francesca Romano", "francesca.romano@email.it", "+39 333 1245678", "Napoli", "appartamento", 95, "luxury", 2, 3, "Subito", "Moderno minimal", "landing", "nuovo", None, 0, True),
        ("Luigi De Luca", "luigi.deluca@email.it", "+39 348 9981234", "Caserta", "villa", 180, "luxury", 3, 4, "Subito", "Contemporaneo caldo", "landing", "nuovo", None, 0, True),
        ("Maria Esposito", "maria.esposito@email.it", "+39 320 5567890", "Salerno", "appartamento", 70, "premium", 1, 2, "Entro 3 mesi", "Classico elegante", "social", "qualificato", "Marco Esposito", 1, False),
        ("Giovanni Coppola", "g.coppola@email.it", "+39 339 7741122", "Pozzuoli", "ufficio", 120, "premium", 2, 0, "Entro 3 mesi", "Industrial loft", "referral", "sopralluogo_fissato", "Marco Esposito", 2, True),
        ("Anna Ferrara", "anna.ferrara@email.it", "+39 347 3398765", "Casoria", "appartamento", 85, "premium", 2, 2, "Entro 6 mesi", "Moderno minimal", "landing", "sopralluogo_fatto", "Antonio Russo", 4, False),
        ("Salvatore Greco", "s.greco@email.it", "+39 334 2218899", "Aversa", "negozio", 60, "essenziale", 1, 0, "Subito", "Industrial loft", "landing", "preventivo_inviato", "Marco Esposito", 7, False),
        ("Carla Rizzo", "carla.rizzo@email.it", "+39 366 5543210", "Napoli", "appartamento", 110, "luxury", 2, 3, "Entro 3 mesi", "Contemporaneo caldo", "social", "preventivo_inviato", "Marco Esposito", 12, True),
        ("Paolo Marino", "paolo.marino@email.it", "+39 329 8876543", "Benevento", "villa", 200, "luxury", 3, 5, "Sto valutando", "Classico elegante", "referral", "in_trattativa", "Antonio Russo", 9, True),
        ("Roberta Conti", "roberta.conti@email.it", "+39 351 1122334", "Avellino", "appartamento", 75, "premium", 1, 2, "Entro 6 mesi", "Moderno minimal", "landing", "follow_up", "Marco Esposito", 6, False),
        ("Davide Galli", "davide.galli@email.it", "+39 340 9988776", "Giugliano in Campania", "capannone", 350, "essenziale", 1, 0, "Entro 3 mesi", "Industrial loft", "landing", "chiuso_vinto", "Antonio Russo", 20, False),
        ("Elena Bruno", "elena.bruno@email.it", "+39 333 4455667", "Castellammare di Stabia", "appartamento", 65, "premium", 1, 2, "Sto valutando", "Classico elegante", "social", "chiuso_perso", "Marco Esposito", 28, False),
        ("Marco Villa", "marco.villa@email.it", "+39 348 7766554", "Napoli", "appartamento", 90, "premium", 2, 3, "Subito", "Contemporaneo caldo", "landing", "nuovo", None, 0, False),
    ]
    docs = []
    for (nome, email, tel, citta, tipo, mq, liv, bagni, camere, temp, stile,
         origine, status, owner, days_ago, has_files) in seeds:
        ambienti = ["Cucina", "Soggiorno", "Ingresso"]
        if bagni:
            ambienti.append("Bagni")
        cfg = {"tipo_immobile": tipo, "mq": mq, "livello": liv, "bagni": bagni,
               "camere": camere, "cucina": True, "ambienti": ambienti,
               "stile": stile, "tempistiche": temp}
        est = calcola_preventivo(cfg)
        score = lead_score(cfg, has_files)
        pkg = est["pacchetti"][liv]
        created = now - timedelta(days=days_ago, hours=2)
        tags = []
        if score >= 75:
            tags.append("Caldo")
        if liv in ("premium", "luxury"):
            tags.append(liv.capitalize())
        if "subito" in temp.lower():
            tags.append("Subito")
        if has_files:
            tags.append("File caricati")
        timeline = [{
            "id": "ev-create", "tipo": "lead_ricevuto",
            "testo": f"Lead ricevuto dalla landing - {tipo} {mq}mq a {citta}",
            "ts": _iso(created),
        }]
        if status not in ("nuovo",):
            timeline.append({"id": "ev-call", "tipo": "chiamata",
                             "testo": "Prima chiamata di qualifica effettuata - esito positivo",
                             "ts": _iso(created + timedelta(days=1))})
        if status in ("preventivo_inviato", "follow_up", "in_trattativa", "chiuso_vinto", "chiuso_perso"):
            timeline.append({"id": "ev-quote", "tipo": "preventivo",
                             "testo": f"Preventivo {liv} inviato via email",
                             "ts": _iso(created + timedelta(days=3))})
        docs.append({
            "nome": nome, "email": email, "telefono": tel, "citta": citta,
            "tipo_immobile": tipo, "mq": mq, "livello": liv, "bagni": bagni,
            "camere": camere, "cucina": True, "ambienti": ambienti, "stile": stile,
            "tempistiche": temp, "origine": origine, "status": status,
            "owner": owner, "score": score, "tags": tags, "has_files": has_files,
            "note_cliente": "",
            "range_basso": pkg["range_basso"], "range_alto": pkg["range_alto"],
            "estimate": est,
            "prossima_azione": "",
            "timeline": list(reversed(timeline)),
            "created_at": _iso(created),
            "last_contact": _iso(created + timedelta(days=min(days_ago, 1))) if status != "nuovo" else _iso(created),
            "status_changed_at": _iso(created + timedelta(days=max(0, days_ago - 2))),
        })
    return docs


def build_demo_cantieri():
    now = datetime.now(timezone.utc)
    return [
        {"cliente": "Davide Galli", "indirizzo": "Via Roma 45, Giugliano in Campania",
         "avanzamento": 65, "milestone": "Posa pavimenti", "milestone_data": _iso(now + timedelta(days=8)),
         "capocantiere": "Antonio Russo", "importo": 142000, "criticita": None,
         "fasi": [{"nome": "Demolizioni", "stato": "completata"}, {"nome": "Impianti", "stato": "completata"},
                  {"nome": "Massetti", "stato": "completata"}, {"nome": "Pavimenti", "stato": "in_corso"},
                  {"nome": "Finiture", "stato": "da_iniziare"}, {"nome": "Consegna", "stato": "da_iniziare"}]},
        {"cliente": "Studio Legale Marino", "indirizzo": "Corso Umberto 12, Napoli",
         "avanzamento": 30, "milestone": "Rifacimento impianti", "milestone_data": _iso(now + timedelta(days=15)),
         "capocantiere": "Antonio Russo", "importo": 98000, "criticita": "Ritardo consegna infissi (+5gg)",
         "fasi": [{"nome": "Demolizioni", "stato": "completata"}, {"nome": "Impianti", "stato": "in_corso"},
                  {"nome": "Massetti", "stato": "da_iniziare"}, {"nome": "Pavimenti", "stato": "da_iniziare"},
                  {"nome": "Finiture", "stato": "da_iniziare"}, {"nome": "Consegna", "stato": "da_iniziare"}]},
        {"cliente": "Famiglia Sorrentino", "indirizzo": "Via Posillipo 88, Napoli",
         "avanzamento": 90, "milestone": "Pulizia finale e consegna", "milestone_data": _iso(now + timedelta(days=3)),
         "capocantiere": "Antonio Russo", "importo": 215000, "criticita": None,
         "fasi": [{"nome": "Demolizioni", "stato": "completata"}, {"nome": "Impianti", "stato": "completata"},
                  {"nome": "Massetti", "stato": "completata"}, {"nome": "Pavimenti", "stato": "completata"},
                  {"nome": "Finiture", "stato": "completata"}, {"nome": "Consegna", "stato": "in_corso"}]},
    ]


DEMO_PROJECTS = [
    {"nome": "Attico Posillipo", "citta": "Napoli", "tipo": "Appartamento 140mq", "stile": "Contemporaneo caldo"},
    {"nome": "Loft Vomero", "citta": "Napoli", "tipo": "Appartamento 95mq", "stile": "Industrial loft"},
    {"nome": "Villa Caserta", "citta": "Caserta", "tipo": "Villa 220mq", "stile": "Classico elegante"},
    {"nome": "Ufficio Centro Direzionale", "citta": "Napoli", "tipo": "Ufficio 160mq", "stile": "Moderno minimal"},
    {"nome": "Appartamento Salerno", "citta": "Salerno", "tipo": "Appartamento 80mq", "stile": "Moderno minimal"},
    {"nome": "Boutique Chiaia", "citta": "Napoli", "tipo": "Negozio 70mq", "stile": "Industrial loft"},
    {"nome": "Casa Pozzuoli", "citta": "Pozzuoli", "tipo": "Appartamento 110mq", "stile": "Contemporaneo caldo"},
    {"nome": "Villa Sorrento", "citta": "Sorrento", "tipo": "Villa 260mq", "stile": "Classico elegante"},
]
