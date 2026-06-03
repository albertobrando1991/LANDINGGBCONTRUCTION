"""GB Construction - Servizio AI per suggerimenti commerciali e insight report."""
import asyncio
import os
import uuid

import requests

MODEL_PROVIDER = "openai"
MODEL_NAME = os.getenv("SALES_AI_MODEL", "gpt-4o")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or os.getenv("APIKEY_OPENAI") or ""


def _ai_available() -> bool:
    return bool(_openai_api_key())


def _fallback_next_action() -> str:
    return (
        "Contatta il cliente via WhatsApp entro 2 ore, richiamando metratura, zona e soluzione scelta. "
        "Proponi subito un sopralluogo gratuito con due fasce orarie concrete."
    )


def _fallback_insights() -> str:
    return (
        "Priorita: richiamare i lead nuovi entro 2 ore e fissare sopralluoghi sui contatti con score alto. "
        "Controlla i preventivi in follow-up: sono il punto piu vicino alla conversione."
    )


def _chat_completion(system: str, prompt: str) -> str:
    key = _openai_api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY/APIKEY_OPENAI non configurata")

    response = requests.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "max_tokens": 280,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"].strip()


async def suggest_next_action(lead: dict) -> str:
    if not _ai_available():
        return _fallback_next_action()

    timeline = lead.get("timeline", [])
    eventi = "\n".join(f"- {e.get('ts','')[:10]}: {e.get('testo','')}" for e in timeline[:8]) or "Nessun evento registrato."
    system = (
        "Sei un sales manager esperto di GB Construction, impresa di ristrutturazioni a Napoli. "
        "Dai un consiglio operativo conciso (max 2 frasi, in italiano) sulla prossima azione commerciale "
        "per convertire questo lead. Sii concreto: canale, tempistica, messaggio chiave."
    )
    prompt = (
        f"Lead: {lead.get('nome')} - {lead.get('citta')}\n"
        f"Immobile: {lead.get('tipo_immobile')} {lead.get('mq')}mq, soluzione {lead.get('livello')}\n"
        f"Stato pipeline: {lead.get('status')} | Score: {lead.get('score')}/100\n"
        f"Tempistiche dichiarate: {lead.get('tempistiche')}\n"
        f"Tag: {', '.join(lead.get('tags', []))}\n"
        f"Timeline recente:\n{eventi}\n\n"
        "Qual e' la prossima azione migliore?"
    )
    try:
        return await asyncio.to_thread(_chat_completion, system, prompt)
    except Exception:
        return _fallback_next_action()


async def generate_insights(stats: dict) -> str:
    if not _ai_available():
        return _fallback_insights()

    system = (
        "Sei un analista business di GB Construction. Dai 2-3 insight azionabili e concisi (in italiano) "
        "sui dati del funnel di vendita per migliorare la conversione. Niente preamboli."
    )
    prompt = (
        f"Dati mese corrente:\n"
        f"- Lead ricevuti: {stats.get('lead_ricevuti')}\n"
        f"- Lead qualificati: {stats.get('lead_qualificati')}\n"
        f"- Sopralluoghi fissati: {stats.get('sopralluoghi')}\n"
        f"- Preventivi inviati: {stats.get('preventivi')}\n"
        f"- Contratti chiusi: {stats.get('chiusi_vinti')}\n"
        f"- Lead persi: {stats.get('chiusi_persi')}\n"
        f"- Tasso conversione: {stats.get('conversione')}%\n"
        f"- Valore pipeline aperta: {stats.get('valore_pipeline')} EUR\n"
    )
    try:
        return await asyncio.to_thread(_chat_completion, system, prompt)
    except Exception:
        return _fallback_insights()
