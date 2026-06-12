import dotenv from "dotenv";
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || "3000", 10),
  mongoUri: process.env.MONGODB_URI || "",
  mongoDbName: process.env.MONGODB_DB_NAME || "rag_support_agent",
  fastapiUrl: process.env.FASTAPI_URL || "http://ai-service:8000",
  nodeEnv: process.env.NODE_ENV || "development",
};

// Validate required vars at startup
const required = ["MONGODB_URI"] as const;
for (const key of required) {
  if (!process.env[key]) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
}
