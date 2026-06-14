# Acceptance Criteria

## Purpose

This document defines acceptance criteria for the local-first but cloud-ready Video Note Agent roadmap.

---

# Phase 1 - YouTube Subtitle MVP

Status:

- [x] Completed

## AC-1 YouTube URL Input

The application accepts a YouTube URL from the command line.

Verification:

```bash
python main.py "<youtube_url>"
```

Expected:

- Valid YouTube URLs begin processing.
- Invalid URLs return a readable error.

## AC-2 Subtitle Download

The application downloads existing subtitles.

Expected:

- English and Chinese subtitles are supported.
- Video files are not downloaded for YouTube subtitle processing.
- Missing subtitles return a readable error.

## AC-3 Transcript Generation

The application generates transcript text from subtitles.

Expected:

- Transcript text is readable.
- Subtitle metadata and timestamps are removed where appropriate.
- Empty transcript content returns a readable error.

## AC-4 Basic Notes

The application generates basic notes from transcript text.

Expected:

- Notes are readable.
- Rule-based fallback exists when AI processing is unavailable.

## AC-5 Local Output

The application writes output locally.

Expected:

- Local output exists after successful processing.
- Local output remains available even if external publishing fails.

---

# Phase 2 - Per-Video Output Workspace

Status:

- [x] Completed in current implementation

## AC-6 Dedicated Workspace

Each processed video creates one dedicated output folder.

Expected:

```text
output/<safe-video-folder-name>/
```

## AC-7 Required Files

Each workspace contains:

```text
metadata.json
01_raw_transcript.txt
02_formatted_transcript.md
03_cleaned_content.md
04_notes_outline.md
```

Expected:

- Files are created successfully.
- Files contain valid content.
- Existing video outputs are not overwritten.

## AC-8 Metadata

`metadata.json` contains:

- title
- url
- source
- author
- duration
- language
- tags
- status
- created_at
- summary
- processing_method

Expected:

- Unavailable scalar values are empty strings.
- Unavailable list values are empty arrays.
- `status` defaults to `Processed`.
- Output adapters can derive platform-specific output from `metadata.json` and the four canonical note assets.

---

# Phase 3 - AI Note Processing

Status:

- [x] Completed in current implementation

## AC-9 Derived Artifacts

Transcript text is processed into:

- formatted transcript
- cleaned content
- notes outline

Expected:

- `02_formatted_transcript.md` is readable.
- `03_cleaned_content.md` contains edited transcript-style content.
- `04_notes_outline.md` contains structured knowledge output.

## AC-10 Local Source Of Truth

Local files remain the source of truth.

Expected:

- AI provider failure does not delete or prevent local output.
- Rule-based fallback output is written when AI processing fails.

---

# Phase 4 - Transcription Provider Layer

Status:

- [ ] Planned

## AC-11 Future Local Video Support

Future local video inputs:

- `.mp4`
- `.mov`
- `.mkv`

Expected when implemented:

- Local video input produces transcript text.
- Transcript text enters the same downstream pipeline as YouTube subtitles.

## AC-12 ASR Providers

ASR provider targets:

- Doubao Speech ASR: explicit audio URL and TOS-backed local audio helper implemented
- Tencent ASR
- Alibaba ASR
- Deepgram
- AWS Transcribe

Expected when implemented:

- Each provider returns transcript text through a shared interface.
- Provider failures return readable errors.
- Provider credentials are explicit environment configuration.

Doubao Speech TOS-backed ASR expected behavior:

- Local audio is uploaded to a private TOS bucket.
- A 1-hour presigned GET URL is generated for ASR.
- The uploaded TOS object is deleted after ASR finishes.
- TOS delete failures warn but do not discard a successful transcript.
- TOS uses IAM AK/SK.
- Doubao Speech ASR uses old-console AppId and Access Token.
- Doubao Speech ASR does not use IAM AK/SK, `open.volcengineapi.com`, `Action=SubmitRecognitionTask`, `Version=2023-08-01`, or HMAC-SHA256 signing.

Local video extraction into ASR is not implemented yet.

---

# Phase 5 - Output Adapter Layer

Status:

- [ ] Planned architecture
- [x] Some adapters exist in current implementation

## AC-13 Optional Publishing

Publishing destinations are optional.

Expected:

- Local files are generated before publishing.
- Adapter failures do not fail local processing.
- Adapter results are reported to CLI or Telegram when available.
- Notion creates a database page when `NOTION_DATABASE_ID` is configured.
- Notion falls back to parent-page publishing when only `NOTION_PARENT_PAGE_ID` is configured.
- Feishu creates a document under the configured folder.
- Feishu creates a Bitable record when Bitable configuration is present.

## AC-14 Supported Destination Targets

Planned destinations:

- Local Markdown
- Feishu Docs
- Notion
- Google Docs
- Obsidian

## AC-15 Feishu Structured Blocks

Feishu should not receive raw Markdown.

Expected when implemented:

- Generated notes are converted into Feishu document blocks:
  - Heading 1
  - Heading 2
  - Heading 3
  - Paragraph
  - Bullet List
  - Numbered List

---

# Phase 6 - Cloud Deployment

Status:

- [ ] Planned

## AC-16 Cloud-Ready Execution

Future cloud deployment supports:

- task orchestration in cloud
- ASR by API
- publishing by adapters
- optional home workstation usage

Expected when implemented:

- Cloud deployment does not replace local-first operation.
- Local files remain the source of truth.
- Secrets are not committed or baked into images.

No cloud deployment is implemented in this documentation update.
