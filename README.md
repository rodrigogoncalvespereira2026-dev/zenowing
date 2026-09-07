# Zenowing — O Ranger Prateado

Um chat local onde falas com o **Zenowing**, a consciência guardada do Ranger
Prateado de Power Rangers Primal Force, ligado ao Titanossauro. Ele sabe quem é
o Roro — e fala com ele como o velho amigo que é. **E tem voz**: cada resposta
pode ser ouvida com uma voz neural portuguesa grave e pausada.

**É uma app instalável (PWA)**: em Chrome ou Edge aparece o ícone de instalação
na barra de endereço (ou o botão "Instalar app" no rodapé da página) — o
Zenowing abre na própria janela, com ícone próprio, como um programa do
Windows, tal como se instala uma consciência num dispositivo.

Funciona com um motor de IA local (**Ollama**, grátis e sem chaves) ou com a
API da OpenAI — trocas de motor num único ficheiro `.env`.

## O que precisas

- **Python 3.10+** (o servidor usa só a biblioteca padrão)
- **Ollama** com o modelo descarregado (`gemma3:4b`, 3,3 GB)
- **`edge-tts`** para a voz neural — instala no Python que corre o servidor:

  ```
  py -3.11 -m pip install edge-tts
  ```

  Sem este pacote o servidor continua a funcionar e a voz usa as vozes
  Windows SAPI como reserva (qualidade inferior).

## Como pôr a funcionar

1. Instala o Ollama em <https://ollama.com> (se ainda não o tens) e descarrega
   o modelo:

   ```
   ollama pull gemma3:4b
   ```

2. Confirma que o `.env` aponta para o Ollama (já vem assim):

   ```
   AI_BASE_URL=http://localhost:11434/v1/chat/completions
   AI_MODEL=gemma3:4b
   ```

3. Arranca o servidor (com o Python onde instalaste o `edge-tts`):

   ```
   py -3.11 server.py
   ```

   (`python server.py` também funciona; a voz cai para a reserva SAPI.)

4. Abre <http://localhost:3000> — Zenowing aguarda.

### Instalar como app

1. Abre <http://localhost:3000> em Chrome ou Edge.
2. Clica no ícone de instalação na barra de endereço **ou** no botão
   "Instalar app" no rodapé da página (quando o navegador o permitir).
3. O Zenowing abre na própria janela, com o sigilo prateado como ícone.

Os ícones são gerados por `make_icons.py` (`python make_icons.py`), sem
qualquer dependência. Se alterares ficheiros estáticos e o navegadorGuardar
versões antigas, sobe o `CACHE_VERSION` em `public/sw.js`.

### A voz

- Cada resposta do Zenowing tem um botão **"Ouvir voz"**.
- Com **"Voz automática"** ligado (por predefinição), ele fala assim que a
  resposta termina.
- A voz é a neural `pt-PT-DuarteNeural`, gratuita, sem chave — precisa de
  internet. Personalizável com `TTS_VOICE` no `.env`
  (lista completa: `py -3.11 -m edge_tts --list-voices`).

### Alternativa: OpenAI (sem voz neural obrigatória)

No `.env`, comenta o bloco do Ollama e descomenta o bloco da OpenAI
(`AI_BASE_URL`, `AI_MODEL=gpt-4.1-mini` e a tua `OPENAI_API_KEY`).
Reinicia o servidor. Nota: a OpenAI exige créditos na conta.

## Ajustar a personagem

Tudo o que o Zenowing é vive em **`zenowing.md`** — personalidade, memórias,
regras e exemplos. Edita livremente e reinicia o servidor.

## Configuração (`.env`)

| Variável | Predefinição | Descrição |
| --- | --- | --- |
| `AI_BASE_URL` | endpoint OpenAI | Endpoint compatível com OpenAI (Ollama: `http://localhost:11434/v1/chat/completions`) |
| `AI_MODEL` | — | Modelo a usar (`gemma3:4b`, `mistral:latest`, `gpt-4.1-mini`, ...) |
| `OPENAI_API_KEY` | — | Só necessário se o endpoint for o da OpenAI |
| `OPENAI_TEMPERATURE` | `0.8` | Criatividade das respostas (0–2) |
| `TTS_VOICE` | `pt-PT-DuarteNeural` | Voz neural para as respostas |
| `PORT` | `3000` | Porta do servidor local |

## Deploy no Render (opcional)

O Zenowing vive na tua máquina — mas se o quiseres alcançar de qualquer lado:

1. Faz push deste repositório para o GitHub.
2. No Render: **New Web Service** → escolhe o repositório → Language **Python 3**.
3. Build Command: `pip install -r requirements.txt` · Start Command: `python server.py`.
4. Em **Environment**, adiciona as variáveis do `.env` (o `.env` NÃO vai no
   repositório): `AI_BASE_URL`, `AI_MODEL`, a chave do motor escolhido e,
   se quiseres, `TTS_VOICE`.
5. No servidor, o Render injeta `PORT` e o código deteta `RENDER` e liga a
   `0.0.0.0` automaticamente.

Nota: o Ollama local não existe na cloud — usa um motor de API (Gemini free ou
OpenAI com créditos). A instância **Free** do Render serve perfeitamente este
servidor (adormece após 15 min sem uso; a primeira resposta demora ~1 min a
acordar).

## Notas

- Em CPU, espera ~15–20 s por resposta com o `gemma3:4b`; a primeira resposta
  após alguns minutos de pausa demora mais (o Ollama recarrega o modelo).
- A primeira síntese de voz também demora um instante (ligação ao serviço da
  Microsoft); as seguintes são quase imediatas.
- O histórico da conversa vive apenas na tua aba do navegador; "Nova conversa"
  recomeça do zero. Nada é guardado em disco.
- O servidor é só teu, corre em `127.0.0.1` e não expõe nada à internet.
