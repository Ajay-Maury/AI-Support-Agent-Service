import express from "express";
import cors from "cors";
import morgan from "morgan";
import fetch from "node-fetch";

import chatRouter from "./routes/chat";
import docsRouter from "./routes/docs";
import { errorHandler } from "./middleware/errorHandler";
import { config } from "./config";

const app = express();

app.use(cors());
app.use(morgan("dev"));
app.use(express.json());

// ── Routes ────────────────────────────────────────────────────────────────────

app.get("/health", async (_req, res) => {
  const fastapiHealthUrl = `${config.fastapiUrl.replace(/\/+$/, "")}/health`;

  try {
    const fastapiRes = await fetch(fastapiHealthUrl);
    if (!fastapiRes.ok) {
      const text = await fastapiRes.text();
      return res.status(503).json({
        status: "unhealthy",
        gateway: "ok",
        fastapi: {
          status: fastapiRes.status,
          detail: text,
        },
      });
    }

    const fastapiBody = await fastapiRes.json();
    return res.json({
      status: "ok",
      services: {
        gateway: "ok",
        fastapi: fastapiBody,
      },
    });
  } catch (error) {
    return res.status(503).json({
      status: "unhealthy",
      gateway: "ok",
      fastapi: {
        status: "unreachable",
        detail: error instanceof Error ? error.message : String(error),
      },
    });
  }
});

app.use("/api/chat", chatRouter);
app.use("/api/docs", docsRouter);

// ── Error handler (must be last) ──────────────────────────────────────────────

app.use(errorHandler);

export default app;
