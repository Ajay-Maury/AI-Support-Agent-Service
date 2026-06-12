import mongoose from "mongoose";
import app from "./app";
import { config } from "./config";

async function start() {
  try {
    await mongoose.connect(config.mongoUri, { dbName: config.mongoDbName });
    console.log("✅  Connected to MongoDB Atlas");

    app.listen(config.port, () => {
      console.log(`🚀  Gateway running on http://localhost:${config.port}`);
    });
  } catch (err) {
    console.error("❌  Failed to start:", err);
    process.exit(1);
  }
}

start();
