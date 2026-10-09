// Every call to the FastAPI backend goes through this file, so the components
// never build URLs or headers themselves.

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface VaultFile {
  id: number;
  filename: string;
  size: number;
  upload_time: string;
  virustotal_result: string | null;
}

export interface CurrentUser {
  username: string;
  email: string;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// FastAPI sends { detail: "..." } for HTTPException and { detail: [{ msg }] } for validation errors
function errorMessage(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg ?? "Invalid input").join(", ");
  }
  return fallback;
}

interface RequestOptions {
  method?: string;
  token?: string;
  json?: unknown;
  form?: FormData;
}

async function send(path: string, { method = "GET", token, json, form }: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
    });
  } catch {
    throw new ApiError(0, "Could not reach the server");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, errorMessage(body, `Request failed (${response.status})`));
  }
  return response;
}

async function request<T>(path: string, options?: RequestOptions): Promise<T> {
  const response = await send(path, options);
  return response.json() as Promise<T>;
}

export function register(username: string, email: string, password: string) {
  return request<{ message: string }>("/register", { method: "POST", json: { username, email, password } });
}

export async function login(username: string, password: string): Promise<string> {
  const data = await request<{ access_token: string }>("/login", { method: "POST", json: { username, password } });
  return data.access_token;
}

export function logout(token: string) {
  return request<{ message: string }>("/logout", { method: "POST", token });
}

export function getMe(token: string) {
  return request<CurrentUser>("/me", { token });
}

export function listFiles(token: string) {
  return request<VaultFile[]>("/files", { token });
}

export function uploadFile(token: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ file_id: number; filename: string }>("/files/upload", { method: "POST", token, form });
}

export function deleteFile(token: string, fileId: number) {
  return request<{ message: string }>(`/files/${fileId}`, { method: "DELETE", token });
}

export function checkScan(token: string, fileId: number) {
  return request<{ filename: string; scan_result: string | null }>(`/files/${fileId}/scan`, { token });
}

// The download endpoint needs the Authorization header, so a plain <a href> won't work;
// fetch the bytes instead and let the caller hand them to the browser.
export async function downloadFile(token: string, fileId: number): Promise<Blob> {
  const response = await send(`/files/${fileId}/download`, { token });
  return response.blob();
}
