# Backend-Datenfluss: OpenAI (GenericBackend) vs. MistralBackend

## Überblick
- **Ziel**: Gegenüberstellung des Datenflusses und der Funktionsoberflächen der beiden Backends, inkl. Streaming-Verhalten.
- **Quellen**: `vibe/core/llm/backend/generic.py`, `vibe/core/llm/backend/mistral.py`.

## Datenfluss (Non-Streaming)
### OpenAI-Style (GenericBackend + OpenAIAdapter)
1. **Vorbereitung**: Adapter baut Payload (`model`, `messages`, `temperature`, optionale `tools`, `tool_choice`, `max_tokens`). Bei Streaming-Flag fügt er `stream=true` hinzu, bei Provider `mistral` zusätzlich `stream_options.stream_tool_calls=true`.
2. **Request**: `GenericBackend.complete` ruft `_make_request` → `httpx.AsyncClient.post` auf `${provider.api_base}/chat/completions` mit JSON-Body. Zusätzliche Header (u.a. `user-agent`, `x-affinity`) werden im Agent gesetzt.
3. **Antwort-Parsing**: `OpenAIAdapter.parse_response` nimmt `choices[0].message|delta`, mappt zu `LLMMessage`, liest `finish_reason`, baut `LLMUsage`. Ergebnis wird als `LLMChunk` zurückgegeben.

### MistralBackend
1. **Vorbereitung**: `MistralMapper` wandelt `LLMMessage` → SDK-Messages und Tools → `mistralai.Tool`. `tool_choice` wird zu `ToolChoiceEnum` oder `FunctionName`.
2. **Request**: `MistralBackend.complete` ruft `mistralai.Mistral.chat.complete_async` mit bereits typisierten Objekten auf. `provider.api_base` wird in `__init__` in `server_url` (ohne Versionspfad) zerlegt.
3. **Antwort-Parsing**: Liest `choices[0].message`, konkateniert Content-Chunks, konvertiert Tool-Calls zurück in `ToolCall`, baut `LLMUsage` und `finish_reason`, liefert `LLMChunk`.

## Streaming-Verhalten
- **OpenAI-Style**: `complete_streaming` nutzt `_make_streaming_request` (SSE-Zeilen, `data:`). Jeder empfangene JSON-Chunk wird durch `OpenAIAdapter.parse_response` geschickt. Tool-Call-Deltas werden per `index` aggregiert; Finish erfolgt bei `data: [DONE]`.
- **MistralBackend**: `chat.stream_async` liefert SDK-Chunks. Jede Delta-Nachricht wird per Mapper in `LLMMessage` (Content-Append, Tool-Calls) übersetzt; `finish_reason` kommt aus `chunk.data.choices[0].finish_reason`. Usage kann erst im finalen Chunk gesetzt sein; Code füllt sie pro Chunk falls vorhanden.

## Methodenübersicht
| Methode                       | GenericBackend (OpenAI)                         | MistralBackend                       | Notes |
|-------------------------------|-------------------------------------------------|--------------------------------------|-------|
| `__init__(provider, timeout, client=None)` | Baut httpx-Client lazy; speichert Provider/Timeout | Zerlegt `api_base` in `server_url`; speichert API-Key/Timeout | Mistral validiert URL-Format |
| `__aenter__/__aexit__`        | Öffnet/ schließt httpx.AsyncClient              | Öffnet/ schließt `mistralai.Mistral` | Unterschiedliche Client-Typen |
| `_get_client`                 | Erstellt httpx.AsyncClient bei Bedarf           | Erstellt Mistral-SDK-Client          | Lazy init in beiden |
| `complete`                    | Adapter → HTTP POST → Adapter-Parsing           | SDK `chat.complete_async` → Mapper-Parsing | Beide liefern `LLMChunk` |
| `complete_streaming`          | SSE-Loop (`data:`) → Adapter-Parsing            | SDK `chat.stream_async` → Mapper-Parsing | Finish-Signal via `[DONE]` vs. SDK-Chunk `finish_reason` |
| `_make_request`               | httpx POST + JSON decode                        | –                                    | Nur Generic |
| `_make_streaming_request`     | httpx stream + Zeilenparser                     | –                                    | Nur Generic |
| `count_tokens`                | Fire-and-forget Completion mit `max_tokens=16`  | Wiederverwendet `complete` mit `max_tokens=1` | Unterschiedliche Minimal-Token-Annahme |
| `close`                       | Schließt eigenen httpx-Client                   | – (SDK-Context schließt im Exit)     | Nur Generic |
| Mapper/Adapter                | `OpenAIAdapter` (Payload/Header/Parse)          | `MistralMapper` (Message/Tool/Choice Mapping) | Spezifische Hilfs-Klassen |

