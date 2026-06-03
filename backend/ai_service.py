"""GB Construction - Servizio AI (Emergent LLM Key).

Funzioni interne: suggerimento prossima azione commerciale e insight report.
"""
import os
import uuid

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except ImportError:
    LlmChat = None
    UserMessage = None

MODEL_PROVIDER = "openai"
MODEL_NAME = "gpt-4o"


def _key() -> str:
    return os.environ["EMERGENT_LLM_KEY"]


def _emergent_available() -> bool:
    return LlmChat is not None and UserMessage is not None and bool(os.environ.get("EMERGENT_LLM_KEY"))


async def suggest_next_action(lead: dict) -> str:
    if not _emergent_available():
        return (
            "Contatta il cliente via WhatsApp entro 2 ore, richiamando metratura, zona e soluzione scelta. "
            "Proponi subito un sopralluogo gratuito con due fasce orarie concrete."
        )

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
    chat = LlmChat(api_key=_key(), session_id=f"lead-{lead.get('id', uuid.uuid4())}",
                   system_message=system).with_model(MODEL_PROVIDER, MODEL_NAME)
    resp = await chat.send_message(UserMessage(text=prompt))
    return resp.strip()


async def generate_insights(stats: dict) -> str:
    if not _emergent_available():
        return (
            "Priorita: richiamare i lead nuovi entro 2 ore e fissare sopralluoghi sui contatti con score alto. "
            "Controlla i preventivi in follow-up: sono il punto piu vicino alla conversione."
        )

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
    chat = LlmChat(api_key=_key(), session_id=f"insights-{uuid.uuid4()}",
                   system_message=system).with_model(MODEL_PROVIDER, MODEL_NAME)
    resp = await chat.send_message(UserMessage(text=prompt))
    return resp.strip()
