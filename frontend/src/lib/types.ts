export interface DashboardSettings {
  margin_green_bp: number;
  margin_yellow_bp: number;
  worst_min_sales: number;
  feed_size: number;
  sound_enabled: boolean;
  sound_threshold_c: number;
  sound_volume: number;
}

export interface SkuStat {
  sku: string;
  title: string | null;
  vendas: number;
  qtd: number;
  bruto_c: number;
  lucro_c: number;
  bruto_coberto_c: number;
  margem_bp: number | null;
}

export interface Alert {
  type: "missing_cost" | "tax_missing" | "delivery_missing";
  message: string;
  skus?: { sku: string; title: string | null; vendas: number; bruto_c: number }[];
}

export interface Dashboard {
  month: string;
  today: string;
  is_current_month: boolean;
  settings: DashboardSettings;
  totals: {
    vendas: number;
    canceladas: number;
    bruto_c: number;
    tarifa_c: number;
    frete_c: number;
    cupom_c: number;
    liquido_c: number;
    cmv_c: number;
    imposto_c: number;
    entrega_c: number;
    lucro_c: number;
    bruto_coberto_c: number;
    cobertura_bp: number | null;
    margem_bp: number | null;
    projecao_lucro_c?: number | null;
    lucro_apos_ads_c?: number | null;
    margem_apos_ads_bp?: number | null;
    entregas_flex: number;
  };
  goal: {
    goal_c: number | null;
    atingido_bp: number | null;
    projecao_c: number | null;
    projecao_bp: number | null;
    falta_por_dia_c: number | null;
    dias_restantes: number | null;
  };
  hoje: {
    bruto_c: number;
    lucro_c: number;
    bruto_coberto_c: number;
    vendas: number;
    ticket_medio_c: number | null;
    margem_bp: number | null;
  } | null;
  months: { month: string; vendas: number; bruto_c: number; lucro_c: number; bruto_coberto_c: number }[];
  rolling: {
    day: string;
    bruto_c: number;
    lucro_c: number;
    bruto_coberto_c: number;
    vendas: number;
    visitas: number | null;
    conversao_bp: number | null;
  }[];
  traffic: {
    disponivel: boolean;
    visitas_hoje: number | null;
    visitas_mes: number | null;
    conversao_hoje_bp: number | null;
    conversao_mes_bp: number | null;
    daily: { day: string; visitas: number | null }[];
  };
  ads: {
    disponivel: boolean;
    investimento_c: number;
    receita_ads_c: number;
    roas_x100: number | null;
    tacos_bp: number | null;
    atualizado_em: string | null;
  };
  daily: { day: string; bruto_c: number; lucro_c: number; vendas: number }[];
  top_skus: SkuStat[];
  worst_skus: SkuStat[];
  feed: {
    order_id: string;
    ts: string;
    sku: string | null;
    title: string | null;
    qtd: number;
    bruto_c: number;
    lucro_c: number | null;
    margem_bp: number | null;
    logistic_type: string | null;
    grupo: string;
  }[];
  alerts: Alert[];
}

export interface CostVersion {
  id: number;
  cost_c: number;
  valid_from: string | null;
  note: string | null;
}

export interface SkuRow {
  sku: string;
  sku_norm: string;
  title: string | null;
  item_ids: string[];
  versions: CostVersion[];
  custo_atual_c: number | null;
  sem_custo: boolean;
  sem_sku_no_anuncio: boolean;
  vendas_mes: number;
  qtd_mes: number;
  bruto_mes_c: number;
  vendas_total: number;
  ultima_venda: string | null;
}

export interface ImportRow {
  line: number;
  sku: string;
  cost_c: number | null;
  valid_from: string | null;
  action: "novo" | "atualiza" | "igual" | "erro";
  message: string;
  current_cost_c: number | null;
  known_sku: boolean;
}

// ---------------------------------------------------------------- Mercado Ads (/admin/ads)