## Unterschiede (kompakt in Tabelle)
| Aspekt              | OpenAI-Style (GenericBackend)                                                     | MistralBackend                                                             |
|---------------------|-----------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| Transport           | Rohes HTTP (`httpx`), manuelles JSON/SSE-Parsing                                  | Mistral SDK (`mistralai`), typisierte Requests/Responses                   |
| Payload-Form        | Dict → JSON; `stream`-Flag, `stream_options` für Mistral-Provider                 | Typed SDK-Objekte (`Tool`, `ToolChoice`, Messages)                         |
| Header-Handling     | Adapter + Agent setzen Header (z.B. `user-agent`, `x-affinity`, optional Auth)    | Übergibt `http_headers` direkt an SDK                                     |
| Tool-Calls          | Tools werden als OpenAI-Format gesendet; `tool_choice` kann `auto/any/none/required` sein | Tools als SDK-`Tool`; `tool_choice` als Enum/FunctionName                 |
| Streaming           | SSE-Lines, `[DONE]` Terminator; Tool-Call-Deltas per Index aggregiert             | SDK-Stream liefert Delta-Objekte mit `finish_reason` pro Chunk             |
| Error-Handling      | `BackendErrorBuilder` für `httpx.HTTPStatusError`/`RequestError`                  | `BackendErrorBuilder` für `mistralai.SDKError`/`httpx.RequestError`        |
| Tokenzählung        | Extra Completion mit `max_tokens=16`, prüft `usage`                               | Wiederverwendet `complete` mit `max_tokens=1`, erwartet `usage`            |
| Client-Lifecycle    | Optional externer httpx-Client; `close()` vorhanden                               | SDK-Client nur via Context; kein separates `close()`                      |
| API-Base            | Nutzt `provider.api_base` unverändert                                             | Erwartet `<server>/vX` und trennt Version ab                               |

## Methoden-Diff (oberflächliche Signaturen)
```diff
# Gemeinsamer Kern
__init__, __aenter__, __aexit__, _get_client, complete, complete_streaming, count_tokens

# Nur GenericBackend (OpenAI-Style)
_make_request
_make_streaming_request
close

# Nur MistralBackend
# (kein separates close, kein eigener HTTP-Parser; SDK-Client übernimmt)
# zusätzliche Mapper-Hilfen in MistralMapper:
#   prepare_message, prepare_tool, prepare_tool_choice,
#   parse_content, parse_tool_calls
```

## Beobachtungen zu Streaming-Ende
- OpenAI-Style terminiert ausschließlich über die `[DONE]`-Zeile. `finish_reason` kann `tool_calls`/`stop` sein, aber der Agent hört dadurch nicht auf: die Deltas werden bis zum `[DONE]` gesammelt, danach werden Tool-Calls ausgeführt und eine neue LLM-Runde gestartet.
- Mistral-Stream terminiert, wenn das SDK das Stream-Ende signalisiert; `finish_reason` in einem Chunk (z. B. `tool_calls`) beendet den Stream nicht eigenständig, sondern markiert nur den letzten Delta-Inhalt. Usage-Daten können erst im finalen Chunk gesetzt werden, der Code propagiert sie pro Chunk, falls vorhanden.

