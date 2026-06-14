# Constraints

## Purpose

This document defines the project goal, MVP scope, security constraints, technical constraints, coding style, and definition of success for Video Note Agent.

## Project Goal

The purpose of this project is:

The architecture is local-first but cloud-ready.

The system must work locally without cloud deployment.

Cloud systems are optional orchestration and runtime targets for future phases.

### Input

- A YouTube video URL

Future phases should support local video files:

- MP4
- MOV
- MKV

Future phases should support ASR providers:

- Volcengine
- Tencent ASR
- Alibaba ASR
- Deepgram
- AWS Transcribe

All supported sources should converge into transcript text before downstream processing.

### Output

- `output/<safe-video-folder-name>/metadata.json`
- `output/<safe-video-folder-name>/01_raw_transcript.txt`
- `output/<safe-video-folder-name>/02_formatted_transcript.md`
- `output/<safe-video-folder-name>/03_cleaned_content.md`
- `output/<safe-video-folder-name>/04_notes_outline.md`

These local files are the primary source of truth.

External publishing systems are optional secondary destinations.

`metadata.json` must contain:

- `title`
- `url`
- `source`
- `author`
- `duration`
- `language`
- `tags`
- `status`
- `created_at`
- `summary`
- `processing_method`

Unavailable values must use empty strings or empty arrays.

The Notes should contain:

- Executive Summary
- Key Takeaways
- Structured Outline
- Action Items when explicitly present in the source content

The cleaned content file should contain an Edited Transcript.

## MVP Scope

The MVP only supports:

- YouTube URLs
- Existing subtitles

Local video support is part of Phase 2.

Whisper and faster-whisper are part of Phase 2 and are not part of Phase 1.

The MVP does NOT support:

- Telegram Bot
- Discord Bot
- Feishu Bot
- Notion Integration
- Feishu Integration
- Docker
- Whisper
- Local LLM
- OpenAI API
- Multi-user support

## Security Constraints

The application must NOT:

- Read local user documents
- Read email accounts
- Read browser history
- Access Google Drive
- Access Notion
- Access Feishu
- Execute arbitrary shell commands

The application only processes:

- User supplied YouTube URLs
- Downloaded subtitles

Phase 2 adds user supplied local video files as an allowed input source.

Phase 3 adds configurable LLM providers for improved cleaned content and notes.

Ollama remains supported as a private local-network LLM source.

Cloud LLM providers are allowed only when explicitly configured by the user with environment variables.

Allowed Phase 3 LLM environment variables:

