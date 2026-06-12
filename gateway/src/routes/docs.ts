/**
 * Document routes
 *
 * POST /api/docs/upload          — upload .md or .txt file
 * GET  /api/docs/:id/status      — poll ingestion status
 * GET  /api/docs                 — list all documents
 */

import { Router, Request, Response, NextFunction } from "express";
import { ingestDocument, getIngestStatus, listDocuments } from "../services/fastapi";

const router = Router();

// ── POST /api/docs/upload ─────────────────────────────────────────────────────

router.post("/upload", async (req: Request, res: Response, next: NextFunction) => {
  try {
    // Express doesn't parse multipart — forward raw request body to FastAPI
    // The client sends multipart/form-data directly; we pass it through.
    const contentType = req.headers["content-type"] || "";
    if (!contentType.includes("multipart/form-data")) {
      return res.status(400).json({ error: "Expected multipart/form-data" });
    }

    // Collect raw body chunks
    const chunks: Buffer[] = [];
    for await (const chunk of req) {
      chunks.push(chunk as Buffer);
    }
    const rawBody = Buffer.concat(chunks);

    // Forward to FastAPI preserving content-type (includes boundary)
    const { default: fetch } = await import("node-fetch");
    const { config } = await import("../config");

    const fastapiRes = await fetch(`${config.fastapiUrl}/ingest`, {
      method: "POST",
      headers: { "content-type": contentType },
      body: rawBody,
    });

    const data = await fastapiRes.json();
    return res.status(fastapiRes.status).json(data);
  } catch (err) {
    next(err);
  }
});

// ── GET /api/docs/:id/status ──────────────────────────────────────────────────

router.get("/:id/status", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const data = await getIngestStatus(req.params.id);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

// ── GET /api/docs ─────────────────────────────────────────────────────────────

router.get("/", async (_req: Request, res: Response, next: NextFunction) => {
  try {
    const data = await listDocuments();
    res.json(data);
  } catch (err) {
    next(err);
  }
});

export default router;
