"""Primo rilievo Campo: schede e ambienti modificabili con autosalvataggio."""

from __future__ import annotations

import asyncio
from io import BytesIO
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException
import fitz
from PIL import Image, UnidentifiedImageError

from system_jobs.rilievo_assets import signed_asset_urls, upload_asset

RILIEVO_ROLES = frozenset({"owner", "admin", "staff", "operations"})
RILIEVO_PHOTO_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})
_IMAGE_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def _value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _d(row: asyncpg.Record | dict | None) -> dict | None:
    if row is None:
        return None
    out = {key: _value(value) for key, value in dict(row).items()}
    if isinstance(out.get("misure_extra"), str):
        out["misure_extra"] = json.loads(out["misure_extra"])
    if isinstance(out.get("planimetria_data"), str):
        out["planimetria_data"] = json.loads(out["planimetria_data"])
    return out


def _clean(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _extra_json(misure_extra: list[dict]) -> str:
    return json.dumps(misure_extra, ensure_ascii=False, default=str)


def _validate_photo_paths(
    tenant_id: str, rilievo_id: str, ambiente_client_uuid: str, paths: list[str]
) -> None:
    prefix = f"{tenant_id}/rilievo-{rilievo_id}/" f"ambiente-{ambiente_client_uuid}/"
    if any(not path.startswith(prefix) for path in paths):
        raise HTTPException(
            status_code=400,
            detail="Una o piu foto non appartengono all'ambiente selezionato",
        )


async def _require_rilievo(
    conn: asyncpg.Connection, tenant_id: str, rilievo_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        select * from public.rilievi
        where tenant_id = $1::uuid and id = $2::uuid and archived_at is null
        """,
        tenant_id,
        rilievo_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rilievo non trovato")
    return _d(row)


async def require_rilievo(
    conn: asyncpg.Connection, tenant_id: str, rilievo_id: str
) -> dict:
    return await _require_rilievo(conn, tenant_id, rilievo_id)


def render_pdf_preview(content: bytes) -> bytes:
    if not content or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Il file non e un PDF valido")
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if document.page_count < 1:
                raise HTTPException(
                    status_code=400, detail="La planimetria PDF non contiene pagine"
                )
            page = document.load_page(0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return pixmap.tobytes("png")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="La planimetria PDF non puo essere letta"
        ) from exc


def _verified_image_mime(content: bytes) -> str:
    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > 80_000_000:
                raise HTTPException(
                    status_code=413, detail="Immagine troppo grande da elaborare"
                )
            mime = _IMAGE_MIME_BY_FORMAT.get(str(image.format or "").upper())
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="Immagine non valida") from exc
    if mime not in RILIEVO_PHOTO_MIME:
        raise HTTPException(status_code=415, detail="Formato immagine non supportato")
    return mime


def _safe_asset_filename(filename: str, fallback: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", filename or fallback).strip("-._")
    return (safe or fallback)[:140]


def _photo_asset_prefixes(tenant_id: str, rilievo_id: str) -> tuple[str, str]:
    base = f"{tenant_id}/rilievo-{rilievo_id}/"
    return f"{base}generali/", f"{base}ambiente-"


def validate_asset_paths(
    tenant_id: str, rilievo_id: str, bucket: str, paths: list[str]
) -> None:
    if bucket == "planimetrie":
        prefix = f"{tenant_id}/rilievo-{rilievo_id}/planimetria/"
        valid = all(path.startswith(prefix) and ".." not in path for path in paths)
    elif bucket == "foto-cantiere":
        general_prefix, room_prefix = _photo_asset_prefixes(tenant_id, rilievo_id)
        valid = all(
            ".." not in path
            and (
                path.startswith(general_prefix)
                or (
                    path.startswith(room_prefix)
                    and re.match(
                        rf"^{re.escape(room_prefix)}[0-9a-f-]{{36}}/[^/]+$",
                        path,
                        re.IGNORECASE,
                    )
                )
            )
            for path in paths
        )
    else:
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="Asset non appartenente al rilievo")


async def salva_asset(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    *,
    tipo: str,
    filename: str,
    content_type: str,
    content: bytes,
    ambiente_client_uuid: Optional[str] = None,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    if not content:
        raise HTTPException(status_code=400, detail="Il file e vuoto")
    declared_mime = (content_type or "").lower().split(";", 1)[0]
    if tipo == "planimetria":
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="La planimetria supera il limite di 25 MB"
            )
        if declared_mime == "application/pdf":
            render_pdf_preview(content)
            mime = declared_mime
            extension = "pdf"
        else:
            mime = _verified_image_mime(content)
            extension = mime.split("/", 1)[1].replace("jpeg", "jpg")
        bucket = "planimetrie"
        safe_name = _safe_asset_filename(filename, f"planimetria.{extension}")
        path = (
            f"{tenant_id}/rilievo-{rilievo_id}/planimetria/"
            f"originale-{uuid4()}-{safe_name}"
        )
    elif tipo == "planimetria_preview":
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="La preview supera il limite di 15 MB"
            )
        mime = _verified_image_mime(content)
        if mime != "image/png":
            raise HTTPException(status_code=415, detail="La preview deve essere PNG")
        bucket = "planimetrie"
        path = f"{tenant_id}/rilievo-{rilievo_id}/planimetria/" f"preview-{uuid4()}.png"
    elif tipo in {"foto_generale", "foto_ambiente"}:
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="La foto supera il limite di 15 MB"
            )
        mime = _verified_image_mime(content)
        extension = mime.split("/", 1)[1].replace("jpeg", "jpg")
        bucket = "foto-cantiere"
        if tipo == "foto_ambiente":
            try:
                room_uuid = str(UUID(str(ambiente_client_uuid or "")))
            except (TypeError, ValueError, AttributeError) as exc:
                raise HTTPException(
                    status_code=400, detail="Ambiente foto non valido"
                ) from exc
            folder = f"ambiente-{room_uuid}"
        else:
            folder = "generali"
        path = f"{tenant_id}/rilievo-{rilievo_id}/{folder}/" f"{uuid4()}.{extension}"
    else:
        raise HTTPException(status_code=422, detail="Tipo asset rilievo non valido")
    await asyncio.to_thread(upload_asset, bucket, path, content, mime)
    return {"bucket": bucket, "path": path, "mime_type": mime}


async def crea_url_asset(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    *,
    bucket: str,
    paths: list[str],
) -> list[dict]:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    validate_asset_paths(tenant_id, rilievo_id, bucket, paths)
    urls = await asyncio.to_thread(signed_asset_urls, bucket, paths, 5 * 60)
    return [{"path": path, "url": url} for path, url in zip(paths, urls)]


async def lista_rilievi(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        select r.*,
               count(a.id)::int as n_ambienti,
               (
                 coalesce(sum(cardinality(a.foto_paths)), 0)
                 + cardinality(r.foto_paths)
               )::int as n_foto
        from public.rilievi r
        left join public.rilievo_ambienti a
          on a.tenant_id = r.tenant_id
         and a.rilievo_id = r.id
         and a.archived_at is null
        where r.tenant_id = $1::uuid and r.archived_at is null
        group by r.id
        order by r.data_rilievo desc, r.updated_at desc, r.id desc
        """,
        tenant_id,
    )
    return [_d(row) for row in rows]


async def crea_rilievo(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    client_uuid: str,
    cliente: str,
    data_rilievo: date,
    lead_id: Optional[str] = None,
    sopralluogo_legacy_id: Optional[str] = None,
    indirizzo: Optional[str] = None,
    tecnico: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    row = await conn.fetchrow(
        """
        insert into public.rilievi (
          tenant_id, lead_id, sopralluogo_legacy_id, client_uuid, cliente,
          indirizzo, data_rilievo, tecnico, note, created_by
        ) values (
          $1::uuid, $2::uuid, $3, $4::uuid, $5,
          $6, $7::date, $8, $9, auth.uid()
        )
        on conflict (tenant_id, client_uuid) do update
          set cliente = excluded.cliente,
              lead_id = coalesce(public.rilievi.lead_id, excluded.lead_id),
              sopralluogo_legacy_id = coalesce(
                public.rilievi.sopralluogo_legacy_id,
                excluded.sopralluogo_legacy_id
              ),
              indirizzo = excluded.indirizzo,
              data_rilievo = excluded.data_rilievo,
              tecnico = excluded.tecnico,
              note = excluded.note,
              archived_at = null
        returning *
        """,
        tenant_id,
        lead_id,
        _clean(sopralluogo_legacy_id),
        client_uuid,
        cliente.strip(),
        _clean(indirizzo),
        data_rilievo,
        _clean(tecnico),
        _clean(note),
    )
    return _d(row)


async def get_rilievo(
    conn: asyncpg.Connection, tenant_id: str, rilievo_id: str
) -> dict:
    rilievo = await _require_rilievo(conn, tenant_id, rilievo_id)
    ambienti = await conn.fetch(
        """
        select * from public.rilievo_ambienti
        where tenant_id = $1::uuid and rilievo_id = $2::uuid
          and archived_at is null
        order by ordine, created_at, id
        """,
        tenant_id,
        rilievo_id,
    )
    rilievo["ambienti"] = [_d(row) for row in ambienti]
    rilievo["n_ambienti"] = len(rilievo["ambienti"])
    rilievo["n_foto_generali"] = len(rilievo.get("foto_paths") or [])
    rilievo["n_foto"] = rilievo["n_foto_generali"] + sum(
        len(ambiente.get("foto_paths") or []) for ambiente in rilievo["ambienti"]
    )
    return rilievo


def _validate_tavola_paths(
    tenant_id: str,
    rilievo_id: str,
    planimetria_path: Optional[str],
    planimetria_preview_path: Optional[str],
    foto_paths: list[str],
) -> None:
    plans = [path for path in (planimetria_path, planimetria_preview_path) if path]
    validate_asset_paths(tenant_id, rilievo_id, "planimetrie", plans)
    general_prefix, _ = _photo_asset_prefixes(tenant_id, rilievo_id)
    if any(not path.startswith(general_prefix) for path in foto_paths):
        raise HTTPException(
            status_code=400,
            detail="Una o piu foto generali non appartengono al rilievo",
        )
    validate_asset_paths(tenant_id, rilievo_id, "foto-cantiere", foto_paths)


async def salva_tavola(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    *,
    planimetria_path: Optional[str],
    planimetria_preview_path: Optional[str],
    planimetria_filename: Optional[str],
    planimetria_mime_type: Optional[str],
    planimetria_data: dict,
    foto_paths: list[str],
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    _validate_tavola_paths(
        tenant_id,
        rilievo_id,
        planimetria_path,
        planimetria_preview_path,
        foto_paths,
    )
    row = await conn.fetchrow(
        """
        update public.rilievi
        set planimetria_path = $3,
            planimetria_preview_path = $4,
            planimetria_filename = $5,
            planimetria_mime_type = $6,
            planimetria_data = $7::jsonb,
            foto_paths = $8::text[]
        where tenant_id = $1::uuid and id = $2::uuid and archived_at is null
        returning id
        """,
        tenant_id,
        rilievo_id,
        _clean(planimetria_path),
        _clean(planimetria_preview_path),
        _clean(planimetria_filename),
        _clean(planimetria_mime_type),
        json.dumps(planimetria_data, ensure_ascii=False, default=str),
        foto_paths,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rilievo non trovato")
    return await get_rilievo(conn, tenant_id, rilievo_id)


async def aggiorna_rilievo(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    changes: dict,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    allowed = {
        "cliente",
        "indirizzo",
        "data_rilievo",
        "tecnico",
        "note",
        "stato",
    }
    updates = {key: value for key, value in changes.items() if key in allowed}
    if not updates:
        return await get_rilievo(conn, tenant_id, rilievo_id)
    if updates.get("stato") == "completato":
        count = await conn.fetchval(
            """
            select count(*) from public.rilievo_ambienti
            where tenant_id = $1::uuid and rilievo_id = $2::uuid
              and archived_at is null
            """,
            tenant_id,
            rilievo_id,
        )
        if not count:
            raise HTTPException(
                status_code=409,
                detail="Inserisci almeno un ambiente prima di completare il rilievo",
            )

    assignments = []
    args: list[Any] = [tenant_id, rilievo_id]
    for key, value in updates.items():
        args.append(value.strip() if isinstance(value, str) else value)
        cast = "::date" if key == "data_rilievo" else ""
        assignments.append(f"{key} = ${len(args)}{cast}")
    if "stato" in updates:
        assignments.append(
            "completed_at = now()"
            if updates["stato"] == "completato"
            else "completed_at = null"
        )
    row = await conn.fetchrow(
        f"""
        update public.rilievi set {', '.join(assignments)}
        where tenant_id = $1::uuid and id = $2::uuid and archived_at is null
        returning *
        """,
        *args,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rilievo non trovato")
    return await get_rilievo(conn, tenant_id, rilievo_id)


async def salva_ambiente(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    ambiente_client_uuid: str,
    *,
    nome: str,
    tipologia: Optional[str] = None,
    piano: Optional[str] = None,
    ordine: int = 0,
    lunghezza: Optional[Decimal] = None,
    larghezza: Optional[Decimal] = None,
    altezza: Optional[Decimal] = None,
    superficie: Optional[Decimal] = None,
    misure_extra: Optional[list[dict]] = None,
    note: Optional[str] = None,
    foto_paths: Optional[list[str]] = None,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    paths = list(foto_paths or [])
    _validate_photo_paths(tenant_id, rilievo_id, ambiente_client_uuid, paths)
    if superficie is None and lunghezza is not None and larghezza is not None:
        superficie = (lunghezza * larghezza).quantize(Decimal("0.001"))
    row = await conn.fetchrow(
        """
        insert into public.rilievo_ambienti (
          tenant_id, rilievo_id, client_uuid, nome, tipologia, piano, ordine,
          lunghezza, larghezza, altezza, superficie, misure_extra, note,
          foto_paths
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7,
          $8, $9, $10, $11, $12::jsonb, $13, $14::text[]
        )
        on conflict (tenant_id, rilievo_id, client_uuid) do update
          set nome = excluded.nome,
              tipologia = excluded.tipologia,
              piano = excluded.piano,
              ordine = excluded.ordine,
              lunghezza = excluded.lunghezza,
              larghezza = excluded.larghezza,
              altezza = excluded.altezza,
              superficie = excluded.superficie,
              misure_extra = excluded.misure_extra,
              note = excluded.note,
              foto_paths = excluded.foto_paths,
              archived_at = null
        returning *
        """,
        tenant_id,
        rilievo_id,
        ambiente_client_uuid,
        nome.strip(),
        _clean(tipologia),
        _clean(piano),
        ordine,
        lunghezza,
        larghezza,
        altezza,
        superficie,
        _extra_json(misure_extra or []),
        _clean(note),
        paths,
    )
    return _d(row)


async def archivia_ambiente(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    ambiente_client_uuid: str,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    row = await conn.fetchrow(
        """
        update public.rilievo_ambienti set archived_at = now()
        where tenant_id = $1::uuid and rilievo_id = $2::uuid
          and client_uuid = $3::uuid and archived_at is null
        returning id, client_uuid
        """,
        tenant_id,
        rilievo_id,
        ambiente_client_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ambiente non trovato")
    return {"ok": True, "id": str(row["id"]), "client_uuid": str(row["client_uuid"])}
