# Video Note Agent

A local-first but cloud-ready video note generation system.

The project converts video content into structured notes that can later be integrated into personal knowledge management systems.

---

# Current Status

Current Roadmap:

```text
Phase 1 - YouTube Subtitle MVP: Completed
Phase 2 - Per-Video Output Workspace
Phase 3 - AI Note Processing
Phase 4 - Transcription Provider Layer
Phase 5 - Output Adapter Layer
Phase 6 - Cloud Deployment
```

Current Objective:

```text
Video Source
    ↓
Transcript Layer
    ↓
AI Note Processing
    ↓
Per-Video Local Workspace
    ↓
Output Adapter Layer
    ↓
Optional Cloud Orchestration
```

Local files are always the source of truth.

Cloud deployment is planned for the future but is not required for local use.

---

# MVP Features

The MVP supports:

- YouTube URL input
- Subtitle download
- Transcript generation
- YouTube audio ASR fallback when supported subtitles are unavailable
- Markdown note generation
- Local file output

Phase 2 creates a per-video output workspace with:

- `metadata.json`
- `01_raw_transcript.txt`
- `02_formatted_transcript.md`
- `03_cleaned_content.md`
- `04_notes_outline.md`

These files are the canonical source of truth for all publishing targets.

`metadata.json` contains:

```json
{
  "title": "",
  "url": "",
  "source": "",
  "author": "",
  "duration": "",
  "language": "",
  "tags": [],
  "status": "Processed",
  "created_at": "",
  "summary": "",
  "processing_method": ""
}
```

Phase 3 adds AI note processing.

Phase 4 defines a transcription provider layer for future local video and ASR providers.

Local files are always the primary source of truth.

External systems are optional publishing destinations.

Phase 5 defines an output adapter layer.

Phase 6 defines future cloud deployment.

---

# Setup

Use Python 3.12 or newer.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After activating the virtual environment, run commands with:

```bash
export OLLAMA_BASE_URL=http://100.111.104.41:11434
export OLLAMA_MODEL=qwen3:8b
export LLM_PROVIDER=qwen
export LLM_MODEL=qwen-plus
export QWEN_API_KEY=<your_qwen_api_key>
export QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
export NOTION_TOKEN=<your_notion_integration_token>
export NOTION_DATABASE_ID=<target_notion_database_id>
export NOTION_PARENT_PAGE_ID=<target_parent_page_id>
export OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
export OBSIDIAN_FOLDER="Video Notes"
export FEISHU_APP_ID=<your_feishu_app_id>
export FEISHU_APP_SECRET=<your_feishu_app_secret>
export FEISHU_VIDEO_NOTES_FOLDER_TOKEN=<target_feishu_folder_token>
export FEISHU_PARENT_FOLDER_TOKEN=<target_feishu_folder_token>
export FEISHU_BITABLE_APP_TOKEN=<target_feishu_bitable_app_token>
export FEISHU_BITABLE_TABLE_ID=<target_feishu_bitable_table_id>
export TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
export TELEGRAM_ALLOWED_USER_IDS=<comma_separated_user_ids>
python main.py <youtube_url>
python main.py /path/to/video.mp4
python main.py telegram
pytest
```

For Docker, copy the example environment file and fill in local values:

```bash
cp .env.example .env
```

Run one-shot processing:

```bash
docker compose run --rm video-note-agent "<youtube_url>"
```

Run Telegram polling:

```bash
docker compose up telegram-bot
```

Future local video processing through Docker will require an input volume mount. A future compose setup may use:

```text
./input:/app/input
./output:/app/output
```

The MVP does not support:

- Web UI

---

# Project Goals

Short-term Goal:

```text
Generate a dedicated local output folder for each processed video source.
```

Long-term Goal:

```text
Capture knowledge from video content regardless of source.
```

All supported sources should converge into a transcript first.

The transcript is the primary artifact for cleaned content, notes, and future integrations.

Generated knowledge assets are stored locally first:

```text
01_raw_transcript.txt
02_formatted_transcript.md
03_cleaned_content.md
04_notes_outline.md
```

Output adapters may publish those assets to:

- Local Markdown
- Notion
- Feishu Docs
- Google Docs
- Obsidian

Adapter design:

- Obsidian should generate YAML frontmatter from `metadata.json`.
- Notion uses `NOTION_DATABASE_ID` when configured, creating one database row/page per video; `NOTION_PARENT_PAGE_ID` remains a fallback.
- Feishu creates a document under `FEISHU_VIDEO_NOTES_FOLDER_TOKEN` when configured, falling back to `FEISHU_PARENT_FOLDER_TOKEN`.
- Feishu creates a Bitable record when `FEISHU_BITABLE_APP_TOKEN` and `FEISHU_BITABLE_TABLE_ID` are configured.
- Feishu converts generated notes into structured document blocks instead of raw Markdown.

Future transcription provider layer targets:

- Local video files:
  - `.mp4`
  - `.mov`
  - `.mkv`
- ASR providers:
  - Volcengine
  - Tencent ASR
  - Alibaba ASR
  - Deepgram
  - AWS Transcribe

Doubao Speech ASR is the first implemented provider:

```text
Speech Recognition - Big Model Recording File Recognition
```

Doubao Speech ASR requires an audio URL that the service can access. Local files can be uploaded temporarily to a private Volcengine TOS bucket, then passed to ASR by presigned GET URL:

```text
local audio file or YouTube audio fallback
    ↓
upload to private TOS bucket
    ↓
generate 1-hour presigned GET URL
    ↓
submit URL to Doubao Speech ASR
    ↓
poll ASR result
    ↓
delete uploaded TOS object
```

Configuration placeholders:

