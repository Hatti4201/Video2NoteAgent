# Folder Structure

## Purpose

This document defines the expected folder structure, directory responsibilities, architecture rules, and maximum complexity rule for the Video Note Agent MVP.

## Project Structure

The MVP should use a simple and easy-to-understand structure.

Do not over-engineer.

```text
video-note-agent/
├── docs/
│   ├── constraints.md
│   ├── prd.md
│   ├── todo.md
│   ├── folder-structure.md
│   └── acceptance-criteria.md
│
├── app/
│   ├── adapters/
│   │   ├── base.py
│   │   ├── feishu.py
│   │   ├── markdown.py
│   │   ├── notion.py
│   │   └── obsidian.py
│   ├── input_adapters/
│   │   └── telegram.py
│   ├── storage/
│   │   ├── __init__.py
│   │   └── tos.py
│   ├── downloader.py
│   ├── local_video.py
│   ├── llm.py
│   ├── transcription.py
│   ├── transcript.py
│   ├── notes.py
│   ├── utils.py
│   └── __init__.py
│
├── output/
│   └── <safe-video-folder-name>/
│       ├── metadata.json
│       ├── 01_raw_transcript.txt
│       ├── 02_formatted_transcript.md
│       ├── 03_cleaned_content.md
│       └── 04_notes_outline.md
│
├── tests/
│   ├── test_downloader.py
│   ├── test_local_video.py
│   ├── test_llm.py
│   ├── test_transcript.py
│   └── test_notes.py
│
├── main.py
│
├── requirements.txt
│
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
│
├── .gitignore
│
└── README.md
```

## Directory Responsibilities

### docs/

Contains project documentation.

No application code.

### app/

Contains all business logic.

Phase 4 introduces an output adapter boundary.

Adapters publish already-generated knowledge assets and must not generate transcripts or notes.

#### adapters/

Responsibilities:

- Publish generated local assets to optional destinations
- Keep external destinations replaceable
- Isolate adapter failures from core processing

Planned adapters:

- `markdown.py`
- `notion.py`
- `obsidian.py`
- `feishu.py`
- `google_docs.py`

#### input_adapters/

Responsibilities:

- Accept optional external inputs
- Validate and authorize input sources
- Forward accepted requests to the core processing pipeline

Current adapters:

- `telegram.py`

#### storage/

Responsibilities:

- Store temporary transport files for external APIs
- Generate short-lived access URLs when needed
- Clean up temporary objects after processing

Current storage modules:

- `tos.py`

TOS audio storage must remain temporary and private.

#### downloader.py

Responsibilities:

- Validate YouTube URL
- Download subtitles
- Get video metadata

#### local_video.py

Responsibilities:

- Validate local video paths
- Support MP4, MOV, and MKV inputs
- Transcribe local video audio with Whisper or faster-whisper

#### transcription.py

Responsibilities:

- Submit transcript generation jobs to ASR providers
- Poll ASR results
- Return transcript text to the common transcript layer
- Keep ASR provider errors readable

#### llm.py

Responsibilities:

- Read selected LLM provider and model configuration from environment variables
- Support Ollama, OpenAI, Claude, Gemini, DeepSeek, and Qwen providers
- Generate cleaned content and structured notes
- Return readable errors when the selected LLM is unavailable
- Preserve rule-based fallback behavior outside the LLM module

#### transcript.py

Responsibilities:

- Parse subtitle files
- Remove timestamps
- Generate transcript text

#### notes.py

Responsibilities:

- Generate markdown notes
- Create summary section
- Create key points section
- Create action items section

#### utils.py

Responsibilities:

- Shared helper functions

Keep this file small.

### output/

Contains generated files.

Each processed video gets a dedicated folder named from the video date and title.

Generated at runtime.

Do not commit generated files.

### tests/

Contains unit tests.

One test file per module.

### main.py

Application entry point.

Expected usage:

```bash
python main.py <youtube_url>
```

### requirements.txt

Contains project dependencies.

Keep dependencies minimal.

### Dockerfile

Builds a Python runtime image for CLI and Telegram bot usage.

### docker-compose.yml

Defines CLI and Telegram bot services.

Current one-shot Docker usage:

```bash
docker compose run --rm video-note-agent "<youtube_url>"
```

Future local video processing through Docker will require an input volume mount, for example:

```text
./input:/app/input
./output:/app/output
```

### .dockerignore

Excludes generated output, local environments, tests, and secrets from Docker build context.

## Architecture Rules

The MVP must remain:

- Simple
- Local-first
- Single-user
- CLI-based

Avoid:

- Databases
- Web frameworks
- Authentication
- Background workers
- Message queues
- Cloud services

## Maximum Complexity Rule

If a feature can be implemented in:

```text
1 file
```

do not create:

```text
3 files
```

If a function can be:

```text
20 lines
```

do not create:

```text
5 classes
```

Keep the MVP small.
