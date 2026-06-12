/**
 * Chat routes
 *
 * POST /api/chat/stream   — SSE streaming answer + sources
 * POST /api/chat          — non-streaming answer
 * GET  /api/chat/:id      — load session history
 * GET  /api/chat          — list sessions
 */

import { Router, Request, Response, NextFunction } from "express";
import { nanoid } from "nanoid";
import { z } from "zod";
import { ChatSession } from "../models/ChatSession";
import { queryAI, queryAIStream, ChunkSource } from "../services/fastapi";
import { AppError } from "../middleware/errorHandler";

const router = Router();

const ChatBody = z.object({
  question: z.string().min(1).max(1000),
  session_id: z.string().optional(),
});

// ── Helper: ensure session exists ─────────────────────────────────────────────

async function ensureSession(sessionId?: string): Promise<string> {
  const id = sessionId || nanoid();
  const exists = await ChatSession.findOne({ session_id: id });
  if (!exists) {
    await ChatSession.create({ session_id: id, messages: [] });
  }
  return id;
}

// ── POST /api/chat/stream — SSE streaming ─────────────────────────────────────

router.post("/stream", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { question, session_id } = ChatBody.parse(req.body);
    const sessionId = await ensureSession(session_id);

    // Save user message immediately
    await ChatSession.updateOne(
      { session_id: sessionId },
      {
        $push: { messages: { role: "user", content: question, timestamp: new Date() } },
        $set: { updated_at: new Date() },
      }
    );

    // SSE headers
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.setHeader("X-Accel-Buffering", "no");
    res.flushHeaders();

    // Send session_id as first event so client knows it
    res.write(`data: [SESSION]${sessionId}\n\n`);

    // Pipe FastAPI stream → client
    const fastapiRes = await queryAIStream(question, sessionId);
    const reader = fastapiRes.body!.getReader();
    const decoder = new TextDecoder();

    let fullAnswer = "";
    let sources: ChunkSource[] = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const raw = decoder.decode(value);
      // Split on SSE frame boundaries
      const lines = raw.split("\n\n").filter(Boolean);

      for (const line of lines) {
        const data = line.replace(/^data: /, "");

        if (data.startsWith("[SOURCES]")) {
          sources = JSON.parse(data.slice(9));
          // Forward sources frame to client
          res.write(`data: [SOURCES]${JSON.stringify(sources)}\n\n`);
        } else if (data === "[DONE]") {
          res.write("data: [DONE]\n\n");
        } else {
          fullAnswer += data.replace(/\\n/g, "\n");
          res.write(`data: ${data}\n\n`);
        }
      }
    }

    res.end();

    // Persist completed assistant message to MongoDB
    await ChatSession.updateOne(
      { session_id: sessionId },
      {
        $push: {
          messages: {
            role: "assistant",
            content: fullAnswer,
            timestamp: new Date(),
            sources,
          },
        },
        $set: { updated_at: new Date() },
      }
    );
  } catch (err) {
    next(err);
  }
});

// ── POST /api/chat — non-streaming ────────────────────────────────────────────

router.post("/", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { question, session_id } = ChatBody.parse(req.body);
    const sessionId = await ensureSession(session_id);

    await ChatSession.updateOne(
      { session_id: sessionId },
      { $push: { messages: { role: "user", content: question, timestamp: new Date() } } }
    );

    const result = await queryAI(question, sessionId);

    await ChatSession.updateOne(
      { session_id: sessionId },
      {
        $push: {
          messages: {
            role: "assistant",
            content: result.answer,
            timestamp: new Date(),
            sources: result.sources,
          },
        },
        $set: { updated_at: new Date() },
      }
    );

    res.json({ ...result, session_id: sessionId });
  } catch (err) {
    next(err);
  }
});

// ── GET /api/chat/:id — load session ─────────────────────────────────────────

router.get("/:id", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const session = await ChatSession.findOne({ session_id: req.params.id });
    if (!session) throw new AppError(404, "Session not found");
    res.json(session);
  } catch (err) {
    next(err);
  }
});

// ── GET /api/chat — list sessions ─────────────────────────────────────────────

router.get("/", async (_req: Request, res: Response, next: NextFunction) => {
  try {
    const sessions = await ChatSession.find(
      {},
      { session_id: 1, updated_at: 1, "messages": { $slice: -1 } }
    ).sort({ updated_at: -1 }).limit(20);
    res.json(sessions);
  } catch (err) {
    next(err);
  }
});

export default router;