```bash
TRANSCRIPTION_PROVIDER=doubao

# Doubao Speech ASR
DOUBAO_ASR_APP_ID=2614672586
DOUBAO_ASR_ACCESS_TOKEN=
DOUBAO_ASR_RESOURCE_ID=volc.seedasr.auc
DOUBAO_ASR_SUBMIT_URL=https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit
DOUBAO_ASR_QUERY_URL=https://openspeech.bytedance.com/api/v3/auc/bigmodel/query
DOUBAO_ASR_LANGUAGE=zh-CN
DOUBAO_ASR_AUDIO_FORMAT=mp3
DOUBAO_ASR_ENABLE_ITN=true
DOUBAO_ASR_ENABLE_PUNC=true
DOUBAO_ASR_ENABLE_DDC=true
DOUBAO_ASR_SHOW_UTTERANCES=true

# Volcengine TOS
VOLCENGINE_ACCESS_KEY_ID=
VOLCENGINE_SECRET_ACCESS_KEY=
TOS_BUCKET=nika-mnemo
TOS_REGION=cn-beijing
TOS_ENDPOINT=tos-cn-beijing.volces.com
```

TOS uses IAM AK/SK. Doubao Speech ASR does not use IAM AK/SK; it uses old-console AppId and Access Token.

Do not use `open.volcengineapi.com`, `Action=SubmitRecognitionTask`, `Version=2023-08-01`, HMAC-SHA256 signing, or IAM AK/SK for this Doubao Speech recording-file recognition API.

After filling `.env`, an explicit public audio URL can be tested with:

```bash
python -c 'from app.utils import load_env_file; from app.transcription import transcribe_audio_url; load_env_file(); print(transcribe_audio_url("<public_audio_url>"))'
```

Local audio files can use the TOS-backed ASR path:

```bash
python -c 'from app.utils import load_env_file; from app.transcription import transcribe_audio_file_via_tos; load_env_file(); print(transcribe_audio_file_via_tos("/path/to/audio.mp3"))'
```

The TOS bucket must remain private. Uploaded audio is temporary transport storage only and should be deleted after ASR finishes. A delete failure is reported as a warning and does not discard the returned transcript.

For YouTube URLs, the application first tries existing subtitles. If no supported English or Chinese subtitles are available, it downloads temporary audio and falls back to Doubao Speech ASR. Telegram uses the same processing path.

Notion publishing is optional. If Notion environment variables are missing or the API fails, local output remains successful.

Obsidian publishing is optional. If `OBSIDIAN_VAULT_PATH` is missing, the adapter is disabled.

Feishu publishing is optional. If Feishu environment variables are missing or the API fails, local output remains successful.

Feishu should not receive raw Markdown as the final document representation. The Feishu adapter should convert generated notes into structured Feishu document blocks:

- Heading 1
- Heading 2
- Heading 3
- Paragraph
- Bullet List
- Numbered List

Telegram input is optional. It accepts YouTube URLs only from explicitly allowed user IDs.

Telegram processing uses a single FIFO in-memory queue. If multiple URLs are sent while one video is processing, each URL is queued and processed in arrival order.

Ollama Configuration:

```bash
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://100.111.104.41:11434
OLLAMA_MODEL=qwen3:8b
```

The Ollama API is expected to be reachable through the user's private network.

Do not expose the Ollama API publicly.

Qwen Configuration:

```bash
LLM_PROVIDER=qwen
LLM_MODEL=qwen-plus
QWEN_API_KEY=<your_qwen_api_key>
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Other supported LLM providers:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=<your_openai_api_key>

LLM_PROVIDER=claude
CLAUDE_API_KEY=<your_claude_api_key>

LLM_PROVIDER=gemini
GEMINI_API_KEY=<your_gemini_api_key>

LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=<your_deepseek_api_key>
```

If the selected LLM fails, the app uses rule-based fallback and still writes local output files.

---

# Documentation

Project documentation is located in:

```text
docs/
```

Files:

```text
docs/constraints.md
docs/prd.md
docs/todo.md
docs/folder-structure.md
docs/acceptance-criteria.md
docs/implementation-plan.md
```

---

# Project Structure

```text
video-note-agent/

├── docs/
├── app/
├── output/
├── tests/

├── main.py

├── requirements.txt

├── .gitignore

└── README.md
```

---

# Development Process

All development should follow:

```text
1. Read constraints.md

2. Read PRD

3. Read TODO list

4. Follow Folder Structure

5. Implement current phase only

6. Validate using Acceptance Criteria
```

---

# Security Principles

The project follows a local-first approach.

The MVP must not:

- Access email accounts
- Access cloud drives
- Read personal documents
- Control browsers
- Execute arbitrary commands

The system should only process:

```text
User-provided video URLs
```

---

# Definition of Done

The MVP is complete when:

```bash
python main.py <youtube_url>
```

successfully generates:

```text
output/
└── <safe-video-folder-name>/
    ├── metadata.json
    ├── 01_raw_transcript.txt
    ├── 02_formatted_transcript.md
    ├── 03_cleaned_content.md
    └── 04_notes_outline.md
```

and all requirements in:

```text
docs/acceptance-criteria.md
```

are satisfied.

---

# Future Roadmap

```text
Phase 1 - YouTube + Subtitle
Phase 2 - Local Video Support + Whisper
Phase 3 - Remote Private Ollama Notes
Phase 4 - Output Adapter Architecture
Phase 5 - Notion Adapter
Phase 6 - Additional Output Adapters
Phase 7 - Telegram
Phase 8 - Docker
Phase 9 - Windows Deployment
Phase 10 - Secure Remote Access
Future - Knowledge System
Future - Personal Assistant Ecosystem
```
