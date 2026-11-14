// Vite embeds this public origin at build time. No credentials belong here.
export const API_BASE = ((import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL || '').replace(/\/+$/, '');
