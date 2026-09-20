"""Zenowing — servidor local do chat.

Serve a interface em public/ e faz de ponte com a API da OpenAI,
fazendo streaming da resposta da personagem token a token.
Usa apenas a biblioteca padrão de Python — não é preciso instalar nada.
"""

import json
import os
import socketserver
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
SYSTEM_PROMPT = (ROOT / "zenowing.md").read_text(encoding="utf-8")
LORE_COMUM = ROOT.parent / "lore-comum.md"


def carregar_lore_comum() -> str:
    """Lore comum do universo, partilhado com os outros personagens (pasta-mãe)."""
    try:
        return LORE_COMUM.read_text(encoding="utf-8")
    except OSError:
        return ""
MAX_HISTORY = 40
DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"


def get_api_url() -> str:
    """URL do motor de IA: OpenAI por defeito, ou qualquer endpoint compatível (ex.: Ollama)."""
    return os.environ.get("AI_BASE_URL", DEFAULT_API_URL).strip()


def load_env() -> None:
    """Lê o ficheiro .env sem substituir variáveis já definidas no sistema."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_error(text: str, status: int) -> str:
    try:
        message = json.loads(text).get("error", {}).get("message")
        if message:
            return f"OpenAI: {message}"
    except (json.JSONDecodeError, AttributeError):
        pass
    return f"OpenAI respondeu com o estado {status}."


def _synth_edge(text: str, voice: str) -> bytes:
    """Síntese com as vozes neurais da Edge (grátis, precisa de internet)."""
    import asyncio
    import edge_tts

    async def run() -> bytes:
        communicate = edge_tts.Communicate(text, voice, rate="-8%")
        buf = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    return asyncio.run(run())


def _synth_sapi(text: str) -> bytes:
    """Reserva sem dependências: vozes SAPI instaladas no Windows."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    txt_path = wav_path + ".txt"
    Path(txt_path).write_text(text, encoding="utf-8")
    try:
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'pt*' } | Select-Object -First 1; "
            "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
            "$s.SetOutputToWaveFile($args[0]); "
            "$s.Speak((Get-Content -Raw -Encoding UTF8 $args[1])); "
            "$s.Dispose()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script, wav_path, txt_path],
            check=True,
            capture_output=True,
        )
        return Path(wav_path).read_bytes()
    finally:
        for path in (wav_path, txt_path):
            try:
                Path(path).unlink()
            except OSError:
                pass


def synth_speech(text: str):
    """Devolve (bytes, content_type). edge-tts (mp3) com reserva SAPI (wav)."""
    voice = os.environ.get("TTS_VOICE", "pt-PT-DuarteNeural")
    try:
        return _synth_edge(text, voice), "audio/mpeg"
    except ImportError:
        return _synth_sapi(text), "audio/wav"


