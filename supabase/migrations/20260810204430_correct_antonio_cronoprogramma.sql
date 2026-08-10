-- PREV-2026-0005 e il relativo computo sono gia stati inviati/confermati.
-- Lo storico resta immutato: creiamo una variante in bozza, con superficie
-- verificata e sole riclassificazioni deterministiche delle voci ACCA.
do $$
declare
  source_id constant uuid := 'a4d7032e-5a14-49aa-bbec-c3bbd929a992';
  tenant_id_gb constant uuid := 'a0000000-0000-4000-8000-000000000001';
  target_id uuid;
  affected integer;
begin
  if not exists (
    select 1 from public.computi
    where id = source_id
      and tenant_id = tenant_id_gb
      and stato = 'confermato'
  ) then
    -- Database nuovi, test e tenant diversi non contengono questo documento.
    -- La migrazione di prodotto deve restare riproducibile anche senza dati live.
    return;
  end if;

  if exists (
    select 1 from public.computi
    where tenant_id = tenant_id_gb
      and parent_computo_id = source_id
      and note = 'Correzione cronoprogramma PREV-2026-0005'
  ) then
    raise exception 'Variante correttiva PREV-2026-0005 gia presente';
  end if;

  insert into public.computi (
    tenant_id, lead_id, cantiere_id, parent_computo_id, prezzario_id,
    tipo, stato, note, superficie_mq, durate_fasi
  )
  select
    tenant_id, lead_id, cantiere_id, id, prezzario_id,
    'variante', 'bozza', 'Correzione cronoprogramma PREV-2026-0005',
    92, '{}'::jsonb
  from public.computi
  where id = source_id and tenant_id = tenant_id_gb
  returning id into target_id;

  insert into public.computo_voci (
    tenant_id, computo_id, origine_voce_id, parent_voce_id, ordine,
    super_categoria, categoria, sub_categoria, descrizione, um, tipo,
    qta, prezzo_unitario, fase, fase_ordine, area,
    generata_da_ai, validata_umano
  )
  select
    tenant_id, target_id, origine_voce_id, id, ordine,
    super_categoria, categoria, sub_categoria, descrizione, um, tipo,
    qta, prezzo_unitario,
    case
      when id in (
        '56c870ea-b726-4759-838d-64f4032bcd7e'::uuid
      ) then 'Strutture e opere murarie'
      when id in (
        '943ba5f6-7190-4877-9118-b369569bde7d'::uuid,
        'e51b120e-a196-4b30-8a90-9596e6628674'::uuid
      ) then 'Impianto idrico-sanitario e scarichi'
      when id in (
        '914dfe56-4540-47f7-ad86-f8e6c8bf4d1e'::uuid,
        '21315650-af6b-4182-9d82-0d490b0d0cee'::uuid,
        '3f18a258-8910-479b-be41-a005f7b11b51'::uuid,
        '7324c559-ddde-483d-bc9c-3f03d878d79e'::uuid,
        'f0db79c9-221a-4771-bc77-0b727d456808'::uuid
      ) then 'Impianto elettrico e speciali'
      when id in (
        '67313212-9676-49b2-a7e5-3604a1c85b94'::uuid
      ) then 'Impianto termico e climatizzazione'
      when id in (
        'b62decf6-cf9b-4795-ba9e-74589aff38f6'::uuid
      ) then 'Pavimenti e rivestimenti'
      when id in (
        '168aff90-5a3e-403d-9217-b27b1eb9826b'::uuid,
        '1fae5c66-a097-4b03-9d79-de3a33cdec9b'::uuid
      ) then 'Tinteggiature e finiture'
      else fase
    end,
    case
      when id in ('56c870ea-b726-4759-838d-64f4032bcd7e'::uuid) then 25
      when id in (
        '943ba5f6-7190-4877-9118-b369569bde7d'::uuid,
        'e51b120e-a196-4b30-8a90-9596e6628674'::uuid
      ) then 35
      when id in (
        '914dfe56-4540-47f7-ad86-f8e6c8bf4d1e'::uuid,
        '21315650-af6b-4182-9d82-0d490b0d0cee'::uuid,
        '3f18a258-8910-479b-be41-a005f7b11b51'::uuid,
        '7324c559-ddde-483d-bc9c-3f03d878d79e'::uuid,
        'f0db79c9-221a-4771-bc77-0b727d456808'::uuid
      ) then 45
      when id in ('67313212-9676-49b2-a7e5-3604a1c85b94'::uuid) then 55
      when id in ('b62decf6-cf9b-4795-ba9e-74589aff38f6'::uuid) then 70
      when id in (
        '168aff90-5a3e-403d-9217-b27b1eb9826b'::uuid,
        '1fae5c66-a097-4b03-9d79-de3a33cdec9b'::uuid
      ) then 80
      else fase_ordine
    end,
    area, generata_da_ai, validata_umano
  from public.computo_voci
  where computo_id = source_id and tenant_id = tenant_id_gb;

  get diagnostics affected = row_count;
  if affected <> 66 then
    raise exception 'Copia computo Antonio incompleta: % voci invece di 66', affected;
  end if;

  if (
    select count(*)
    from public.computo_voci
    where computo_id = target_id and fase_ordine = 99
  ) <> 0 then
    raise exception 'La variante correttiva contiene ancora voci non classificate';
  end if;
end
$$;
