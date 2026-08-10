-- La migration runtime non deve revocare l'accesso alle funzioni private
-- tenant-scoped gia usate da EdilOS. Le nuove tabelle restano comunque senza
-- privilegi per authenticated e sono protette da FORCE RLS.
revoke all on schema private from public, anon;
grant usage on schema private to authenticated, service_role;
