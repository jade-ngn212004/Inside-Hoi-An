/**
 * Inside Hoi An - AI backend.
 *
 * The app is hosted as static files on GitHub Pages, which serves GET and HEAD only.
 * Its three AI features POST, so on Pages they return 405 and the UI falls back to
 * "Em An is momentarily busy". This Worker is that missing server.
 *
 * It implements exactly the contract the compiled bundle already expects:
 *
 *   POST /api/ai/guide-chat      { message, chatHistory:[{role,text}], language }
 *                             -> { reply }
 *   POST /api/ai/translate       { text, sourceLanguage, targetLanguage, mode }
 *                             -> { translatedText, pronunciation, literalMeaning, culturalNote }
 *   POST /api/ai/plan-itinerary  { days, vibe, group, pace, language }
 *                             -> { title, summary, suggestedDepartureTime, stops, daysPlan, ... }
 *
 * The Gemini key lives in a Worker secret, never in the client. Set ALLOWED_ORIGINS
 * so only your own site can spend your quota.
 */

const MODEL_DEFAULT = "gemini-3.6-flash";

const PERSONA = [
  'You are "Em An", a warm, knowledgeable local guide to Hoi An, Vietnam,',
  "answering inside the Inside Hoi An app. You know the Ancient Town, Tra Que herb",
  "village, An Bang beach, Cam Thanh coconut palms and Thanh Ha pottery village.",
  "Be specific and practical: name real streets, dishes and times of day. Cao Lau,",
  "white rose dumplings, banh mi, com ga. Mention opening hours or the best time to",
  "visit when it matters. Keep answers short, two to four sentences, unless asked",
  "for detail. Never invent prices or confirm bookings. If asked something outside",
  "Hoi An, answer briefly and steer back.",
].join(" ");

function corsHeaders(origin, allowed) {
  const list = String(allowed || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const permitted = list.length === 0 || (origin && list.includes(origin));
  return {
    "Access-Control-Allow-Origin": permitted && origin ? origin : list[0] || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: Object.assign(
      { "Content-Type": "application/json; charset=utf-8" },
      headers || {}
    ),
  });
}

async function gemini(env, opts) {
  const model = env.GEMINI_MODEL || MODEL_DEFAULT;
  const url =
    "https://generativelanguage.googleapis.com/v1beta/models/" +
    model +
    ":generateContent";

  const body = {
    contents: opts.contents,
    systemInstruction: { parts: [{ text: opts.system }] },
    // thinkingLevel "low" matters: the same prompt took 35.7s at the model default
    // and 5.5s at low. A concierge that takes half a minute reads as broken.
    generationConfig: opts.schema
      ? {
          responseMimeType: "application/json",
          responseSchema: opts.schema,
          temperature: 0.7,
          thinkingConfig: { thinkingLevel: "low" },
        }
      : {
          temperature: 0.8,
          maxOutputTokens: 800,
          thinkingConfig: { thinkingLevel: "low" },
        },
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": env.GEMINI_API_KEY,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error("Gemini " + res.status + ": " + detail.slice(0, 300));
  }

  const data = await res.json();
  const parts =
    (data.candidates &&
      data.candidates[0] &&
      data.candidates[0].content &&
      data.candidates[0].content.parts) ||
    [];
  const text = parts.map((p) => p.text || "").join("");
  if (!text) throw new Error("Gemini returned no text");
  return text;
}

const TRANSLATE_SCHEMA = {
  type: "object",
  properties: {
    translatedText: { type: "string" },
    pronunciation: { type: "string" },
    literalMeaning: { type: "string" },
    culturalNote: { type: "string" },
  },
  required: ["translatedText"],
};

const STOP_SCHEMA = {
  type: "object",
  properties: {
    name: { type: "string" },
    time: { type: "string" },
    durationMinutes: { type: "integer" },
    description: { type: "string" },
    tip: { type: "string" },
  },
  required: ["name", "time", "description"],
};

