# Whop Course Downloader

## Começar no Windows — Content Autopilot

Na pasta deste repositório, execute no PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\download.ps1
```

O Chromium abrirá no seu computador. Entre na sua conta Whop no próprio
navegador. A sessão fica em `.whop_browser_data`, somente no seu computador.
Não envie essa pasta nem URLs assinadas para o GitHub.

Caso a URL antiga não abra o curso, abra uma aula em sua conta e use sua URL:

```powershell
powershell -ExecutionPolicy Bypass -File .\download.ps1 -CourseUrl "URL_DA_AULA"
```

Para atualizar URLs expiradas:

```powershell
powershell -ExecutionPolicy Bypass -File .\download.ps1 -Refresh
```

Vídeos: `content-copilot/downloads/videos/`.
Manifesto: `content-copilot/downloads/manifest.json`.
Para transcrever no Gemini, envie os vídeos pela interface do Gemini. Nenhuma
integração de transcrição foi instalada neste repo.

**Limitação de validação:** download de um MP4 de teste, checkpoints e retomada
foram verificados. A descoberta de todas as aulas e módulos deste curso ainda
precisa ser validada na sua sessão. Módulos recolhidos/links não renderizados
podem não ser descobertos; confira o total antes de considerar a exportação
completa. Módulos não identificados ficam `null`.

**Dependências:** Python 3.9+, Git e FFmpeg. Se necessário:
`winget install --id Gyan.FFmpeg -e` e abra um novo terminal.


A Python script to download video courses from Whop using browser automation. Supports both automatic and manual navigation modes depending on the course structure.

## Features

- 🎯 **Smart Navigation Detection** - Automatically detects if keyboard navigation works
- 🤖 **Automatic Mode** - Uses ArrowRight key for courses that support it
- 🖱️ **Manual Mode** - Captures videos as you click through lessons
- 🔗 **Iframe Support** - Handles courses.apps.whop.com iframe architecture
- 📹 **Mux Video Support** - Downloads HLS streams with authentication
- ⏸️ **Resume Downloads** - Skips already downloaded videos
- 💾 **URL Caching** - Saves extracted URLs to avoid re-extraction
- 🔄 **Smart Retries** - Automatically tries different video formats
- 🧪 **Test Mode** - Verify extraction works before downloading

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/whop-downloader.git
cd whop-downloader

# Install Playwright browser (first time only)
playwright install chromium
```

## Usage

### Download a Course

```bash
# Basic usage
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download <course_url>

# Download to specific directory
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download <course_url> "/path/to/save"

# Example with full URL
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download https://courses.apps.whop.com/customer-v2/experience/exp_xxx/

# Example with Whop course page
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download https://whop.com/your-course-name/

# Retry failed downloads (uses cached URLs)
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download https://whop.com/your-course-name/

# Force re-extraction of URLs
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download https://whop.com/your-course-name/ --force
```

### Test Mode

Test extraction without downloading:

```bash
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader test <course_url>
```

## How it Works

1. **Opens browser with saved session** - Login persists between runs
2. **Navigates to course** - Uses redirect URL for iframe-based courses
3. **Keyboard navigation** - Uses ArrowRight key to go through all lessons
4. **Captures video URLs** - Monitors network traffic for Mux streaming URLs
5. **Downloads with yt-dlp** - High quality video downloads with resume support

## Commands

### `download` - Download entire course
```bash
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader download <course_url> [target_directory] [--force]
```
- Uses cached video URLs if available (skip extraction)
- Downloads videos to `target_directory/downloads/videos/`
- Skips already downloaded files
- Saves progress to `video_urls.json`
- Use `--force` to re-extract URLs even if cache exists

### `test` - Test extraction only
```bash
uvx --from git+https://github.com/mlapping/whop-downloader.git whop-downloader test <course_url> [--force]
```
- Extracts all video URLs without downloading
- Useful for verifying the script works with your course
- Saves URLs to `downloads/video_urls.json` (same as download command)

## Output Structure

```
target_directory/
├── logs/
│   └── whop_downloader.log
└── downloads/
    ├── video_urls.json
    └── videos/
        ├── 001_Lesson_01.mp4
        ├── 002_Lesson_02.mp4
        └── ...
```

