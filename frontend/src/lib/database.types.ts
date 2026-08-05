export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  public: {
    Tables: {
      cantieri: {
        Row: {
          avanzamento: number
          capocantiere: string | null
          cliente: string
          cliente_id: string | null
          completed_at: string | null
          created_at: string
          criticita: string | null
          fasi: Json
          id: string
          importo: number | null
          indirizzo: string | null
          lead_id: string | null
          legacy_mongo_id: string | null
          milestone: string | null
          milestone_data: string | null
          note: string | null
          stato: string
          tenant_id: string
          updated_at: string
        }
        Insert: {
          avanzamento?: number
          capocantiere?: string | null
          cliente: string
          cliente_id?: string | null
          completed_at?: string | null
          created_at?: string
          criticita?: string | null
          fasi?: Json
          id?: string
          importo?: number | null
          indirizzo?: string | null
          lead_id?: string | null
          legacy_mongo_id?: string | null
          milestone?: string | null
          milestone_data?: string | null
          note?: string | null
          stato?: string
          tenant_id: string
          updated_at?: string
        }
        Update: {
          avanzamento?: number
          capocantiere?: string | null
          cliente?: string
          cliente_id?: string | null
          completed_at?: string | null
          created_at?: string
          criticita?: string | null
          fasi?: Json
          id?: string
          importo?: number | null
          indirizzo?: string | null
          lead_id?: string | null
          legacy_mongo_id?: string | null
          milestone?: string | null
          milestone_data?: string | null
          note?: string | null
          stato?: string
          tenant_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "cantieri_cliente_id_fkey"
            columns: ["cliente_id"]
            isOneToOne: false
            referencedRelation: "clienti"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "cantieri_lead_id_fkey"
            columns: ["lead_id"]
            isOneToOne: false
            referencedRelation: "leads"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "cantieri_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      clienti: {
        Row: {
          cf: string | null
          citta: string | null
          created_at: string
          email: string | null
          id: string
          indirizzo: string | null
          nome: string
          note: string | null
          piva: string | null
          telefono: string | null
          tenant_id: string
          tipo: string
          updated_at: string
        }
        Insert: {
          cf?: string | null
          citta?: string | null
          created_at?: string
          email?: string | null
          id?: string
          indirizzo?: string | null
          nome: string
          note?: string | null
          piva?: string | null
          telefono?: string | null
          tenant_id: string
          tipo?: string
          updated_at?: string
        }
        Update: {
          cf?: string | null
          citta?: string | null
          created_at?: string
          email?: string | null
          id?: string
          indirizzo?: string | null
          nome?: string
          note?: string | null
          piva?: string | null
          telefono?: string | null
          tenant_id?: string
          tipo?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "clienti_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      computi: {
        Row: {
          cantiere_id: string | null
          created_at: string
          id: string
          lead_id: string | null
          note: string | null
          numero: string | null
          parent_computo_id: string | null
          prezzario_id: string | null
          stato: string
          tenant_id: string
          tipo: string
          updated_at: string
        }
        Insert: {
          cantiere_id?: string | null
          created_at?: string
          id?: string
          lead_id?: string | null
          note?: string | null
          numero?: string | null
          parent_computo_id?: string | null
          prezzario_id?: string | null
          stato?: string
          tenant_id: string
          tipo?: string
          updated_at?: string
        }
        Update: {
          cantiere_id?: string | null
          created_at?: string
          id?: string
          lead_id?: string | null
          note?: string | null
          numero?: string | null
          parent_computo_id?: string | null
          prezzario_id?: string | null
          stato?: string
          tenant_id?: string
          tipo?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "computi_cantiere_id_fkey"
            columns: ["cantiere_id"]
            isOneToOne: false
            referencedRelation: "cantieri"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "computi_lead_id_fkey"
            columns: ["lead_id"]
            isOneToOne: false
            referencedRelation: "leads"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "computi_parent_computo_id_fkey"
            columns: ["parent_computo_id"]
            isOneToOne: false
            referencedRelation: "computi"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "computi_parent_computo_id_fkey"
            columns: ["parent_computo_id"]
            isOneToOne: false
            referencedRelation: "computi_totali"
            referencedColumns: ["computo_id"]
          },
          {
            foreignKeyName: "computi_prezzario_id_fkey"
            columns: ["prezzario_id"]
            isOneToOne: false
            referencedRelation: "prezzari"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "computi_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      computo_voci: {
        Row: {
          categoria: string
          computo_id: string
          descrizione: string
          generata_da_ai: boolean
          id: string
          ordine: number
          origine_voce_id: string | null
          prezzo_unitario: number
          qta: number
          sub_categoria: string | null
          super_categoria: string
          tenant_id: string
          tipo: string
          totale: number | null
          um: string
          validata_umano: boolean
        }
        Insert: {
          categoria: string
          computo_id: string
          descrizione: string
          generata_da_ai?: boolean
          id?: string
          ordine?: number
          origine_voce_id?: string | null
          prezzo_unitario?: number
          qta?: number
          sub_categoria?: string | null
          super_categoria: string
          tenant_id: string
          tipo?: string
          totale?: number | null
          um: string
          validata_umano?: boolean
        }
        Update: {
          categoria?: string
          computo_id?: string
          descrizione?: string
          generata_da_ai?: boolean
          id?: string
          ordine?: number
          origine_voce_id?: string | null
          prezzo_unitario?: number
          qta?: number
          sub_categoria?: string | null
          super_categoria?: string
          tenant_id?: string
          tipo?: string
          totale?: number | null
          um?: string
          validata_umano?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "computo_voci_computo_id_fkey"
            columns: ["computo_id"]
            isOneToOne: false
            referencedRelation: "computi"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "computo_voci_computo_id_fkey"
            columns: ["computo_id"]
            isOneToOne: false
            referencedRelation: "computi_totali"
            referencedColumns: ["computo_id"]
          },
          {
            foreignKeyName: "computo_voci_origine_voce_id_fkey"
            columns: ["origine_voce_id"]
            isOneToOne: false
            referencedRelation: "prezzario_voci"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "computo_voci_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      leads: {
        Row: {
          ai_architect_job_id: string | null
          citta: string | null
          cliente_id: string | null
          config: Json
          created_at: string
          email: string
          id: string
          indirizzo: string | null
          legacy_mongo_id: string | null
          newsletter: boolean
          nome: string
          note_cliente: string | null
          owner: string | null
          privacy: boolean
          prossima_azione: string | null
          score: number | null
          status: string
          stima: Json | null
          tags: string[]
          telefono: string
          tenant_id: string
          timeline: Json
          tracking: Json
          updated_at: string
        }
        Insert: {
          ai_architect_job_id?: string | null
          citta?: string | null
          cliente_id?: string | null
          config?: Json
          created_at?: string
          email: string
          id?: string
          indirizzo?: string | null
          legacy_mongo_id?: string | null
          newsletter?: boolean
          nome: string
          note_cliente?: string | null
          owner?: string | null
          privacy?: boolean
          prossima_azione?: string | null
          score?: number | null
          status?: string
          stima?: Json | null
          tags?: string[]
          telefono: string
          tenant_id: string
          timeline?: Json
          tracking?: Json
          updated_at?: string
        }
        Update: {
          ai_architect_job_id?: string | null
          citta?: string | null
          cliente_id?: string | null
          config?: Json
          created_at?: string
          email?: string
          id?: string
          indirizzo?: string | null
          legacy_mongo_id?: string | null
          newsletter?: boolean
          nome?: string
          note_cliente?: string | null
          owner?: string | null
          privacy?: boolean
          prossima_azione?: string | null
          score?: number | null
          status?: string
          stima?: Json | null
          tags?: string[]
          telefono?: string
          tenant_id?: string
          timeline?: Json
          tracking?: Json
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "leads_cliente_id_fkey"
            columns: ["cliente_id"]
            isOneToOne: false
            referencedRelation: "clienti"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "leads_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      libretto_misure: {
        Row: {
          altezza: number | null
          cantiere_id: string
          client_uuid: string
          computo_voce_id: string | null
          created_at: string
          data_misura: string
          descrizione: string | null
          foto_paths: string[]
          id: string
          larghezza: number | null
          lunghezza: number | null
          parti: number
          qta: number
          rilevata_da: string | null
          tenant_id: string
        }
        Insert: {
          altezza?: number | null
          cantiere_id: string
          client_uuid: string
          computo_voce_id?: string | null
          created_at?: string
          data_misura?: string
          descrizione?: string | null
          foto_paths?: string[]
          id?: string
          larghezza?: number | null
          lunghezza?: number | null
          parti?: number
          qta: number
          rilevata_da?: string | null
          tenant_id: string
        }
        Update: {
          altezza?: number | null
          cantiere_id?: string
          client_uuid?: string
          computo_voce_id?: string | null
          created_at?: string
          data_misura?: string
          descrizione?: string | null
          foto_paths?: string[]
          id?: string
          larghezza?: number | null
          lunghezza?: number | null
          parti?: number
          qta?: number
          rilevata_da?: string | null
          tenant_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "libretto_misure_cantiere_tenant_fk"
            columns: ["tenant_id", "cantiere_id"]
            isOneToOne: false
            referencedRelation: "cantieri"
            referencedColumns: ["tenant_id", "id"]
          },
          {
            foreignKeyName: "libretto_misure_computo_voce_tenant_fk"
            columns: ["tenant_id", "computo_voce_id"]
            isOneToOne: false
            referencedRelation: "computo_voci"
            referencedColumns: ["tenant_id", "id"]
          },
          {
            foreignKeyName: "libretto_misure_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      mapping_regole: {
        Row: {
          attiva: boolean
          condizione: Json | null
          created_at: string
          id: string
          metrica: string
          moltiplicatore: number
          ordine: number
          prezzario_voce_id: string
          tenant_id: string
        }
        Insert: {
          attiva?: boolean
          condizione?: Json | null
          created_at?: string
          id?: string
          metrica: string
          moltiplicatore?: number
          ordine?: number
          prezzario_voce_id: string
          tenant_id: string
        }
        Update: {
          attiva?: boolean
          condizione?: Json | null
          created_at?: string
          id?: string
          metrica?: string
          moltiplicatore?: number
          ordine?: number
          prezzario_voce_id?: string
          tenant_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "mapping_regole_prezzario_voce_id_fkey"
            columns: ["prezzario_voce_id"]
            isOneToOne: false
            referencedRelation: "prezzario_voci"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "mapping_regole_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      preventivi: {
        Row: {
          accettato_at: string | null
          anno: number
          cliente_id: string | null
          computo_id: string
          created_at: string
          id: string
          inviato_at: string | null
          iva_percentuale: number
          lead_id: string | null
          note: string | null
          numero: string
          pdf_path: string | null
          progressivo: number
          rifiutato_at: string | null
          scaduto_at: string | null
          sconto_percentuale: number
          snapshot_voci: Json
          stato: string
          tenant_id: string
          totale_documento: number
          totale_imponibile: number
          totale_iva: number
          ultimo_destinatario: string | null
          ultimo_email_id: string | null
          ultimo_email_provider: string | null
          updated_at: string
          validita_giorni: number
        }
        Insert: {
          accettato_at?: string | null
          anno: number
          cliente_id?: string | null
          computo_id: string
          created_at?: string
          id?: string
          inviato_at?: string | null
          iva_percentuale?: number
          lead_id?: string | null
          note?: string | null
          numero: string
          pdf_path?: string | null
          progressivo: number
          rifiutato_at?: string | null
          scaduto_at?: string | null
          sconto_percentuale?: number
          snapshot_voci?: Json
          stato?: string
          tenant_id: string
          totale_documento?: number
          totale_imponibile?: number
          totale_iva?: number
          ultimo_destinatario?: string | null
          ultimo_email_id?: string | null
          ultimo_email_provider?: string | null
          updated_at?: string
          validita_giorni?: number
        }
        Update: {
          accettato_at?: string | null
          anno?: number
          cliente_id?: string | null
          computo_id?: string
          created_at?: string
          id?: string
          inviato_at?: string | null
          iva_percentuale?: number
          lead_id?: string | null
          note?: string | null
          numero?: string
          pdf_path?: string | null
          progressivo?: number
          rifiutato_at?: string | null
          scaduto_at?: string | null
          sconto_percentuale?: number
          snapshot_voci?: Json
          stato?: string
          tenant_id?: string
          totale_documento?: number
          totale_imponibile?: number
          totale_iva?: number
          ultimo_destinatario?: string | null
          ultimo_email_id?: string | null
          ultimo_email_provider?: string | null
          updated_at?: string
          validita_giorni?: number
        }
        Relationships: [
          {
            foreignKeyName: "preventivi_cliente_id_fkey"
            columns: ["cliente_id"]
            isOneToOne: false
            referencedRelation: "clienti"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "preventivi_computo_id_fkey"
            columns: ["computo_id"]
            isOneToOne: false
            referencedRelation: "computi"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "preventivi_computo_id_fkey"
            columns: ["computo_id"]
            isOneToOne: false
            referencedRelation: "computi_totali"
            referencedColumns: ["computo_id"]
          },
          {
            foreignKeyName: "preventivi_lead_id_fkey"
            columns: ["lead_id"]
            isOneToOne: false
            referencedRelation: "leads"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "preventivi_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      preventivo_eventi: {
        Row: {
          autore: string | null
          created_at: string
          destinatario: string | null
          dettaglio: string | null
          id: string
          idempotency_key: string | null
          oggetto: string | null
          preventivo_id: string
          provider: string | null
          provider_message_id: string | null
          stato_precedente: string | null
          stato_successivo: string | null
          tenant_id: string
          tipo: string
        }
        Insert: {
          autore?: string | null
          created_at?: string
          destinatario?: string | null
          dettaglio?: string | null
          id?: string
          idempotency_key?: string | null
          oggetto?: string | null
          preventivo_id: string
          provider?: string | null
          provider_message_id?: string | null
          stato_precedente?: string | null
          stato_successivo?: string | null
          tenant_id: string
          tipo: string
        }
        Update: {
          autore?: string | null
          created_at?: string
          destinatario?: string | null
          dettaglio?: string | null
          id?: string
          idempotency_key?: string | null
          oggetto?: string | null
          preventivo_id?: string
          provider?: string | null
          provider_message_id?: string | null
          stato_precedente?: string | null
          stato_successivo?: string | null
          tenant_id?: string
          tipo?: string
        }
        Relationships: [
          {
            foreignKeyName: "preventivo_eventi_preventivo_tenant_fk"
            columns: ["tenant_id", "preventivo_id"]
            isOneToOne: false
            referencedRelation: "preventivi"
            referencedColumns: ["tenant_id", "id"]
          },
          {
            foreignKeyName: "preventivo_eventi_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      prezzari: {
        Row: {
          anno: number | null
          created_at: string
          fonte: string
          id: string
          is_default: boolean
          is_sistema: boolean
          nome: string
          tenant_id: string
          updated_at: string
        }
        Insert: {
          anno?: number | null
          created_at?: string
          fonte?: string
          id?: string
          is_default?: boolean
          is_sistema?: boolean
          nome: string
          tenant_id: string
          updated_at?: string
        }
        Update: {
          anno?: number | null
          created_at?: string
          fonte?: string
          id?: string
          is_default?: boolean
          is_sistema?: boolean
          nome?: string
          tenant_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "prezzari_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      prezzario_voci: {
        Row: {
          attiva: boolean
          categoria: string
          chiave_wizard: boolean
          codice: string | null
          created_at: string
          descrizione: string
          id: string
          prezzario_id: string
          prezzo_riferimento: number | null
          prezzo_unitario: number
          sub_categoria: string | null
          super_categoria: string
          tenant_id: string
          tipo: string
          um: string
        }
        Insert: {
          attiva?: boolean
          categoria: string
          chiave_wizard?: boolean
          codice?: string | null
          created_at?: string
          descrizione: string
          id?: string
          prezzario_id: string
          prezzo_riferimento?: number | null
          prezzo_unitario: number
          sub_categoria?: string | null
          super_categoria: string
          tenant_id: string
          tipo?: string
          um: string
        }
        Update: {
          attiva?: boolean
          categoria?: string
          chiave_wizard?: boolean
          codice?: string | null
          created_at?: string
          descrizione?: string
          id?: string
          prezzario_id?: string
          prezzo_riferimento?: number | null
          prezzo_unitario?: number
          sub_categoria?: string | null
          super_categoria?: string
          tenant_id?: string
          tipo?: string
          um?: string
        }
        Relationships: [
          {
            foreignKeyName: "prezzario_voci_prezzario_id_fkey"
            columns: ["prezzario_id"]
            isOneToOne: false
            referencedRelation: "prezzari"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "prezzario_voci_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      sal: {
        Row: {
          cantiere_id: string
          created_at: string
          created_by: string | null
          id: string
          numero: number
          periodo_a: string
          periodo_da: string
          stato: string
          tenant_id: string
          updated_at: string
        }
        Insert: {
          cantiere_id: string
          created_at?: string
          created_by?: string | null
          id?: string
          numero: number
          periodo_a: string
          periodo_da: string
          stato?: string
          tenant_id: string
          updated_at?: string
        }
        Update: {
          cantiere_id?: string
          created_at?: string
          created_by?: string | null
          id?: string
          numero?: number
          periodo_a?: string
          periodo_da?: string
          stato?: string
          tenant_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "sal_cantiere_tenant_fk"
            columns: ["tenant_id", "cantiere_id"]
            isOneToOne: false
            referencedRelation: "cantieri"
            referencedColumns: ["tenant_id", "id"]
          },
          {
            foreignKeyName: "sal_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      sal_righe: {
        Row: {
          computo_voce_id: string
          created_at: string
          descrizione: string
          id: string
          importo_periodo: number | null
          prezzo_unitario: number
          qta_periodo: number
          qta_progressiva: number
          sal_id: string
          tenant_id: string
          um: string
        }
        Insert: {
          computo_voce_id: string
          created_at?: string
          descrizione: string
          id?: string
          importo_periodo?: number | null
          prezzo_unitario: number
          qta_periodo: number
          qta_progressiva: number
          sal_id: string
          tenant_id: string
          um: string
        }
        Update: {
          computo_voce_id?: string
          created_at?: string
          descrizione?: string
          id?: string
          importo_periodo?: number | null
          prezzo_unitario?: number
          qta_periodo?: number
          qta_progressiva?: number
          sal_id?: string
          tenant_id?: string
          um?: string
        }
        Relationships: [
          {
            foreignKeyName: "sal_righe_computo_voce_tenant_fk"
            columns: ["tenant_id", "computo_voce_id"]
            isOneToOne: false
            referencedRelation: "computo_voci"
            referencedColumns: ["tenant_id", "id"]
          },
          {
            foreignKeyName: "sal_righe_sal_tenant_fk"
            columns: ["tenant_id", "sal_id"]
            isOneToOne: false
            referencedRelation: "sal"
            referencedColumns: ["tenant_id", "id"]
          },
          {
            foreignKeyName: "sal_righe_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      tenant_members: {
        Row: {
          created_at: string
          nome: string | null
          photo_url: string | null
          role: Database["public"]["Enums"]["tenant_role"]
          tenant_id: string
          user_id: string
        }
        Insert: {
          created_at?: string
          nome?: string | null
          photo_url?: string | null
          role?: Database["public"]["Enums"]["tenant_role"]
          tenant_id: string
          user_id: string
        }
        Update: {
          created_at?: string
          nome?: string | null
          photo_url?: string | null
          role?: Database["public"]["Enums"]["tenant_role"]
          tenant_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "tenant_members_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      tenants: {
        Row: {
          ai_credits: number
          attivo: boolean
          contatti: Json
          created_at: string
          custom_domain: string | null
          id: string
          piano: string
          piva: string | null
          ragione_sociale: string
          slug: string
          theme: Json
          updated_at: string
        }
        Insert: {
          ai_credits?: number
          attivo?: boolean
          contatti?: Json
          created_at?: string
          custom_domain?: string | null
          id?: string
          piano?: string
          piva?: string | null
          ragione_sociale: string
          slug: string
          theme?: Json
          updated_at?: string
        }
        Update: {
          ai_credits?: number
          attivo?: boolean
          contatti?: Json
          created_at?: string
          custom_domain?: string | null
          id?: string
          piano?: string
          piva?: string | null
          ragione_sociale?: string
          slug?: string
          theme?: Json
          updated_at?: string
        }
        Relationships: []
      }
    }
    Views: {
      computi_totali: {
        Row: {
          computo_id: string | null
          n_da_validare: number | null
          n_voci: number | null
          tenant_id: string | null
          totale: number | null
        }
        Relationships: [
          {
            foreignKeyName: "computi_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Functions: {
      custom_access_token_hook: { Args: { event: Json }; Returns: Json }
      has_role: {
        Args: { roles: Database["public"]["Enums"]["tenant_role"][]; t: string }
        Returns: boolean
      }
      is_member: { Args: { t: string }; Returns: boolean }
    }
    Enums: {
      tenant_role: "owner" | "admin" | "staff" | "operations" | "client"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      tenant_role: ["owner", "admin", "staff", "operations", "client"],
    },
  },
} as const
