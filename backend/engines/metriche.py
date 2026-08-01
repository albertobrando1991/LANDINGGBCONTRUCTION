"""Metriche strutturate estratte dalla planimetria AI.
NESSUN PREZZO per contratto: solo quantità e confidenze.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MetricheComputo(BaseModel):
    """Quantità estratte dalla planimetria. NESSUN PREZZO, per contratto."""

    mq_calpestabile: float = 0.0
    mq_pavimento: float = 0.0
    mq_rivestimento: float = 0.0
    mq_intonaco: float = 0.0
    ml_tramezzi_demolire: float = 0.0
    ml_tramezzi_nuovi: float = 0.0
    ml_battiscopa: float = 0.0
    n_bagni: int = 0
    n_camere: int = 0
    n_punti_luce: int = 0
    n_punti_presa: int = 0
    n_punti_acqua: int = 0
    n_infissi_interni: int = 0
    n_infissi_esterni: int = 0
    confidenza: dict[str, float] = Field(default_factory=dict)

    @field_validator("confidenza")
    @classmethod
    def _no_price_keys(cls, v: dict[str, float]) -> dict[str, float]:
        forbidden = ("prezzo", "importo", "euro", "costo", "price", "amount")
        for k in v:
            lk = k.lower()
            if any(f in lk for f in forbidden):
                raise ValueError(f"confidenza non può contenere chiavi prezzo: {k}")
        return v


_PRICE_KEYS = ("prezzo", "importo", "euro", "costo", "price", "amount", "totale_euro")


def _f(d: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return default


def _i(d: dict, *keys: str, default: int = 0) -> int:
    return int(round(_f(d, *keys, default=float(default))))


def estrai_metriche(analisi_ai: dict) -> MetricheComputo:
    """Estrae MetricheComputo da un payload di analisi AI (job output / analisi locale)."""
    if not isinstance(analisi_ai, dict):
        return MetricheComputo()

    # supporta sia struttura flat sia nested under metriche / quantities / rooms
    src = dict(analisi_ai)
    for nest in ("metriche", "metrics", "quantities", "boq_metrics"):
        nested = analisi_ai.get(nest)
        if isinstance(nested, dict):
            src = {**src, **nested}

    rooms = analisi_ai.get("rooms") or analisi_ai.get("ambienti") or []
    n_bagni = _i(src, "n_bagni", "bagni", "bathrooms")
    n_camere = _i(src, "n_camere", "camere", "bedrooms")
    if isinstance(rooms, list) and rooms:
        if n_bagni == 0:
            n_bagni = sum(
                1
                for r in rooms
                if isinstance(r, dict)
                and str(r.get("type") or r.get("tipo") or "").lower()
                in ("bagno", "bathroom", "wc")
            )
        if n_camere == 0:
            n_camere = sum(
                1
                for r in rooms
                if isinstance(r, dict)
                and str(r.get("type") or r.get("tipo") or "").lower()
                in ("camera", "bedroom", "letto")
            )

    mq = _f(src, "mq_calpestabile", "mq", "superficie_mq", "floor_area_mq")
    mq_pav = _f(src, "mq_pavimento", "mq_pavimenti", default=mq)
    conf = src.get("confidenza") or src.get("confidence") or {}
    if not isinstance(conf, dict):
        conf = {}
    # strip accidental price confidences
    conf = {
        k: float(v)
        for k, v in conf.items()
        if not any(f in k.lower() for f in _PRICE_KEYS)
    }

    return MetricheComputo(
        mq_calpestabile=mq,
        mq_pavimento=mq_pav,
        mq_rivestimento=_f(src, "mq_rivestimento", "mq_rivestimenti"),
        mq_intonaco=_f(src, "mq_intonaco", "mq_pareti", default=mq * 2.8 if mq else 0),
        ml_tramezzi_demolire=_f(src, "ml_tramezzi_demolire", "ml_demolizioni"),
        ml_tramezzi_nuovi=_f(src, "ml_tramezzi_nuovi", "ml_tramezzi"),
        ml_battiscopa=_f(src, "ml_battiscopa", default=mq * 1.1 if mq else 0),
        n_bagni=n_bagni,
        n_camere=n_camere,
        n_punti_luce=_i(src, "n_punti_luce", "punti_luce", default=int(mq * 1.1) if mq else 0),
        n_punti_presa=_i(src, "n_punti_presa", "punti_presa", default=int(mq * 0.8) if mq else 0),
        n_punti_acqua=_i(src, "n_punti_acqua", "punti_acqua", default=n_bagni * 9 if n_bagni else 0),
        n_infissi_interni=_i(src, "n_infissi_interni", "porte_interne"),
        n_infissi_esterni=_i(src, "n_infissi_esterni", "finestre", "infissi_esterni"),
        confidenza=conf,
    )


def assert_nessun_prezzo(metriche: MetricheComputo) -> None:
    """Guardrail runtime: fallisce se un campo o confidenza puzza di importo."""
    data = metriche.model_dump()
    for k in data:
        if any(f in k.lower() for f in _PRICE_KEYS):
            raise ValueError(f"MetricheComputo non può contenere prezzi: {k}")
