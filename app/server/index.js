import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import cors from "cors";
import previewRoutes, { warmPreviewTeamCache } from "./routes/preview.js";
import slateRoutes from "./routes/slate.js";
import { defaultSeason, previewSeason } from "./db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = Number(process.env.DATABRICKS_APP_PORT || process.env.PORT || 8000);

app.use(cors());
app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    defaultSeason: defaultSeason(),
    previewSeason: previewSeason(),
  });
});

app.use("/api/preview", previewRoutes);
app.use("/api", slateRoutes);

app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(500).json({ error: err.message || "Server error" });
});

const dist = path.join(__dirname, "../client/dist");
app.use(express.static(dist));
app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api")) return next();
  res.sendFile(path.join(dist, "index.html"), (err) => {
    if (err) {
      res
        .status(503)
        .send("Client not built. Run npm run build in the app/ directory.");
    }
  });
});

app.listen(port, () => {
  console.log(`Saturday HQ listening on http://localhost:${port}`);
  // Don't block boot — warm Season Preview team payloads in the background.
  // Set PREVIEW_CACHE_WARM=0 to skip (useful for cold-path benchmarking).
  if (process.env.PREVIEW_CACHE_WARM !== "0") {
    warmPreviewTeamCache().catch((err) => {
      console.error("Preview team cache warm failed:", err.message || err);
    });
  } else {
    console.log("Preview team cache warm skipped (PREVIEW_CACHE_WARM=0)");
  }
});
