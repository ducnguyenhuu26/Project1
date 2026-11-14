export type Material = {
  id: string; name: string; ai_class: number | null; examples: string[]; synonyms?: string[];
  description: string; do: string[]; avoid: string[]; caution: string; vn_tip: string;
};
export type Detection = {
  id: string; class_id: number; category_id: string | null; label: string; material_id: string | null;
  advice_id?: string | null; confidence: number | null; bbox_xyxy: [number, number, number, number];
  origin: string; status: string; model_version: string | null;
};
export type Scan = {
  mode: string; model_version: string | null; taxonomy_version: string; supported_category_ids: string[];
  image_width: number; image_height: number; detections: Detection[];
  summary: { category_id: string; material_id: string; advice_id?: string | null; name: string; estimated_count: number }[];
  advice: Material[]; warnings: string[];
};
export type Category = { id: string; name_vi: string; detection_supported: boolean; object_type_id: string | null; classification_level: string; material_id: string };
export type Knowledge = { materials: Material[]; categories: Category[]; faq: { question: string; answer: string }[]; updated_at: string; sources: string[]; taxonomy_version: string };
export type HistoryEntry = { id?: string; when: string; detected?: string[]; final?: string[]; corrected?: boolean };
export type ChatMessage = { role: 'assistant' | 'user'; text: string; source?: 'groq' | 'knowledge_base'; groundedIn?: string };
export type Health = { status: string; mode: string; model_status: string; model_version: string | null; supported_category_ids: string[] };
export type RecommendationResult = { status: string; object_id?: string; category_id?: string; stream_label?: string; headline?: string; assessment?: string; recommendation?: string; context_response?: string; practical_steps?: string[]; why?: string; next_step?: string; review_status?: string; sources?: { id: string; title: string; scope: string; url: string }[]; avoid?: string[]; cautions?: string[]; reasons?: string[]; notice?: string; local_collection_verified?: boolean };
export type ItemSession = { confirmedObjectId: string; answers: Record<string, string>; recommendation: RecommendationResult | null };
