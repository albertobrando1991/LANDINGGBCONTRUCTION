"""GB Construction - Dataset motore predittivo.

Coefficienti (18 parametri) e database voci standard (86 righe).
Le formule e i trigger sono espressioni valutate in modo sicuro
nell'engine (vedi predictive_engine.py) con il namespace dei flag.
"""

COEFFICIENTI = {
    "punti_elettrici_mq": 1.10,
    "punti_idrico_bagno": 9.5,
    "rivestimenti_bagno": 22.43,
    "tinteggiatura_mq": 4.26,
    "battiscopa_mq": 1.10,
    "controsoffitto_mq": 1.0,
    "faretti_mq": 0.60,
    "sfrido_pavimenti": 0.15,
    "infissi_per_mq": 0.0556,
    "superficie_infisso": 1.68,
    "imprevisti": 0.12,
    "range_low": -0.15,
    "range_high": 0.20,
    # range di riferimento €/mq (dati storici 200+ cantieri GB)
    "essenziale_mq_min": 480,
    "essenziale_mq_max": 600,
    "premium_mq_min": 542,
    "premium_mq_max": 871,
    "premium_mq_median": 616,
    "luxury_mq_min": 786,
    "luxury_mq_max": 841,
    "luxury_mq_median": 824,
}

# id, categoria, voce, u_m, pu_premium, pu_luxury, pu_min, pu_max, trigger, formula_quantita, note
VOCI_STANDARD = [
    # --- Demolizioni e rimozioni ---
    ("VS-001", "Demolizioni", "Demolizione tramezzi e tracce", "m²", 18, 22, 14, 26, "redistribuzione", "mq*0.30", "Solo con redistribuzione interna"),
    ("VS-002", "Demolizioni", "Rimozione pavimenti esistenti", "m²", 11, 13, 9, 15, "True", "mq", "Sempre prevista"),
    ("VS-003", "Demolizioni", "Rimozione rivestimenti bagno", "m²", 12, 14, 9, 16, "bagni > 0", "bagni*coef['rivestimenti_bagno']", "Per ogni bagno"),
    ("VS-004", "Demolizioni", "Rimozione sanitari esistenti", "cad", 35, 40, 28, 48, "bagni > 0", "bagni*3", "WC, bidet, lavabo"),
    ("VS-005", "Demolizioni", "Smontaggio infissi esistenti", "cad", 45, 55, 35, 65, "infissi != 'no'", "mq*coef['infissi_per_mq']", "Solo se sostituzione infissi"),
    ("VS-006", "Demolizioni", "Trasporto e smaltimento a discarica", "m³", 95, 110, 75, 130, "True", "mq*0.12", "Oneri discarica autorizzata"),
    # --- Opere murarie ---
    ("VS-007", "Opere murarie", "Costruzione nuovi tramezzi", "m²", 42, 50, 34, 58, "redistribuzione", "mq*0.25", "Forati + intonaco"),
    ("VS-008", "Opere murarie", "Tracce e ripristini murari", "m", 14, 16, 10, 20, "rifacimento_elettrico or rifacimento_idrico", "mq*1.2", "Per passaggi impianti"),
    ("VS-009", "Opere murarie", "Massetto autolivellante", "m²", 24, 28, 18, 32, "True", "mq", "Sottofondo pavimenti"),
    ("VS-010", "Opere murarie", "Intonaco di ripristino", "m²", 22, 26, 16, 30, "True", "mq*0.80", "Zone interessate dai lavori"),
    ("VS-011", "Opere murarie", "Assistenze murarie agli impianti", "h", 32, 38, 26, 44, "True", "mq*0.50", "Manodopera assistenza"),
    ("VS-012", "Opere murarie", "Formazione nuovi vani porta", "cad", 280, 340, 220, 400, "redistribuzione", "camere", "Architrave + ripristino"),
    # --- Impianto elettrico ---
    ("VS-013", "Impianto elettrico", "Punti luce / presa comandati", "cad", 58, 72, 46, 85, "rifacimento_elettrico", "mq*coef['punti_elettrici_mq']", "1,10 punti/mq"),
    ("VS-014", "Impianto elettrico", "Quadro elettrico generale", "cad", 620, 780, 480, 900, "rifacimento_elettrico", "1", "Centralino a norma CEI"),
    ("VS-015", "Impianto elettrico", "Linea montante e dorsali", "m", 16, 19, 12, 22, "rifacimento_elettrico", "mq*1.5", "Cavi e canaline"),
    ("VS-016", "Impianto elettrico", "Predisposizione TV / rete dati", "cad", 65, 80, 50, 95, "rifacimento_elettrico", "camere+soggiorno", "Punti multimediali"),
    ("VS-017", "Impianto elettrico", "Impianto domotica base", "cad", 1850, 2600, 1400, 3200, "forniture_incluse", "1", "Scenari luce/clima - Luxury"),
    ("VS-018", "Impianto elettrico", "Certificazione conformità elettrica", "cad", 280, 320, 220, 380, "rifacimento_elettrico", "1", "DM 37/08"),
    ("VS-019", "Impianto elettrico", "Videocitofono", "cad", 380, 460, 300, 540, "rifacimento_elettrico", "1", "Monitor a colori"),
    ("VS-020", "Impianto elettrico", "Faretti LED da incasso", "cad", 42, 58, 32, 70, "controsoffitto", "mq*coef['faretti_mq']", "Su controsoffitto"),
    # --- Impianto idrico-sanitario ---
    ("VS-021", "Impianto idrico", "Punti acqua / scarico", "cad", 95, 115, 75, 135, "rifacimento_idrico", "bagni*coef['punti_idrico_bagno'] + (4 if cucina else 0)", "9,5 punti/bagno"),
    ("VS-022", "Impianto idrico", "Colonna di scarico insonorizzata", "m", 48, 58, 38, 68, "rifacimento_idrico", "bagni*3", "Tubazioni silenziate"),
    ("VS-023", "Impianto idrico", "Collettori e allacci", "cad", 180, 220, 140, 260, "rifacimento_idrico", "bagni", "Distribuzione acqua"),
    ("VS-024", "Impianto idrico", "Predisposizione lavatrice", "cad", 110, 130, 85, 150, "rifacimento_idrico", "1", "Carico/scarico"),
    ("VS-025", "Impianto idrico", "Certificazione conformità idrico", "cad", 220, 260, 170, 300, "rifacimento_idrico", "1", "Dichiarazione conformità"),
    ("VS-026", "Impianto idrico", "Impermeabilizzazione box doccia", "cad", 145, 175, 110, 210, "bagni > 0", "bagni", "Guaina + bandelle"),
    ("VS-027", "Impianto idrico", "Collegamento cucina acqua/gas", "cad", 240, 290, 190, 340, "cucina", "1", "Allaccio zona cottura"),
    ("VS-028", "Impianto idrico", "Scarico condensa climatizzazione", "m", 18, 22, 14, 26, "clima != 'no'", "mq*0.20", "Per split"),
    # --- Impianto termico / clima ---
    ("VS-029", "Impianto termico", "Caldaia a condensazione", "cad", 2200, 2800, 1700, 3300, "rifacimento_termico", "1", "Murale + scarico fumi"),
    ("VS-030", "Impianto termico", "Radiatori in alluminio", "cad", 220, 290, 170, 340, "rifacimento_termico", "camere+soggiorno+bagni", "Dimensionati per ambiente"),
    ("VS-031", "Impianto termico", "Tubazioni impianto termico", "m", 22, 27, 17, 32, "rifacimento_termico", "mq*1.2", "Multistrato coibentato"),
    ("VS-032", "Impianto termico", "Cronotermostato wireless", "cad", 180, 240, 140, 290, "rifacimento_termico", "1", "Programmabile"),
    ("VS-033", "Impianto termico", "Predisposizione climatizzazione", "cad", 380, 460, 300, 540, "clima == 'predisposizione' or clima == 'completo'", "camere+soggiorno", "Tubazioni + staffe"),
    ("VS-034", "Impianto termico", "Climatizzatore multisplit inverter", "cad", 850, 1100, 680, 1300, "clima == 'completo'", "camere+soggiorno", "Unità A+++"),
    # --- Pavimenti e rivestimenti ---
    ("VS-035", "Pavimenti", "Fornitura e posa gres porcellanato", "m²", 52, 78, 42, 95, "True", "mq*(1+coef['sfrido_pavimenti'])", "Sfrido 15%"),
    ("VS-036", "Pavimenti", "Posa parquet prefinito", "m²", 78, 115, 62, 140, "forniture_incluse", "camere*14", "Rovere prefinito - Luxury"),
    ("VS-037", "Pavimenti", "Rivestimento bagno", "m²", 48, 72, 38, 88, "bagni > 0", "bagni*coef['rivestimenti_bagno']", "22,43 m²/bagno"),
    ("VS-038", "Pavimenti", "Battiscopa", "m", 9, 13, 7, 16, "True", "mq*coef['battiscopa_mq']", "1,10 m/mq"),
    ("VS-039", "Pavimenti", "Soglie e davanzali interni", "m", 38, 52, 30, 62, "True", "mq*0.10", "Marmo/gres"),
    ("VS-040", "Pavimenti", "Rivestimento cucina", "m²", 46, 68, 36, 82, "cucina", "8", "Paraschizzi zona cottura"),
    ("VS-041", "Pavimenti", "Profili, giunti e finiture", "m", 12, 16, 9, 20, "True", "mq*0.30", "Profili a scomparsa"),
    ("VS-042", "Pavimenti", "Trattamento e pulizia pavimenti", "m²", 6, 8, 4, 10, "True", "mq", "Protezione fine cantiere"),
    # --- Cartongesso e controsoffitti ---
    ("VS-043", "Cartongesso", "Controsoffitto in cartongesso", "m²", 32, 42, 26, 50, "controsoffitto", "mq*coef['controsoffitto_mq']", "Lastre + orditura"),
    ("VS-044", "Cartongesso", "Velette e ribassamenti", "m", 38, 50, 30, 60, "controsoffitto", "mq*0.30", "Per faretti / tende"),
    ("VS-045", "Cartongesso", "Contropareti isolanti", "m²", 34, 44, 27, 52, "redistribuzione", "mq*0.20", "Acustiche/termiche"),
    ("VS-046", "Cartongesso", "Botola di ispezione", "cad", 95, 120, 75, 145, "controsoffitto", "1", "Accesso impianti"),
    ("VS-047", "Cartongesso", "Nicchie e librerie in cartongesso", "cad", 420, 600, 340, 720, "forniture_incluse", "soggiorno", "Design su misura - Luxury"),
    # --- Tinteggiature e finiture ---
    ("VS-048", "Tinteggiature", "Preparazione e rasatura pareti", "m²", 7, 9, 5, 11, "True", "mq*coef['tinteggiatura_mq']", "Stuccatura a gesso"),
    ("VS-049", "Tinteggiature", "Tinteggiatura traspirante", "m²", 8, 11, 6, 13, "True", "mq*coef['tinteggiatura_mq']", "Doppia mano"),
    ("VS-050", "Tinteggiature", "Smalto per ferri e termosifoni", "cad", 45, 58, 35, 70, "True", "camere+soggiorno", "Verniciatura"),
    ("VS-051", "Tinteggiature", "Pittura decorativa parete focus", "m²", 22, 34, 17, 42, "forniture_incluse", "soggiorno*12", "Effetto materico - Luxury"),
    ("VS-052", "Tinteggiature", "Stuccature e finiture d'angolo", "m", 6, 8, 4, 10, "True", "mq*0.50", "Paraspigoli"),
    ("VS-053", "Tinteggiature", "Protezioni e mascherature", "m²", 4, 5, 3, 6, "True", "mq", "Teli e nastri"),
    # --- Infissi e serramenti ---
    ("VS-054", "Infissi", "Fornitura e posa infissi", "m²", 420, 580, 340, 700, "infissi != 'no'", "mq*coef['infissi_per_mq']*coef['superficie_infisso']", "PVC/alluminio taglio termico"),
    ("VS-055", "Infissi", "Zanzariere a rullo", "cad", 95, 130, 75, 155, "infissi == 'completo'", "mq*coef['infissi_per_mq']", "Per finestra"),
    ("VS-056", "Infissi", "Cassonetti coibentati", "cad", 180, 240, 140, 290, "infissi == 'completo'", "mq*coef['infissi_per_mq']*0.5", "Isolamento termico"),
    ("VS-057", "Infissi", "Davanzali in marmo", "m", 65, 90, 52, 110, "infissi != 'no'", "mq*coef['infissi_per_mq']*1.2", "Soglie esterne"),
    ("VS-058", "Infissi", "Porta blindata ingresso", "cad", 1450, 2100, 1100, 2500, "ingresso", "1", "Classe 3 antieffrazione"),
    ("VS-059", "Infissi", "Tapparelle motorizzate", "cad", 320, 450, 250, 540, "forniture_incluse and infissi == 'completo'", "mq*coef['infissi_per_mq']", "Motore + comando - Luxury"),
    # --- Forniture bagno (Luxury) ---
    ("VS-060", "Forniture bagno", "Sanitari sospesi completi", "cad", 280, 420, 220, 520, "forniture_incluse", "bagni*2", "WC + bidet sospesi"),
    ("VS-061", "Forniture bagno", "Cassetta incasso a parete", "cad", 240, 340, 190, 420, "forniture_incluse", "bagni", "Telaio + placca"),
    ("VS-062", "Forniture bagno", "Piatto doccia + box cristallo", "cad", 680, 980, 540, 1200, "forniture_incluse", "bagni", "Cristallo temperato"),
    ("VS-063", "Forniture bagno", "Mobile bagno sospeso + specchio", "cad", 620, 920, 480, 1100, "forniture_incluse", "bagni", "Top + lavabo integrato"),
    ("VS-064", "Forniture bagno", "Rubinetteria di design", "cad", 180, 280, 140, 340, "forniture_incluse", "bagni*3", "Miscelatori premium"),
    ("VS-065", "Forniture bagno", "Termoarredo scaldasalviette", "cad", 320, 460, 250, 560, "forniture_incluse", "bagni", "Elettrico/idraulico"),
    ("VS-066", "Forniture bagno", "Set accessori bagno", "cad", 180, 280, 140, 340, "forniture_incluse", "bagni", "Porta-asciugamani, ecc."),
    # --- Forniture cucina (Luxury) ---
    ("VS-067", "Forniture cucina", "Predisposizione cucina su misura", "a corpo", 1200, 1900, 950, 2300, "forniture_incluse and cucina", "1", "Coordinamento fornitore"),
    ("VS-068", "Forniture cucina", "Top cucina in quarzo", "m", 320, 480, 250, 580, "forniture_incluse and cucina", "4", "Lavorazione su misura"),
    ("VS-069", "Forniture cucina", "Elettrodomestici da incasso", "cad", 3200, 4800, 2600, 5800, "forniture_incluse and cucina", "1", "Set completo classe A"),
    # --- Illuminazione (Luxury) ---
    ("VS-070", "Illuminazione", "Corpi illuminanti di design", "cad", 120, 190, 95, 230, "forniture_incluse", "camere+soggiorno+bagni", "Marchi premium"),
    ("VS-071", "Illuminazione", "Strip LED architetturali", "m", 28, 42, 22, 52, "forniture_incluse", "mq*0.40", "Con alimentatori"),
    ("VS-072", "Illuminazione", "Lampade a sospensione living", "cad", 280, 420, 220, 520, "forniture_incluse", "soggiorno+ (1 if cucina else 0)", "Design - Luxury"),
    # --- Porte interne (Luxury) ---
    ("VS-073", "Porte interne", "Porte interne laccate/filomuro", "cad", 380, 620, 300, 760, "forniture_incluse", "camere+soggiorno+bagni", "Premium - Luxury"),
    ("VS-074", "Porte interne", "Porta scorrevole a scomparsa", "cad", 680, 980, 540, 1200, "forniture_incluse and redistribuzione", "1", "Controtelaio incluso"),
    ("VS-075", "Porte interne", "Maniglie e ferramenta design", "cad", 65, 110, 50, 135, "forniture_incluse", "camere+soggiorno+bagni", "Finiture premium"),
    # --- Opere esterne / balconi ---
    ("VS-076", "Opere esterne", "Impermeabilizzazione balconi", "m²", 38, 50, 30, 60, "balconi", "mq*0.15", "Guaina liquida"),
    ("VS-077", "Opere esterne", "Pavimentazione esterna balconi", "m²", 48, 68, 38, 82, "balconi", "mq*0.15", "Gres antigelivo"),
    ("VS-078", "Opere esterne", "Ringhiere e parapetti", "m", 145, 200, 110, 240, "balconi", "mq*0.08", "Ferro/inox"),
    ("VS-079", "Opere esterne", "Ripristino fronte facciata", "m²", 34, 44, 27, 52, "balconi", "mq*0.10", "Rasatura + pittura"),
    # --- Sicurezza e oneri ---
    ("VS-080", "Sicurezza e oneri", "Oneri della sicurezza", "a corpo", 38, 46, 30, 54, "True", "mq*0.50", "DPI e prescrizioni"),
    ("VS-081", "Sicurezza e oneri", "Ponteggi e trabattelli", "gg", 85, 105, 68, 125, "True", "mq*0.10", "Noleggio attrezzature"),
    ("VS-082", "Sicurezza e oneri", "Direzione lavori e coordinamento", "a corpo", 42, 52, 34, 62, "True", "mq*0.60", "Gestione cantiere GB"),
    ("VS-083", "Sicurezza e oneri", "Pratiche edilizie (CILA/SCIA)", "cad", 850, 1100, 680, 1300, "True", "1", "Tecnico abilitato"),
    ("VS-084", "Sicurezza e oneri", "Allestimento cantiere e protezioni", "a corpo", 680, 850, 540, 1000, "True", "1", "Baracche, protezioni"),
    ("VS-085", "Sicurezza e oneri", "Pulizia finale di cantiere", "m²", 5, 7, 4, 9, "True", "mq", "Consegna chiavi in mano"),
    ("VS-086", "Sicurezza e oneri", "Imprevisti tecnici e assistenze", "a corpo", 28, 36, 22, 44, "True", "mq*0.30", "Margine tecnico"),
]


def voci_as_dicts():
    keys = ["id", "categoria", "voce", "u_m", "pu_premium", "pu_luxury",
            "pu_min", "pu_max", "trigger", "formula_quantita", "note"]
    return [dict(zip(keys, row)) for row in VOCI_STANDARD]
