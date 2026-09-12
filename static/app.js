const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const button = document.querySelector("#send-button");
const typing = document.querySelector("#typing");

const sessionKey = "vida-verde-chat-session";
let sessionId = localStorage.getItem(sessionKey);

if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem(sessionKey, sessionId);
}

function addMessage(text, role, toolUsed = false, resultCount = null) {
  const article = document.createElement("article");
  article.className = `message ${role}-message`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "assistant" ? "VV" : "TÚ";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  if (toolUsed) {
    const badge = document.createElement("div");
    badge.className = "tool-badge";
    badge.textContent = resultCount !== null
      ? `Catálogo consultado · ${resultCount} resultado(s)`
      : "Catálogo consultado";
    bubble.appendChild(badge);
  }

  article.appendChild(avatar);
  article.appendChild(bubble);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();

  if (!message) return;

  addMessage(message, "user");
  input.value = "";
  button.disabled = true;
  typing.classList.remove("hidden");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : { detail: await response.text() };

    if (!response.ok) {
      throw new Error(data.detail || "No se pudo procesar la pregunta.");
    }

    addMessage(data.response, "assistant", data.tool_used, data.result_count);
  } catch (error) {
    addMessage(`Ocurrió un error: ${error.message}`, "assistant");
  } finally {
    typing.classList.add("hidden");
    button.disabled = false;
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