Browser session data is saved in `.whop_browser_data/` in your current directory.

## Troubleshooting

- **Login required**: The browser will open for manual login on first run
- **Videos not found**: Make sure the course page loads and shows the first video
- **Download fails**: Check that yt-dlp is installed and up to date
- **Session expired**: Delete `.whop_browser_data` folder and log in again

## Navigation Modes

### Automatic Mode
Some courses support keyboard navigation. The script will automatically detect this and use ArrowRight to navigate through lessons:

```
✓ Keyboard navigation (ArrowRight) detected
Using keyboard navigation (ArrowRight key)
Navigation 1: Found 1 videos
Navigation 2: Found 2 videos
...
```

### Manual Mode
For courses that don't support keyboard navigation, the script will prompt you to navigate manually:

```
============================================================
MANUAL NAVIGATION MODE
============================================================
Automatic navigation is not available for this course.
Please manually click through all lessons in the browser.
The script will automatically capture video URLs.
When done, close the browser window.
============================================================
```

## Requirements

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (for uvx command)
- Dependencies (automatically installed by uvx):
  - playwright
  - yt-dlp

## Troubleshooting

### "Command not found: uvx"
Install uv first:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Playwright browser not installed"
```bash
playwright install chromium
```

### "Login required"
The browser will open for manual login on first run. Your session is saved for future runs.

### "No videos found"
- Make sure you're logged in
- Check that the course page loads properly
- For manual mode, ensure you click through all lessons

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is for educational purposes only. Users are responsible for complying with Whop's terms of service and respecting content creators' rights.

## Disclaimer

This tool is not affiliated with Whop. Use at your own risk and ensure you have the right to download content from courses you've purchased.

## Work setup

Install with `python -m venv .venv`, `.venv/bin/python -m pip install -e .`,
and `.venv/bin/python -m playwright install chromium`.

This fork records lesson URLs, detected titles, optional module names, relative
filenames and per-video download status in `downloads/manifest.json`. Checkpoints
are written atomically after each capture/download. Authentication files and
course assets must remain outside git.

Lesson-link navigation replaces the old ArrowRight/manual workflow. Modules stay
null when the page does not expose them. Pages without discoverable lesson links use enabled Next/Próximo buttons.
Always compare captured counts with the course sidebar before treating it as a
full export. Extraction against the Content Autopilot account still requires
an authenticated session and live validation. URLs can expire: use `--force` to
refresh the cache. No transcription or Gemini API integration is included.

Example after authentication:

```bash
.venv/bin/whop-downloader download "COURSE_URL" "./content-copilot"
```


### Capture fix for Group Call Recordings

When the course sidebar exposes no anchor links, the scanner starts the current
player and follows visible enabled Next/Próximo buttons. Stream responses are
captured in iframes too. Dependencies no longer pin the 2024 Playwright release.
This flow is tested against a local two-lesson browser fixture; the live course
still needs validation. Check that all 37 expected recordings are listed.

On WSL, update and run:

```bash
git pull
python -m pip install --upgrade playwright yt-dlp
python -m playwright install chromium
python whop_downloader.py download "https://whop.com/content-autopilot/exp_AjSt1mt0jHqrTq/app/courses/cors_tjtaBLZBFY80r/lessons/lesn_Cx3NXX0fMsWKf/" ./group-call-recordings --force
```


### Slow course pages

The scanner waits for visible media or a Play button, then waits for a captured
stream before advancing. Each wait defaults to 180 seconds, with progress logs.
For slower pages on WSL, use:

```bash
WHOP_LOAD_TIMEOUT=300 python whop_downloader.py download "COURSE_URL" ./group-call-recordings --force
```

This is a maximum per wait, not a fixed delay for every lesson. If no stream
appears, the scan stops as incomplete rather than skipping to the next lesson.


### One stream per lesson

Capture is keyed by the lesson URL at request time. HLS master, audio and quality
playlists are grouped into one lesson entry, preferring the master playlist.
Player-internal error headings are excluded from lesson titles. This assumes one
video per lesson, as in Group Call Recordings. After upgrading, use `--force` to
rebuild earlier URL caches that may contain rendition duplicates.