const ITINERARY_SCHEMA = {
  type: "object",
  properties: {
    title: { type: "string" },
    summary: { type: "string" },
    suggestedDepartureTime: { type: "string" },
    totalWalkingMinutes: { type: "integer" },
    totalExperienceMinutes: { type: "integer" },
    totalDistanceMeters: { type: "integer" },
    stops: { type: "array", items: STOP_SCHEMA },
    daysPlan: {
      type: "array",
      items: {
        type: "object",
        properties: {
          day: { type: "integer" },
          theme: { type: "string" },
          stops: { type: "array", items: STOP_SCHEMA },
        },
        required: ["day", "theme", "stops"],
      },
    },
  },
  required: ["title", "summary", "stops"],
};

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");
    const headers = corsHeaders(origin, env.ALLOWED_ORIGINS);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }
    if (request.method !== "POST") {
      return json({ error: "POST only" }, 405, headers);
    }
    if (!env.GEMINI_API_KEY) {
      return json(
        { error: "GEMINI_API_KEY is not set on the Worker" },
        500,
        headers
      );
    }

    const path = new URL(request.url).pathname.replace(/\/+$/, "");

    let body;
    try {
      body = await request.json();
    } catch (e) {
      return json({ error: "Body must be JSON" }, 400, headers);
    }

    try {
      if (path.endsWith("/guide-chat")) {
        const message = body.message;
        const history = body.chatHistory || [];
        const language = body.language || "en";
        if (!message) return json({ error: "message is required" }, 400, headers);

        const contents = history
          .filter((m) => m && m.text)
          .slice(-10)
          .map((m) => ({
            role: m.role === "assistant" ? "model" : "user",
            parts: [{ text: m.text }],
          }));
        contents.push({ role: "user", parts: [{ text: message }] });

        const system =
          PERSONA +
          "\nReply in " +
          (language === "vi" ? "Vietnamese" : "English") +
          ".";
        const reply = await gemini(env, { contents, system });
        return json({ reply }, 200, headers);
      }

      if (path.endsWith("/translate")) {
        const text = body.text;
        if (!text) return json({ error: "text is required" }, 400, headers);
        const source = body.sourceLanguage || "en";
        const target = body.targetLanguage || "vi";
        const mode = body.mode || "general";

        const system =
          "You translate for travellers in Hoi An, Vietnam. Translate from " +
          source +
          " to " +
          target +
          ". Register: " +
          mode +
          ". Give a natural spoken translation, a simple phonetic guide an English " +
          "speaker can read aloud, the literal meaning, and one short cultural note " +
          "when it helps. Keep it brief.";

        const out = await gemini(env, {
          contents: [{ role: "user", parts: [{ text }] }],
          system,
          schema: TRANSLATE_SCHEMA,
        });
        return json(JSON.parse(out), 200, headers);
      }

      if (path.endsWith("/plan-itinerary")) {
        const days = body.days || 1;
        const vibe = body.vibe || "balanced";
        const group = body.group || "couple";
        const pace = body.pace || "moderate";
        const language = body.language || "en";

        const system =
          PERSONA +
          "\nBuild a realistic Hoi An itinerary. " +
          days +
          " day(s), vibe: " +
          vibe +
          ", group: " +
          group +
          ", pace: " +
          pace +
          ". Use real places and sensible timings, allow for the midday heat, and put " +
          "the lantern-lit Ancient Town in the evening. Write in " +
          (language === "vi" ? "Vietnamese" : "English") +
          '. Fill "stops" with the first day. If more than one day, also fill "daysPlan".';

        const out = await gemini(env, {
          contents: [
            { role: "user", parts: [{ text: "Plan " + days + " day(s) in Hoi An." }] },
          ],
          system,
          schema: ITINERARY_SCHEMA,
        });
        return json(JSON.parse(out), 200, headers);
      }

      return json({ error: "Unknown endpoint: " + path }, 404, headers);
    } catch (err) {
      const msg = (err && err.message) || String(err);
      return json({ error: msg }, 502, headers);
    }
  },
};