def call_openai(messages: list[dict]):
    """Chama a API compatível com OpenAI (OpenAI, Ollama local, ...) com streaming."""
    model = os.environ.get("AI_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    body = {"model": model, "messages": messages, "stream": True}
    try:
        body["temperature"] = float(os.environ.get("OPENAI_TEMPERATURE", "0.8"))
    except ValueError:
        pass

    def request(payload: dict):
        headers = {"Content-Type": "application/json"}
        if os.environ.get("OPENAI_API_KEY"):
            headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"
        req = urllib.request.Request(
            get_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=300)

    try:
        return request(body)
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        # Alguns modelos só aceitam a temperatura predefinida; tenta sem ela.
        if err.code == 400 and "temperature" in body and "temperature" in detail:
            body.pop("temperature")
            return request(body)
        raise RuntimeError(extract_error(detail, err.code)) from err


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # mantém a consola limpa
        pass

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json(404, {"error": "Não encontrado."})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(PUBLIC / "index.html", "text/html; charset=utf-8")
        elif self.path == "/style.css":
            self._serve_file(PUBLIC / "style.css", "text/css; charset=utf-8")
        elif self.path == "/app.js":
            self._serve_file(PUBLIC / "app.js", "text/javascript; charset=utf-8")
        elif self.path == "/manifest.webmanifest":
            self._serve_file(PUBLIC / "manifest.webmanifest", "application/manifest+json")
        elif self.path == "/sw.js":
            self._serve_file(PUBLIC / "sw.js", "text/javascript; charset=utf-8")
        elif self.path in ("/icon-192.png", "/icon-512.png"):
            self._serve_file(PUBLIC / self.path.lstrip("/"), "image/png")
        else:
            self._send_json(404, {"error": "Não encontrado."})

    def do_POST(self):
        if self.path == "/api/tts":
            self._handle_tts()
        elif self.path == "/api/chat":
            self._handle_chat()
        else:
            self._send_json(404, {"error": "Não encontrado."})

    def _handle_tts(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = (payload.get("text") or "").strip()
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Pedido inválido."})
            return
        if not text:
            self._send_json(400, {"error": "Texto vazio."})
            return
        try:
            audio, content_type = synth_speech(text[:2000])
        except Exception as err:
            self._send_json(502, {"error": f"Falha ao sintetizar a voz: {err}"})
            return
        if not audio:
            self._send_json(502, {"error": "Síntese de voz sem resultado."})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(audio)

    def _handle_chat(self) -> None:
        if "api.openai.com" in get_api_url() and not os.environ.get("OPENAI_API_KEY"):
            self._send_json(500, {
                "error": "A chave da API não está configurada. Cria o ficheiro .env "
                         "a partir de .env.example, define OPENAI_API_KEY e reinicia o servidor."
            })
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Pedido inválido."})
            return

        clean = [
            {"role": m["role"], "content": m["content"].strip()}
            for m in (payload.get("messages") or [])
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ][-MAX_HISTORY:]
        # Prompt próprio do Zenowing + lore comum do universo (pasta-mãe).
        lore = carregar_lore_comum()
        system_text = SYSTEM_PROMPT + (("\n\n---\n\n" + lore) if lore else "")
        messages = [{"role": "system", "content": system_text}, *clean]

        if not any(m["role"] == "user" for m in messages):
            self._send_json(400, {"error": "Mensagem vazia."})
            return

        try:
            upstream = call_openai(messages)
        except RuntimeError as err:
            self._send_json(502, {"error": str(err)})
            return
        except Exception:
            self._send_json(502, {"error": "Falha ao contactar a OpenAI."})
            return

        # Resposta em streaming: o corpo termina quando a ligação se fecha.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        try:
            for raw in upstream:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
                    continue
                if delta:
                    self.wfile.write(delta.encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # o utilizador fechou a página a meio da resposta


class ZenowingServer(ThreadingHTTPServer):
    """Como ThreadingHTTPServer, mas sem a pesquisa DNS inversa do arranque.

    O server_bind() original chama socket.getfqdn(), que pode bloquear o
    arranque durante muito tempo em máquinas com DNS lento ou mal configurado.
    """

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = "localhost"
        self.server_port = port


def resolve_port(default: int = 3000) -> int:
    """Lê a porta do ambiente, ignorando valores inválidos (ex.: PORT=0 herdado do sistema)."""
    try:
        port = int(os.environ.get("PORT", "").strip() or default)
    except ValueError:
        return default
    return port if 1 <= port <= 65535 else default


def resolve_host() -> str:
    """Na cloud (Render) liga a todas as interfaces; em local, só a esta máquina."""
    explicit = os.environ.get("BIND_HOST")
    if explicit:
        return explicit
    if os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"):
        return "0.0.0.0"
    return "127.0.0.1"


def main() -> None:
    load_env()
    port = resolve_port()
    host = resolve_host()
    server = ZenowingServer((host, port), Handler)
    print(f"Zenowing aguarda em http://{host}:{port}", flush=True)
    print(f"Motor: {get_api_url()}", flush=True)
    print(f"Modelo: {os.environ.get('AI_MODEL') or os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')}", flush=True)
    if "api.openai.com" in get_api_url() and not os.environ.get("OPENAI_API_KEY"):
        print("Aviso: OPENAI_API_KEY não definida — o chat devolverá erro até configurares o .env.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZenowing recolhe-se ao silêncio.")


if __name__ == "__main__":
    main()
