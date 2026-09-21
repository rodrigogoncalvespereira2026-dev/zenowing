const chatEl = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const resetBtn = document.getElementById("reset");
const typingEl = document.getElementById("typing");
const vozBtnEl = document.getElementById("voz-btn");
const vozTxtEl = document.getElementById("voz-txt");
const vozIcEl = document.getElementById("voz-ic");
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

/* ── Voz ────────────────────────────────────────────────
   Mesmo sistema do Alpha: síntese de fala do próprio browser
   (Web Speech API). Fala sozinho cada resposta, sem cliques.

   O browser só deixa sintetizar depois de um gesto do
   utilizador: até lá a resposta fica em espera e sai no
   primeiro toque.                                              */

const VOZ_LABEL = "Ouvir voz";
const synth = window.speechSynthesis;
let vozLigada = true;
let vozBloqueada = true;
let vozPendente = null;
let vozAtual = null;

function escolherVozPT() {
  if (!synth) return null;
  const vozes = synth.getVoices();
  return (
    vozes.find((v) => v.lang.includes("pt") && v.name.includes("Google")) ||
    vozes.find((v) => v.lang.includes("pt")) ||
    vozes.find((v) => v.lang.includes("es")) ||
    null
  );
}

function marcarBotao(btn, aFalar) {
  if (!btn) return;
  btn.classList.toggle("playing", aFalar);
  btn.textContent = aFalar ? "Parar" : VOZ_LABEL;
}

function falar(texto, { btn = null, forcar = false } = {}) {
  if (!synth || !texto) return;
  if (!forcar && !vozLigada) return;
  if (vozBloqueada) {
    vozPendente = { texto, btn };
    return;
  }
  synth.cancel();
  const voz = new SpeechSynthesisUtterance(texto);
  voz.lang = "pt-PT";
  voz.rate = 0.85;
  voz.pitch = 1.1;
  voz.volume = 1.0;
  const escolhida = escolherVozPT();
  if (escolhida) voz.voice = escolhida;
  voz.onstart = () => marcarBotao(btn, true);
  voz.onend = () => marcarBotao(btn, false);
  voz.onerror = () => marcarBotao(btn, false);
  vozAtual = voz;
  synth.speak(voz);
}

function pararVoz() {
  if (synth) synth.cancel();
  vozPendente = null;
  vozAtual = null;
  document.querySelectorAll(".voice-btn.playing").forEach((btn) => {
    btn.classList.remove("playing");
    btn.textContent = VOZ_LABEL;
  });
}

/** O primeiro gesto do utilizador é o que desbloqueia a síntese. */
function desbloquearVoz() {
  if (!vozBloqueada) return;
  vozBloqueada = false;
  const pendente = vozPendente;
  vozPendente = null;
  if (pendente) falar(pendente.texto, { btn: pendente.btn, forcar: true });
}

["pointerdown", "click", "keydown", "touchstart"].forEach((evento) => {
  window.addEventListener(evento, desbloquearVoz, { once: true, passive: true });
});

function makeVoiceButton(text) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "voice-btn";
  btn.textContent = VOZ_LABEL;
  btn.title = "Ouvir esta resposta";
  btn.addEventListener("click", () => {
    if (btn.classList.contains("playing")) {
      pararVoz();
      return;
    }
    desbloquearVoz();
    falar(text, { btn, forcar: true });
  });
  return btn;
}

function attachVoice(div, text) {
  div.appendChild(makeVoiceButton(text));
}

function atualizarBotaoVoz() {
  vozBtnEl.setAttribute("aria-pressed", String(vozLigada));
  vozTxtEl.textContent = vozLigada ? "Voz ligada" : "Voz desligada";
  vozIcEl.textContent = vozLigada ? "🔊" : "🔇";
}

vozBtnEl.addEventListener("click", () => {
  vozLigada = !vozLigada;
  atualizarBotaoVoz();
  if (!vozLigada) pararVoz();
});

atualizarBotaoVoz();

// O Chrome carrega a lista de vozes de forma assíncrona: aquece-a já.
if (synth) {
  synth.addEventListener("voiceschanged", () => {});
  synth.getVoices();
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
  pararVoz();

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

    // Fala sozinho, sem cliques (a caixa "Voz automática" é o interruptor).
    falar(reply, { btn: zenoDiv.querySelector(".voice-btn") });
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
  pararVoz();
  messages = [{ role: "assistant", content: OPENING }];
  renderHistory();
  input.focus();
});

renderHistory();