## Ablaufdiagramm: 3 Tool-Calls in einer Schleife (Textform)
1) User → Agent: Prompt  
2) Agent → LLM: Completion-Request (messages, tools, `stream=true`)  
3) LLM → Agent (Streaming): mehrere Deltas mit Content/Tool-Calls (`finish_reason: tool_calls`, Stream läuft weiter)  
4) Agent führt Tool 1 aus → Tool 1 → Agent: Result 1  
5) Agent → LLM: neue Completion mit Tool-Result in den Messages  
6) LLM → Agent (Streaming): Deltas mit ggf. weiterem Tool-Call (`finish_reason: tool_calls`)  
7) Agent führt Tool 2 aus → Tool 2 → Agent: Result 2  
8) Agent → LLM: weitere Completion mit beiden Tool-Resulten im Verlauf  
9) LLM → Agent (Streaming): Deltas mit drittem Tool-Call (`finish_reason: tool_calls`)  
10) Agent führt Tool 3 aus → Tool 3 → Agent: Result 3  
11) Agent → LLM: letztes Completion mit allen Tool-Resulten  
12) LLM → Agent: Content ohne Tools (`finish_reason: stop`, bzw. `[DONE]` bei OpenAI-Style)  
13) Agent → User: finaler Assistant-Output  

Hinweise:
- `finish_reason=tool_calls` beendet weder Stream noch Agent-Schleife; erst `[DONE]` (OpenAI-Style) oder das SDK-Stream-Ende (Mistral) stoppt den Stream.
- Nach jedem Tool-Result wird eine neue Completion gestartet; das Loop-Ende erfolgt erst, wenn das LLM keinen Tool-Call mehr liefert und `finish_reason` auf `stop` steht.

## Beziehung: GenericBackend ↔ OpenAIAdapter
- `GenericBackend` kennt kein konkretes API-Format. Es delegiert die Request/Response-Formate an einen registrierten Adapter über `BACKEND_ADAPTERS[api_style]`.
- `OpenAIAdapter` ist der Adapter für `api_style="openai"` und wird von `GenericBackend` verwendet, sobald der Provider `backend=GENERIC` und `api_style=openai` konfiguriert ist.
- Der Adapter kapselt:
  - Payload-Erzeugung (`build_payload`, `prepare_request`)
  - Header-Erzeugung (inkl. Auth)
  - Response-Parsing (`parse_response`) sowohl für volle Responses als auch Streaming-Deltas.
- `GenericBackend` übernimmt Transport (httpx) und Retry/Fehlerbehandlung; der Adapter liefert nur endpoint/headers/body und kann die Rohdaten in `LLMChunk` übersetzen.

## Ablauf Streaming-Response (OpenAI-Style) in Textform
1) Agent ruft `GenericBackend.complete_streaming(...)`  
2) `GenericBackend` fragt `OpenAIAdapter.prepare_request(...)` → liefert endpoint, headers, body (mit `stream=true`, ggf. `stream_options`).  
3) `GenericBackend._make_streaming_request` öffnet HTTP-Stream (`httpx.stream POST`).  
4) Für jede empfangene Zeile `data: {json}`:  
   - Parst JSON  
   - Ruft `OpenAIAdapter.parse_response` → `LLMChunk` (kann Content, Tool-Call-Deltas, finish_reason enthalten)  
   - Yield an Agent (`_chat_streaming`), der Content puffert und Tool-Calls aggregiert.  
5) Bei `data: [DONE]` wird der Stream beendet.  
6) Agent baut aus den gesammelten Chunks die finale Assistant-Message (Content + aggregierte Tool-Calls), setzt `_last_chunk` und startet ggf. Tool-Execution.  


## Fazit
- Beide Backends unterstützen mehrstufige Tool-Call-Ketten; Unterschiede liegen primär in Transport (HTTP vs. SDK), Payload-Form und Fehler-/Lifecycle-Handling.
- Streaming-Mechanismus unterscheidet sich technisch (SSE vs. SDK-Stream), ist aber funktional äquivalent: beide liefern fortlaufend Deltas inkl. Tool-Calls und Finish-Signal.
