import type { ChatMessage, Health, Knowledge, Scan } from '../types';

const API = (import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL || '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init);
  let body: unknown;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    const message = typeof detail === 'string' ? detail : (detail as { message?: string } | null)?.message;
    const fallback: Record<number, string> = {
      413: 'Ảnh vượt giới hạn dung lượng hoặc 24 megapixel. Hãy chọn ảnh nhỏ hơn.',
      415: 'Định dạng ảnh chưa hỗ trợ. Hãy dùng JPEG, PNG hoặc WebP.',
      422: 'Máy chủ không đọc được ảnh này. Hãy thử xuất lại dưới dạng JPEG hoặc PNG.',
      503: 'Dịch vụ nhận diện hiện tạm ngưng. Mở thư viện SOICTERRA để tiếp tục tra cứu.',
    };
    throw new Error(message || fallback[response.status] || `Máy chủ trả về lỗi ${response.status}. Hãy thử lại.`);
  }
  return body as T;
}

export const getKnowledge = () => request<Knowledge>('/api/v1/waste-types');
export const getHealth = () => request<Health>('/api/v1/health');
export function postScan(file: File, signal: AbortSignal) {
  const form = new FormData(); form.append('image', file);
  return request<Scan>('/api/v1/scans', { method: 'POST', body: form, signal });
}
export function postRegionScan(file: File, box: [number, number, number, number], signal: AbortSignal) {
  const form = new FormData();
  form.append('image', file);
  for (const [index, name] of ['x1', 'y1', 'x2', 'y2'].entries()) form.append(name, String(box[index]));
  return request<Scan>('/api/v1/scans/region', { method: 'POST', body: form, signal });
}
export const postChat = (message: string, categoryIds: string[], history: ChatMessage[] = []) => request<{ answer?: string; assistant?: 'groq' | 'knowledge_base'; grounded_in?: string }>('/api/v1/chat', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, category_ids: categoryIds, history: history.slice(-8).map(turn=>({role:turn.role,content:turn.text})) }),
});
