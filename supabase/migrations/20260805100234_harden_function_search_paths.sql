-- I trigger eseguono query su tabelle public: fissare il search_path evita
-- che oggetti omonimi creati in altri schemi vengano risolti a runtime.

alter function public.touch_updated_at()
  set search_path = public, pg_temp;

alter function public.blocca_prezzario_sistema()
  set search_path = public, pg_temp;

alter function public.blocca_computo_confermato()
  set search_path = public, pg_temp;
