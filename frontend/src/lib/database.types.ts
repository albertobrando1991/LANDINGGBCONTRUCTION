/**
 * Placeholder types — regenerate with:
 *   npm run db:types
 * after `supabase start` / linked project.
 * Do not hand-edit generated output in production; this stub unblocks the build.
 */
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export interface Database {
  public: {
    Tables: {
      tenants: {
        Row: {
          id: string;
          slug: string;
          ragione_sociale: string;
          theme: Json;
          contatti: Json;
          piano: string;
          ai_credits: number;
          attivo: boolean;
        };
      };
      prezzari: {
        Row: {
          id: string;
          tenant_id: string;
          nome: string;
          fonte: string;
          is_default: boolean;
          is_sistema: boolean;
        };
      };
      prezzario_voci: {
        Row: {
          id: string;
          tenant_id: string;
          prezzario_id: string;
          codice: string | null;
          super_categoria: string;
          categoria: string;
          descrizione: string;
          um: string;
          prezzo_unitario: number;
          chiave_wizard: boolean;
        };
      };
      computi: {
        Row: {
          id: string;
          tenant_id: string;
          stato: string;
          tipo: string;
        };
      };
      computo_voci: {
        Row: {
          id: string;
          computo_id: string;
          descrizione: string;
          qta: number;
          prezzo_unitario: number;
          totale: number;
          generata_da_ai: boolean;
          validata_umano: boolean;
        };
      };
    };
    Views: {
      computi_totali: {
        Row: {
          computo_id: string;
          tenant_id: string;
          totale: number;
          n_voci: number;
          n_da_validare: number;
        };
      };
    };
  };
}
