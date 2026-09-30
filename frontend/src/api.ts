import type { Session } from './types';
import { MOCK, mockApi } from './demo/api';

let accessToken = '';
export const setToken = (token: string) => { accessToken = token; };
export const getToken = () => accessToken;
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }

export async function api<T>(path: string, body?: unknown, method?: string, signal?: AbortSignal): Promise<T> {
  if (MOCK) return mockApi<T>(path, body, method, signal);
  const response = await fetch(`${(import.meta as ImportMeta & {env:Record<string,string>}).env.VITE_API_BASE_URL||'/api'}/${path}`, {
    method: method ?? (body === undefined ? 'GET' : 'POST'), signal, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }));
    const message = typeof data.detail === 'string' ? data.detail : data.detail?.map((x: {msg: string}) => x.msg).join('; ') || 'Request failed';
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}
export async function refreshSession(): Promise<Session> {
  const session = await api<Session>('auth/refresh', {});
  setToken(session.access_token);
  return session;
}
export async function authenticatedBlob(url: string): Promise<Blob> {
  const response = await fetch(url, { headers: MOCK ? {} : { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new ApiError('Unable to load recorded sample', response.status);
  return response.blob();
}