- `LLM_PROVIDER`
- `LLM_MODEL`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `CLAUDE_API_KEY`
- `ANTHROPIC_API_KEY`
- `CLAUDE_BASE_URL`
- `GEMINI_API_KEY`
- `GEMINI_BASE_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `QWEN_API_KEY`
- `QWEN_BASE_URL`

The Ollama API must not be exposed publicly.

Allowed LLM providers:

- `ollama`
- `openai`
- `claude`
- `gemini`
- `deepseek`
- `qwen`

If the selected LLM provider is unavailable, times out, or returns invalid content, the application must use the rule-based fallback and still write local output files.

Phase 4 adds an output adapter layer.

Output adapters may only publish generated project assets.

Output adapters must consume the canonical local files, including `metadata.json`.

Output adapters must not:

- Generate transcripts
- Generate notes
- Read unrelated local files
- Read external account contents
- Prevent local output generation when unavailable

Future external adapters must use explicit environment configuration.

Phase 5 adds an optional Notion adapter.

Allowed Phase 5 environment variables:

- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `NOTION_PARENT_PAGE_ID`

The Notion adapter may create database pages or parent-page children from generated project assets.

The Notion adapter must not read unrelated Notion pages or databases.

Phase 6 adds additional optional output adapters.

Allowed Phase 6 Obsidian environment variables:

- `OBSIDIAN_VAULT_PATH`
- `OBSIDIAN_FOLDER`

The Obsidian adapter may write generated notes into the configured vault folder.

The Obsidian adapter must not scan or read unrelated vault files.

Allowed Phase 6 Feishu environment variables:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_VIDEO_NOTES_FOLDER_TOKEN`
- `FEISHU_PARENT_FOLDER_TOKEN`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_BITABLE_TABLE_ID`

The Feishu adapter may create documents from generated project assets in the configured Feishu folder.

The Feishu adapter may create Bitable records from `metadata.json` when explicitly configured.

The Feishu adapter must not read unrelated Feishu documents or folders.

The Feishu adapter should not send raw Markdown as the final document representation.

The Feishu adapter should convert generated notes into structured Feishu document blocks:

- Heading 1
- Heading 2
- Heading 3
- Paragraph
- Bullet List
- Numbered List

Doubao Speech ASR is the first implemented ASR provider.

Allowed Doubao Speech ASR environment variables:

- `TRANSCRIPTION_PROVIDER`
- `DOUBAO_ASR_APP_ID`
- `DOUBAO_ASR_ACCESS_TOKEN`
- `DOUBAO_ASR_RESOURCE_ID`
- `DOUBAO_ASR_SUBMIT_URL`
- `DOUBAO_ASR_QUERY_URL`
- `DOUBAO_ASR_LANGUAGE`
- `DOUBAO_ASR_AUDIO_FORMAT`
- `DOUBAO_ASR_ENABLE_ITN`
- `DOUBAO_ASR_ENABLE_PUNC`
- `DOUBAO_ASR_ENABLE_DDC`
- `DOUBAO_ASR_SHOW_UTTERANCES`

Volcengine Big Model Recording File Recognition requires an audio URL accessible by Volcengine.

Local audio files may be uploaded temporarily to private Volcengine TOS storage to create a presigned URL for ASR.

Credential boundaries:

- Volcengine TOS uses IAM AK/SK.
- Doubao Speech ASR uses old-console AppId and Access Token.
- Doubao Speech ASR must not use IAM AK/SK.
- Doubao Speech ASR must not use `open.volcengineapi.com`, `Action=SubmitRecognitionTask`, `Version=2023-08-01`, or HMAC-SHA256 signing.

Allowed Volcengine TOS environment variables:

- `VOLCENGINE_ACCESS_KEY_ID`
- `VOLCENGINE_SECRET_ACCESS_KEY`
- `TOS_BUCKET`
- `TOS_REGION`
- `TOS_ENDPOINT`

TOS storage constraints:

- The bucket must remain private.
- Audio objects are temporary transport files only.
- Presigned GET URLs should expire after 1 hour.
- Audio object keys should use `audio/{yyyy-mm-dd}/{uuid}.{ext}`.
- Uploaded audio should be deleted after ASR finishes.
- Delete failures should be reported without discarding a successful transcript.

Cloud deployment is planned but not implemented.

Phase 7 adds an optional Telegram input adapter.

Allowed Phase 7 environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_IDS`

The Telegram adapter may accept YouTube URLs from explicitly allowed user IDs.

The Telegram adapter processes accepted URLs through a single FIFO queue.

If multiple URLs arrive while one video is processing, later URLs must wait until earlier URLs finish.

The Telegram adapter must not:

- Accept arbitrary shell commands
- Accept unrestricted users
- Read local files from Telegram messages
- Send unrelated local files

Phase 8 adds Docker packaging.

Docker deployment must:

- Keep local output mounted as a volume
- Read secrets from environment variables or `.env`
- Avoid baking secrets into the image
- Avoid exposing public ports by default

## Technical Constraints

### Language

- Python 3.12+

Dependencies should be minimal.

### Preferred Libraries

- yt-dlp
- requests

### Avoid

- Heavy frameworks
- Complex databases

### Storage

- Local files only

Local files are always the primary source of truth.

External systems are optional publishing destinations.

Remote private services reachable through the user's private network, such as Tailscale Ollama, are allowed for Phase 3.

User-configured LLM APIs are allowed for Phase 3. API keys must be read from environment variables or `.env` and must not be committed.

Docker containers may access configured private services through the host network environment when explicitly configured by the user.

## Coding Style

### Requirements

- Simple structure
- Clear functions
- Readable code
- No over-engineering

The MVP should be understandable by a junior developer.

## Definition of Success

Running:

```bash
python main.py <youtube_url>
```

Should generate:

```text
output/
└── <safe-video-folder-name>/
    ├── metadata.json
    ├── 01_raw_transcript.txt
    ├── 02_formatted_transcript.md
    ├── 03_cleaned_content.md
    └── 04_notes_outline.md
```
