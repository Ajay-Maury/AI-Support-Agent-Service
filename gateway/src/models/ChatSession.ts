import mongoose, { Schema, Document } from "mongoose";

// ── Message subdocument ───────────────────────────────────────────────────────

export interface IMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: Array<{
    filename: string;
    chunk_index: number;
    score: number;
  }>;
}

const MessageSchema = new Schema<IMessage>(
  {
    role: { type: String, enum: ["user", "assistant"], required: true },
    content: { type: String, required: true },
    timestamp: { type: Date, default: Date.now },
    sources: [
      {
        filename: String,
        chunk_index: Number,
        score: Number,
      },
    ],
  },
  { _id: false }
);

// ── Chat Session ──────────────────────────────────────────────────────────────

export interface IChatSession extends Document {
  session_id: string;
  messages: IMessage[];
  created_at: Date;
  updated_at: Date;
}

const ChatSessionSchema = new Schema<IChatSession>(
  {
    session_id: { type: String, required: true, unique: true, index: true },
    messages: [MessageSchema],
  },
  {
    timestamps: { createdAt: "created_at", updatedAt: "updated_at" },
  }
);

// TTL: auto-delete sessions older than 30 days
ChatSessionSchema.index({ updated_at: 1 }, { expireAfterSeconds: 30 * 24 * 3600 });

export const ChatSession = mongoose.model<IChatSession>(
  "ChatSession",
  ChatSessionSchema,
  "chat_sessions"
);
