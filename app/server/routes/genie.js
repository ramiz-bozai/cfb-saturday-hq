import { Router } from "express";
import {
  briefPrompt,
  chatContent,
  createMessage,
  extractText,
  generateTeamBrief,
  genieSpaceId,
  getMessage,
  getStoredBrief,
  isTerminalStatus,
  messageIds,
  previewSeason,
  startConversation,
  upsertBrief,
} from "../genie.js";

const router = Router();

router.get("/brief", async (req, res, next) => {
  try {
    const season = Number(req.query.season || previewSeason());
    const team = String(req.query.team || "").trim();
    if (!team) return res.status(400).json({ error: "team is required" });

    const brief = await getStoredBrief(season, team);
    res.json(brief);
  } catch (err) {
    if (String(err.message || "").includes("TABLE_OR_VIEW_NOT_FOUND") || err.status === 404) {
      return res.json({
        season: Number(req.query.season || previewSeason()),
        team: String(req.query.team || "").trim(),
        status: "missing",
        text: null,
        error: "genie_team_briefs table not found - run dbt model app_genie_team_briefs",
      });
    }
    next(err);
  }
});

/** Force regenerate one team brief via Genie and upsert. Ops / warm script helper. */
router.post("/brief/refresh", async (req, res, next) => {
  try {
    const season = Number(req.body?.season || req.query.season || previewSeason());
    const team = String(req.body?.team || req.query.team || "").trim();
    if (!team) return res.status(400).json({ error: "team is required" });

    const result = await generateTeamBrief(team, season);
    if (!result.ok || !result.text) {
      return res.status(502).json({
        error: result.error || "Genie did not return text",
        conversationId: result.conversationId,
        messageId: result.messageId,
      });
    }

    await upsertBrief({
      season,
      team,
      prompt: result.prompt || briefPrompt(team, season),
      briefText: result.text,
      conversationId: result.conversationId,
      messageId: result.messageId,
    });

    res.json({
      status: "ready",
      season,
      team,
      text: result.text,
      mode: result.mode || null,
      conversationId: result.conversationId,
      messageId: result.messageId,
    });
  } catch (err) {
    next(err);
  }
});

router.post("/chat", async (req, res, next) => {
  try {
    const question = String(req.body?.question || "").trim();
    const conversationId = req.body?.conversationId
      ? String(req.body.conversationId)
      : null;
    const team = req.body?.team ? String(req.body.team).trim() : null;
    const season = req.body?.season != null ? Number(req.body.season) : previewSeason();

    if (!question) return res.status(400).json({ error: "question is required" });

    // Match Databricks Genie UI phrasing as closely as possible.
    const content = chatContent({ question, team, season, conversationId });

    let started;
    if (conversationId) {
      started = await createMessage(conversationId, content);
    } else {
      started = await startConversation(content);
    }

    const { conversationId: convId, messageId } = messageIds(
      started,
      conversationId
    );
    if (!convId || !messageId) {
      return res.status(502).json({ error: "Genie did not return conversation/message ids" });
    }

    res.json({
      conversationId: convId,
      messageId,
      status: started?.message?.status || "IN_PROGRESS",
      spaceId: genieSpaceId(),
      contentSent: content,
    });
  } catch (err) {
    next(err);
  }
});

router.get("/chat/:conversationId/messages/:messageId", async (req, res, next) => {
  try {
    const { conversationId, messageId } = req.params;
    const msg = await getMessage(conversationId, messageId);
    const status = String(msg?.status || "UNKNOWN").toUpperCase();
    const text = status === "COMPLETED" ? extractText(msg) : null;
    res.json({
      conversationId,
      messageId,
      status,
      text,
      done: isTerminalStatus(status),
      spaceId: genieSpaceId(),
      error:
        status === "FAILED"
          ? msg?.error?.error || msg?.error?.message || "Genie failed"
          : null,
    });
  } catch (err) {
    next(err);
  }
});

export default router;
