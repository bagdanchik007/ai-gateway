/**
 * Minimale Chat-Logik für die AI-Gateway-Demo-UI.
 *
 * EventSource kann kein POST und keine eigenen Header (Authorization) senden,
 * daher wird SSE hier manuell über fetch() + ReadableStream geparst statt
 * über die EventSource-API — das ist der Preis dafür, echte Bearer-Auth mit
 * Streaming zu kombinieren.
 */

const STORAGE_KEY = "ai-gateway-demo-settings";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const apiKeyEl = document.getElementById("api-key");
const modelEl = document.getElementById("model");
const fallbackModelsEl = document.getElementById("fallback-models");
const useStreamEl = document.getElementById("use-stream");
const clearBtn = document.getElementById("clear-btn");

let history = [];

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const settings = JSON.parse(raw);
    if (settings.apiKey) apiKeyEl.value = settings.apiKey;
    if (settings.model) modelEl.value = settings.model;
  } catch {
    // Kaputte/alte gespeicherte Settings ignorieren, statt die Seite zu brechen.
  }
}

function saveSettings() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ apiKey: apiKeyEl.value, model: modelEl.value })
  );
}

function appendMessage(role, content) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = content;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function buildRequestBody(userMessage) {
  const fallbackModels = fallbackModelsEl.value
    .split(",")
    .map((m) => m.trim())
    .filter(Boolean);

  return {
    model: modelEl.value.trim(),
    messages: [...history, { role: "user", content: userMessage }],
    stream: useStreamEl.checked,
    ...(fallbackModels.length > 0 ? { fallback_models: fallbackModels } : {}),
  };
}

async function sendNonStreaming(body) {
  const response = await fetch("/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKeyEl.value.trim()}`,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error?.message || `HTTP ${response.status}`);
  }
  return data.choices[0].message.content;
}

async function sendStreaming(body, onDelta) {
  const response = await fetch("/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKeyEl.value.trim()}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data?.error?.message || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice("data: ".length);
      if (payload === "[DONE]") return;

      const chunk = JSON.parse(payload);
      if (chunk.error) {
        throw new Error(chunk.error.message);
      }
      const delta = chunk.choices?.[0]?.delta?.content;
      if (delta) onDelta(delta);
    }
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userMessage = inputEl.value.trim();
  if (!userMessage) return;
  if (!apiKeyEl.value.trim()) {
    appendMessage("error", "Bitte zuerst einen API-Key eintragen.");
    return;
  }

  saveSettings();
  appendMessage("user", userMessage);
  inputEl.value = "";
  formEl.querySelector("button").disabled = true;

  const body = buildRequestBody(userMessage);
  const assistantEl = appendMessage("assistant", "");

  try {
    let fullContent = "";
    if (useStreamEl.checked) {
      await sendStreaming(body, (delta) => {
        fullContent += delta;
        assistantEl.textContent = fullContent;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      });
    } else {
      fullContent = await sendNonStreaming(body);
      assistantEl.textContent = fullContent;
    }

    history.push({ role: "user", content: userMessage });
    history.push({ role: "assistant", content: fullContent });
  } catch (error) {
    assistantEl.remove();
    appendMessage("error", `Fehler: ${error.message}`);
  } finally {
    formEl.querySelector("button").disabled = false;
  }
});

clearBtn.addEventListener("click", () => {
  history = [];
  messagesEl.innerHTML = "";
});

loadSettings();
