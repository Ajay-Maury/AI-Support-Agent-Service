/**
 * Thin HTTP client wrapping the FastAPI AI service.
 * All AI calls go through here — keeps routes clean.
 */

import { config } from "../config";

const BASE = config.fastapiUrl;

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ChunkSource {
  filename: string;
  chunk_index: number;
  score: number;
}

export interface QueryResult {
  answer: string;
  sources: ChunkSource[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`FastAPI error ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Non-streaming query — returns complete answer + sources.
 */
export async function queryAI(
  question: string,
  sessionId: string
): Promise<QueryResult> {
  return post<QueryResult>("/query", { question, session_id: sessionId });
}

/**
 * Streaming query — returns raw fetch Response body for SSE piping.
 */
export async function queryAIStream(
  question: string,
  sessionId: string
): Promise<Response> {
  const res = await fetch(`${BASE}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`FastAPI stream error ${res.status}: ${text}`);
  }

  return res;
}

/**
 * Forward a file upload to FastAPI for ingestion.
 */
export async function ingestDocument(formData: FormData): Promise<{
  doc_id: string;
  status: string;
  message: string;
}> {
  const res = await fetch(`${BASE}/ingest`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Ingest error ${res.status}: ${text}`);
  }

  return res.json() as Promise<{ doc_id: string; status: string; message: string }>;
}

/**
 * Check ingestion status of a document.
 */
export async function getIngestStatus(docId: string) {
  const res = await fetch(`${BASE}/ingest/${docId}`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

/**
 * List all ingested documents.
 */
export async function listDocuments() {
  const res = await fetch(`${BASE}/ingest`);
  if (!res.ok) throw new Error(`List docs failed: ${res.status}`);
  return res.json();
}