export type AdsMetrics = {
  cost_c: number;
  revenue_c: number;
  direct_revenue_c: number;
  clicks: number;
  prints: number;
  units: number;
  organic_units: number;
  acos_bp: number | null;
  roas_x100: number | null;
  ctr_bp: number | null;
  cpc_c: number | null;
  cvr_bp: number | null;
};

export type AdsAccount = AdsMetrics & {
  faturamento_c: number;
  faturamento_bruto_c: number;
  tacos_bp: number | null;
  participacao_ads_bp: number | null;
  lucro_c: number;
  lucro_apos_ads_c: number;
  margem_apos_ads_bp: number | null;
  cobertura_bp: number | null;
};

export type AdsCampaignRow = AdsMetrics & {
  id: number;
  name: string;
  status: string;
  strategy: string | null;
  budget_c: number | null;
  automatic_budget: boolean;
  acos_target_bp: number | null;
  impression_share_bp: number | null;
  top_impression_share_bp: number | null;
  lost_budget_bp: number | null;
  lost_rank_bp: number | null;
  anuncios: number;
  anuncios_ativos: number;
  lucro_apos_ads_c: number | null;
  prev_cost_c: number;
  prev_acos_bp: number | null;
  daily: { day: string; cost_c: number; revenue_c: number }[];
};

export type AdsAdRow = AdsMetrics & {
  item_id: string;
  title: string | null;
  thumbnail: string | null;
  permalink: string | null;
  status: string | null;
  price_c: number | null;
  campaign_id: number | null;
  campaign_name: string | null;
  sku: string | null;
  vendas_total: number;
  unidades_total: number;
  faturamento_c: number;
  lucro_c: number | null;
  acos_max_bp: number | null;
  lucro_apos_ads_c: number | null;
  prev_cost_c: number;
  prev_acos_bp: number | null;
};

export type AdsAlert = {
  level: "critico" | "atencao" | "oportunidade";
  kind: string;
  title: string;
  detail: string;
  campaign_id?: number;
  item_id?: string;
};

export type AdsReport = {
  period: { from: string; to: string; days: number; prev_from: string; prev_to: string };
  totals: AdsAccount;
  prev: AdsAccount;
  daily: {
    day: string;
    cost_c: number;
    revenue_c: number;
    faturamento_c: number;
    clicks: number;
    units: number;
    acos_bp: number | null;
    tacos_bp: number | null;
  }[];
  campaigns: AdsCampaignRow[];
  ads: AdsAdRow[];
  alerts: AdsAlert[];
  sync: { at?: string; campanhas?: number; anuncios?: number } | null;
  margin_window_days: number;
};

export type AdsSaleRow = {
  order_id: string;
  pack_id: string | null;
  status: string;
  ts: string;
  comprador: { nome: string; apelido: string | null };
  counted: boolean;
  motivo: string | null;
  logistic_type: string | null;
  itens: {
    item_id: string | null;
    sku: string;
    title: string | null;
    qtd: number;
    unit_price_c: number;
    thumbnail: string | null;
    ads_dia_c: number;
    vendas_dia: number;
  }[];
  bruto_c: number;
  tarifa_c: number;
  frete_c: number;
  cupom_c: number;
  liquido_c: number;
  cmv_c: number | null;
  imposto_c: number | null;
  entrega_c: number;
  lucro_c: number | null;
  margem_bp: number | null;
  ads_c: number;
  lucro_apos_ads_c: number | null;
  margem_apos_ads_bp: number | null;
  missing_skus: string[];
};

export type AdsSales = {
  rows: AdsSaleRow[];
  page: number;
  per_page: number;
  total_rows: number;
  totals: {
    vendas?: number;
    bruto_c?: number;
    ads_c?: number;
    lucro_c?: number;
    lucro_apos_ads_c?: number;
    margem_bp: number | null;
    margem_apos_ads_bp: number | null;
    ads_sem_venda_c: number;
  };
};
