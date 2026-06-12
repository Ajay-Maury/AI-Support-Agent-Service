import express from "express";
import cors from "cors";
import morgan from "morgan";

import chatRouter from "./routes/chat";
import docsRouter from "./routes/docs";
import { errorHandler } from "./middleware/errorHandler";

const app = express();

app.use(cors());
app.use(morgan("dev"));
app.use(express.json());

// ── Routes ────────────────────────────────────────────────────────────────────

app.get("/health", (_req, res) => res.json({ status: "ok" }));
app.use("/api/chat", chatRouter);
app.use("/api/docs", docsRouter);

// ── Error handler (must be last) ──────────────────────────────────────────────

app.use(errorHandler);

export default app;
