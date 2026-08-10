"""API documentale su Supabase/Postgres per il runtime storico GB.

Il modello applicativo resta invariato durante il cutover, ma ogni documento è
salvato in ``private.runtime_documents``. Le operazioni di modifica sono
atomiche e usano ``SELECT ... FOR UPDATE`` dentro transazioni brevi.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Sequence
from uuid import UUID

import asyncpg

from document_id import ObjectId


class DuplicateKeyError(RuntimeError):
    pass


class ReturnDocument(Enum):
    BEFORE = 0
    AFTER = 1


@dataclass
class InsertOneResult:
    inserted_id: str


@dataclass
class InsertManyResult:
    inserted_ids: list[str]


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: str | None = None


@dataclass
class DeleteResult:
    deleted_count: int


def _json_value(value: Any) -> Any:
    if isinstance(value, (ObjectId, UUID)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _path_parts(path: str) -> list[str]:
    parts = str(path).split(".")
    if not parts or any(not re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts):
        raise ValueError(f"Percorso documento non valido: {path!r}")
    return parts


def _get_path(document: dict, path: str, missing: Any = None) -> Any:
    value: Any = document
    for part in _path_parts(path):
        if not isinstance(value, dict) or part not in value:
            return missing
        value = value[part]
    return value


def _set_path(document: dict, path: str, value: Any) -> None:
    parts = _path_parts(path)
    cursor = document
    for part in parts[:-1]:
        nested = cursor.get(part)
        if not isinstance(nested, dict):
            nested = {}
            cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = _json_value(value)


def _unset_path(document: dict, path: str) -> None:
    parts = _path_parts(path)
    cursor: Any = document
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return
        cursor = cursor[part]
    if isinstance(cursor, dict):
        cursor.pop(parts[-1], None)


_MISSING = object()


def _matches_operator(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "$exists":
        return (actual is not _MISSING) is bool(expected)
    if operator == "$ne":
        return actual is _MISSING or actual != _json_value(expected)
    if operator in {"$in", "$nin"}:
        choices = [_json_value(item) for item in expected]
        if isinstance(actual, list):
            matched = any(item in choices for item in actual)
        else:
            matched = actual in choices
        return matched if operator == "$in" else not matched
    if actual is _MISSING:
        return False
    if operator in {"$gt", "$gte", "$lt", "$lte"}:
        expected = _json_value(expected)
        try:
            if operator == "$gt":
                return actual > expected
            if operator == "$gte":
                return actual >= expected
            if operator == "$lt":
                return actual < expected
            return actual <= expected
        except TypeError:
            return False
    if operator == "$regex":
        return re.search(str(expected), str(actual or "")) is not None
    if operator == "$type":
        expected_type = str(expected).lower()
        return {
            "string": isinstance(actual, str),
            "array": isinstance(actual, list),
            "object": isinstance(actual, dict),
            "number": isinstance(actual, (int, float)) and not isinstance(actual, bool),
            "bool": isinstance(actual, bool),
        }.get(expected_type, False)
    if operator == "$options":
        return True
    raise ValueError(f"Operatore filtro non supportato: {operator}")


def _matches(document: dict, query: dict | None) -> bool:
    for key, expected in (query or {}).items():
        if key == "$or":
            if not any(_matches(document, branch) for branch in expected):
                return False
            continue
        if key == "$and":
            if not all(_matches(document, branch) for branch in expected):
                return False
            continue
        actual = _get_path(document, key, _MISSING)
        if isinstance(expected, dict) and any(str(op).startswith("$") for op in expected):
            regex = expected.get("$regex")
            if regex is not None:
                flags = re.IGNORECASE if "i" in str(expected.get("$options") or "") else 0
                if actual is _MISSING or re.search(str(regex), str(actual or ""), flags) is None:
                    return False
            for operator, operand in expected.items():
                if operator in {"$regex", "$options"}:
                    continue
                if not _matches_operator(actual, operator, operand):
                    return False
            continue
        expected = _json_value(expected)
        if isinstance(actual, list):
            if expected not in actual and actual != expected:
                return False
        elif actual is _MISSING:
            if expected is not None:
                return False
        elif actual != expected:
            return False
    return True


def _apply_update(document: dict, update: dict, *, inserting: bool = False) -> dict:
    result = copy.deepcopy(document)
    if not any(str(key).startswith("$") for key in update):
        replacement = _json_value(update)
        replacement["_id"] = result.get("_id")
        return replacement
    for operator, values in update.items():
        if operator == "$set" or (operator == "$setOnInsert" and inserting):
            for path, value in values.items():
                _set_path(result, path, value)
        elif operator == "$setOnInsert":
            continue
        elif operator == "$unset":
            for path in values:
                _unset_path(result, path)
        elif operator == "$inc":
            for path, amount in values.items():
                current = _get_path(result, path, 0)
                _set_path(result, path, (current or 0) + amount)
        elif operator in {"$push", "$addToSet"}:
            for path, value in values.items():
                current = _get_path(result, path, [])
                items = list(current) if isinstance(current, list) else []
                if isinstance(value, dict) and "$each" in value:
                    incoming = [_json_value(item) for item in value["$each"]]
                else:
                    incoming = [_json_value(value)]
                if operator == "$addToSet":
                    for item in incoming:
                        if item not in items:
                            items.append(item)
                else:
                    position = value.get("$position") if isinstance(value, dict) else None
                    if position is None:
                        items.extend(incoming)
                    else:
                        for offset, item in enumerate(incoming):
                            items.insert(int(position) + offset, item)
                _set_path(result, path, items)
        else:
            raise ValueError(f"Operatore update non supportato: {operator}")
    return result


def _projection(document: dict, projection: dict | None) -> dict:
    if not projection:
        return document
    included = [key for key, enabled in projection.items() if enabled and key != "_id"]
    if included:
        result = {"_id": document.get("_id")}
        for path in included:
            value = _get_path(document, path, _MISSING)
            if value is not _MISSING:
                _set_path(result, path, value)
        if projection.get("_id") == 0:
            result.pop("_id", None)
        return result
    result = copy.deepcopy(document)
    for path, enabled in projection.items():
        if not enabled:
            _unset_path(result, path)
    return result


def _sort_value(document: dict, field: str) -> tuple[bool, Any]:
    value = _get_path(document, field, None)
    return value is None, value


class DocumentCursor:
    def __init__(self, collection: "DocumentCollection", query: dict, projection: dict | None):
        self.collection = collection
        self.query = query
        self.projection = projection
        self.sort_spec: list[tuple[str, int]] = []

    def sort(self, field_or_list, direction: int | None = None):
        self.sort_spec = (
            [(str(field), int(order)) for field, order in field_or_list]
            if isinstance(field_or_list, list)
            else [(str(field_or_list), int(direction or 1))]
        )
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        documents = await self.collection._all_documents()
        documents = [doc for doc in documents if _matches(doc, self.query)]
        for field, direction in reversed(self.sort_spec):
            documents.sort(key=lambda doc: _sort_value(doc, field), reverse=direction < 0)
        if length is not None:
            documents = documents[: int(length)]
        return [_projection(doc, self.projection) for doc in documents]


class DocumentCollection:
    def __init__(self, database: "PostgresDocumentDatabase", name: str):
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,62}", name):
            raise ValueError(f"Collection non valida: {name!r}")
        self.database = database
        self.name = name

    async def create_index(self, *_args, **_kwargs) -> str:
        return "managed_by_supabase_migration"

    async def _all_documents(self, *, conn=None, for_update: bool = False) -> list[dict]:
        tenant_id = await self.database.tenant_id()
        sql = """
            select id, data
            from private.runtime_documents
            where tenant_id = $1::uuid and collection = $2
        """
        if for_update:
            sql += " for update"
        if conn is None:
            async with self.database.pool.acquire() as acquired:
                rows = await acquired.fetch(sql, tenant_id, self.name)
        else:
            if for_update:
                # Anche una collection vuota deve essere serializzata: SELECT
                # FOR UPDATE non blocca righe inesistenti e due upsert concorrenti
                # perderebbero l'atomicita dei contatori condivisi.
                await conn.execute(
                    "select pg_advisory_xact_lock(hashtextextended($1, 0))",
                    f"{tenant_id}:{self.name}",
                )
            rows = await conn.fetch(sql, tenant_id, self.name)
        documents = []
        for row in rows:
            payload = row["data"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            document = dict(payload or {})
            raw_id = str(row["id"])
            document["_id"] = ObjectId(raw_id) if ObjectId.is_valid(raw_id) else raw_id
            documents.append(document)
        return documents

    def find(self, query: dict | None = None, projection: dict | None = None) -> DocumentCursor:
        return DocumentCursor(self, query or {}, projection)

    async def find_one(
        self,
        query: dict | None = None,
        projection: dict | None = None,
        sort: Sequence[tuple[str, int]] | None = None,
    ) -> dict | None:
        cursor = self.find(query, projection)
        if sort:
            cursor.sort(list(sort))
        rows = await cursor.to_list(1)
        return rows[0] if rows else None

    async def count_documents(self, query: dict | None = None) -> int:
        return len(await self.find(query).to_list(None))

    async def insert_one(self, document: dict) -> InsertOneResult:
        payload = _json_value(copy.deepcopy(document))
        raw_id = str(payload.pop("_id", ObjectId()))
        tenant_id = await self.database.tenant_id()
        try:
            async with self.database.pool.acquire() as conn:
                await conn.execute(
                    """
                    insert into private.runtime_documents (tenant_id, collection, id, data)
                    values ($1::uuid, $2, $3, $4::jsonb)
                    """,
                    tenant_id,
                    self.name,
                    raw_id,
                    json.dumps(payload, ensure_ascii=False),
                )
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        return InsertOneResult(ObjectId(raw_id) if ObjectId.is_valid(raw_id) else raw_id)

    async def insert_many(self, documents: Iterable[dict]) -> InsertManyResult:
        inserted = []
        for document in documents:
            inserted.append((await self.insert_one(document)).inserted_id)
        return InsertManyResult(inserted)

    def _upsert_seed(self, query: dict) -> dict:
        seed: dict = {}
        for path, value in query.items():
            if path.startswith("$"):
                continue
            if isinstance(value, dict) and any(str(key).startswith("$") for key in value):
                continue
            _set_path(seed, path, value)
        return seed

    async def _write_document(self, conn, document: dict) -> None:
        tenant_id = await self.database.tenant_id()
        raw_id = str(document["_id"])
        payload = _json_value({key: value for key, value in document.items() if key != "_id"})
        await conn.execute(
            """
            update private.runtime_documents
            set data = $4::jsonb
            where tenant_id = $1::uuid and collection = $2 and id = $3
            """,
            tenant_id,
            self.name,
            raw_id,
            json.dumps(payload, ensure_ascii=False),
        )

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> UpdateResult:
        tenant_id = await self.database.tenant_id()
        try:
            async with self.database.pool.acquire() as conn:
                async with conn.transaction():
                    documents = await self._all_documents(conn=conn, for_update=True)
                    current = next((doc for doc in documents if _matches(doc, query)), None)
                    if current is not None:
                        updated = _apply_update(current, update)
                        changed = updated != current
                        if changed:
                            await self._write_document(conn, updated)
                        return UpdateResult(1, int(changed))
                    if not upsert:
                        return UpdateResult(0, 0)
                    inserted = _apply_update(self._upsert_seed(query), update, inserting=True)
                    raw_id = str(inserted.pop("_id", ObjectId()))
                    payload = _json_value(inserted)
                    await conn.execute(
                        """
                        insert into private.runtime_documents (tenant_id, collection, id, data)
                        values ($1::uuid, $2, $3, $4::jsonb)
                        """,
                        tenant_id,
                        self.name,
                        raw_id,
                        json.dumps(payload, ensure_ascii=False),
                    )
                    inserted_id = ObjectId(raw_id) if ObjectId.is_valid(raw_id) else raw_id
                    return UpdateResult(0, 0, inserted_id)
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateKeyError(str(exc)) from exc

    async def update_many(self, query: dict, update: dict, upsert: bool = False) -> UpdateResult:
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                documents = await self._all_documents(conn=conn, for_update=True)
                matches = [doc for doc in documents if _matches(doc, query)]
                modified = 0
                for current in matches:
                    updated = _apply_update(current, update)
                    if updated != current:
                        await self._write_document(conn, updated)
                        modified += 1
                if matches or not upsert:
                    return UpdateResult(len(matches), modified)
        return await self.update_one(query, update, upsert=True)

    async def find_one_and_update(
        self,
        query: dict,
        update: dict,
        *,
        upsert: bool = False,
        return_document: ReturnDocument = ReturnDocument.BEFORE,
    ) -> dict | None:
        tenant_id = await self.database.tenant_id()
        try:
            async with self.database.pool.acquire() as conn:
                async with conn.transaction():
                    documents = await self._all_documents(conn=conn, for_update=True)
                    current = next((doc for doc in documents if _matches(doc, query)), None)
                    if current is None:
                        if not upsert:
                            return None
                        current = self._upsert_seed(query)
                        updated = _apply_update(current, update, inserting=True)
                        raw_id = str(updated.pop("_id", ObjectId()))
                        await conn.execute(
                            """
                            insert into private.runtime_documents (tenant_id, collection, id, data)
                            values ($1::uuid, $2, $3, $4::jsonb)
                            """,
                            tenant_id,
                            self.name,
                            raw_id,
                            json.dumps(_json_value(updated), ensure_ascii=False),
                        )
                        updated["_id"] = ObjectId(raw_id) if ObjectId.is_valid(raw_id) else raw_id
                        return updated if return_document == ReturnDocument.AFTER else None
                    before = copy.deepcopy(current)
                    updated = _apply_update(current, update)
                    if updated != current:
                        await self._write_document(conn, updated)
                    return updated if return_document == ReturnDocument.AFTER else before
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateKeyError(str(exc)) from exc

    async def delete_one(self, query: dict) -> DeleteResult:
        tenant_id = await self.database.tenant_id()
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                documents = await self._all_documents(conn=conn, for_update=True)
                current = next((doc for doc in documents if _matches(doc, query)), None)
                if current is None:
                    return DeleteResult(0)
                await conn.execute(
                    """
                    delete from private.runtime_documents
                    where tenant_id = $1::uuid and collection = $2 and id = $3
                    """,
                    tenant_id,
                    self.name,
                    str(current["_id"]),
                )
                return DeleteResult(1)

    async def delete_many(self, query: dict) -> DeleteResult:
        tenant_id = await self.database.tenant_id()
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                documents = await self._all_documents(conn=conn, for_update=True)
                ids = [str(doc["_id"]) for doc in documents if _matches(doc, query)]
                if ids:
                    await conn.execute(
                        """
                        delete from private.runtime_documents
                        where tenant_id = $1::uuid and collection = $2 and id = any($3::text[])
                        """,
                        tenant_id,
                        self.name,
                        ids,
                    )
                return DeleteResult(len(ids))


class PostgresDocumentDatabase:
    def __init__(self, db_module, tenant_slug: str = "gbconstruction"):
        self.db_module = db_module
        self.tenant_slug = tenant_slug
        self._tenant_id: str | None = None
        self._collections: dict[str, DocumentCollection] = {}

    @property
    def pool(self):
        pool = getattr(self.db_module, "_pool", None)
        if pool is None:
            raise RuntimeError("Pool Supabase non inizializzato")
        return pool

    async def startup(self) -> None:
        await self.tenant_id()
        async with self.pool.acquire() as conn:
            await conn.fetchval("select private.purge_expired_runtime_documents()")

    async def tenant_id(self) -> str:
        if self._tenant_id:
            return self._tenant_id
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                "select id from public.tenants where slug = $1",
                self.tenant_slug,
            )
        if not value:
            raise RuntimeError(f"Tenant Supabase non trovato: {self.tenant_slug}")
        self._tenant_id = str(value)
        return self._tenant_id

    def __getattr__(self, name: str) -> DocumentCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = DocumentCollection(self, name)
        return self._collections[name]
