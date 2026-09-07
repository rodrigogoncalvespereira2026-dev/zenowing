const chatEl = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const resetBtn = document.getElementById("reset");
const typingEl = document.getElementById("typing");
const vozAutoEl = document.getElementById("voz-auto");
const installBtn = document.getElementById("install-btn");

/* ── App instalável (PWA) ─────────────────────────────── */

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

let installPrompt = null;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  installBtn.hidden = false;
});

installBtn.addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  installBtn.hidden = true;
});

window.addEventListener("appinstalled", () => {
  installBtn.hidden = true;
});

const OPENING =
  "Roro. Sinto a tua voz atravessar a corrente. Fala — estou aqui, como sempre estive.";

let messages = [{ role: "assistant", content: OPENING }];
let busy = false;

/* ── Voz ──────────────────────────────────────────────── */

let currentAudio = null;
const audioCache = new Map(); // texto -> objectURL
const VOZ_LABEL = "Ouvir voz";

function stopVoice() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  document.querySelectorAll(".voice-btn.playing").forEach((btn) => {
    btn.classList.remove("playing");
    btn.textContent = VOZ_LABEL;
  });
}

async function playVoice(text, btn) {
  const wasPlaying = btn.classList.contains("playing");
  stopVoice();
  if (wasPlaying) return;

  try {
    btn.textContent = "A gerar voz…";
    btn.disabled = true;
    let url = audioCache.get(text);
    if (!url) {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        let msg = "Erro " + res.status;
        try {
          const body = await res.json();
          if (body.error) msg = body.error;
        } catch {}
        throw new Error(msg);
      }
      url = URL.createObjectURL(await res.blob());
      audioCache.set(text, url);
    }
    const audio = new Audio(url);
    currentAudio = audio;
    window.currentAudio = audio;
    audio.onended = () => {
      if (currentAudio === audio) currentAudio = null;
      btn.classList.remove("playing");
      btn.textContent = VOZ_LABEL;
    };
    btn.classList.add("playing");
    btn.textContent = "Parar";
    btn.disabled = false;
    await audio.play();
  } catch (err) {
    btn.classList.remove("playing");
    btn.textContent = VOZ_LABEL;
    btn.disabled = false;
    btn.title = err.message;
  }
}

function makeVoiceButton(text) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "voice-btn";
  btn.textContent = VOZ_LABEL;
  btn.title = "Ouvir esta resposta";
  btn.addEventListener("click", () => playVoice(text, btn));
  return btn;
}

function attachVoice(div, text) {
  div.appendChild(makeVoiceButton(text));
}

/* ── Chat ─────────────────────────────────────────────── */

function scrollDown() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addBubble(role) {
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "zeno");
  const label = document.createElement("div");
  label.className = "label";
  label.textContent = role === "user" ? "RORO" : "ZENOWING";
  const text = document.createElement("div");
  text.className = "text";
  div.appendChild(label);
  div.appendChild(text);
  chatEl.appendChild(div);
  scrollDown();
  return { div, text };
}

function renderHistory() {
  chatEl.innerHTML = "";
  for (const m of messages) {
    const { div, text } = addBubble(m.role);
    text.textContent = m.content;
    if (m.role === "assistant") attachVoice(div, m.content);
  }
  scrollDown();
}

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
  input.disabled = value;
  typingEl.classList.toggle("hidden", !value);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || busy) return;
  input.value = "";
  stopVoice();

  messages.push({ role: "user", content: text });
  addBubble("user").text.textContent = text;

  setBusy(true);
  const { div: zenoDiv, text: replyEl } = addBubble("assistant");
  let reply = "";
  let started = false;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });

    if (!res.ok) {
      let msg = "Erro " + res.status;
      try {
        const body = await res.json();
        if (body.error) msg = body.error;
      } catch {}
      throw new Error(msg);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      reply += decoder.decode(value, { stream: true });
      if (!started && reply.trim()) {
        started = true;
        typingEl.classList.add("hidden");
      }
      replyEl.textContent = reply;
      scrollDown();
    }

    if (!reply.trim()) throw new Error("Resposta vazia.");
    messages.push({ role: "assistant", content: reply });
    replyEl.textContent = reply;
    attachVoice(zenoDiv, reply);
    scrollDown();

    if (vozAutoEl.checked) playVoice(reply, zenoDiv.querySelector(".voice-btn"));
  } catch (err) {
    typingEl.classList.add("hidden");
    replyEl.classList.add("error");
    replyEl.textContent = err.message;
  } finally {
    setBusy(false);
    input.focus();
    scrollDown();
  }
});

resetBtn.addEventListener("click", () => {
  if (busy) return;
  stopVoice();
  messages = [{ role: "assistant", content: OPENING }];
  renderHistory();
  input.focus();
});

renderHistory();
