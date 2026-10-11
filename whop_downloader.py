#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "playwright",
#   "yt-dlp",
# ]
# ///
"""
Whop Course Downloader - uvx script
Downloads courses from Whop using Playwright iframe navigation

Usage:
    uvx whop_downloader.py download <course_url> [target_directory]
    uvx whop_downloader.py test <course_url>
    
Commands:
    download - Extract and download all videos from the course
    test     - Extract video URLs only (no downloading)
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import re
from urllib.parse import urlsplit
from pathlib import Path
from playwright.async_api import async_playwright


class WhopDownloader:
    def __init__(self, course_url, target_dir=None):
        self.course_url = course_url
        self.target_dir = Path(target_dir) if target_dir else Path.cwd()
        self.setup_logging()
        self.setup_directories()
        
    def setup_logging(self):
        """Setup logging configuration"""
        self.log_dir = self.target_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_dir / "whop_downloader.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_directories(self):
        """Create necessary directories"""
        self.base_dir = self.target_dir
        self.downloads_dir = self.base_dir / "downloads"
        self.videos_dir = self.downloads_dir / "videos"
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        
        # Browser data directory in current working directory
        self.browser_data_dir = Path.cwd() / ".whop_browser_data"
        self.browser_data_dir.mkdir(exist_ok=True)

    @staticmethod
    def safe_name(value):
        name = re.sub(r'[^\w -]', '', str(value)).strip().replace(' ', '_')[:120]
        return name if name not in ('', '.', '..') else 'Uncategorized'

    def video_path(self, info, index):
        folder = self.videos_dir
        if info.get('module'):
            folder = folder / self.safe_name(info['module'])
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{index:03d}_{self.safe_name(info['title'])}.mp4"

    def save_progress(self, videos):
        for i, info in enumerate(videos, 1):
            path = self.video_path(info, i)
            info['filename'] = str(path.relative_to(self.target_dir))
        payloads = {
            self.downloads_dir / 'video_urls.json': videos,
            self.downloads_dir / 'manifest.json': {
                'course_url': self.course_url, 'lessons': videos,
                'note': 'Module is null when not exposed by the page; verify scan completeness.'
            },
        }
        for path, payload in payloads.items():
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
            temp.chmod(0o600)
            temp.replace(path)

    async def extract_video_urls(self, force_reextract=False):
        """Extract video URLs using iframe navigation approach"""
        urls_file = self.downloads_dir / "video_urls.json"
        
        # Check if we already have extracted URLs
        if urls_file.exists() and not force_reextract:
            self.logger.info("Found existing video URLs file, loading...")
            try:
                with open(urls_file, 'r') as f:
                    video_data = json.load(f)
                if video_data:
                    self.logger.info(f"Loaded {len(video_data)} videos from cache")
                    return video_data
            except Exception as e:
                self.logger.warning(f"Could not load cached URLs: {e}")
                self.logger.info("Will re-extract video URLs...")
        
        self.logger.info("Starting URL extraction with iframe navigation...")
        
        async with async_playwright() as p:
            # Launch browser with minimal flags for iframe access
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.browser_data_dir),
                headless=os.environ.get('WHOP_HEADLESS') == '1',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = browser.pages[0] if browser.pages else await browser.new_page()
            
            # Track all video URLs found
            all_video_urls = {}
            video_data = []
            
            # Capture only successful top-level Mux manifests, not rendition playlists.
            active_lesson = {}

            async def handle_response(response):
                parsed = urlsplit(response.url)
                if (response.status == 200 and parsed.path.endswith('.m3u8')
                        and (parsed.hostname != 'stream.mux.com' or re.fullmatch(r'/[^/]+\.m3u8', parsed.path))):
                    video_id = parsed.hostname + parsed.path.rsplit('.m3u8', 1)[0]
                    if video_id in all_video_urls:
                        for info in video_data:
                            if info['video_id'] == video_id and active_lesson:
                                info.update(active_lesson)
                                info.update(url=response.url, video_url=response.url)
                        self.save_progress(video_data)
                        return
                    if video_id not in all_video_urls:
                        all_video_urls[video_id] = response.url
                        info = dict(active_lesson)
                        info.update(index=len(video_data) + 1, video_id=video_id,
                                    url=response.url, video_url=response.url,
                                    downloaded=False)
                        info.setdefault('lesson_url', page.url)
                        if not info.get('title'):
                            headings = response.request.frame.locator('h1, h2, h3')
                            info['title'] = (await headings.last.inner_text()).strip() if await headings.count() else 'Untitled_' + video_id[:12]
                        info.setdefault('module', None)
                        video_data.append(info)
                        self.save_progress(video_data)
                        self.logger.info('Captured video %s', len(video_data))

            pending_responses = set()
            def queue_response(response):
                task = asyncio.create_task(handle_response(response))
                pending_responses.add(task)
                def response_done(done):
                    pending_responses.discard(done)
                    if not done.cancelled() and done.exception():
                        self.logger.warning('Could not read metadata for a captured response (%s).', type(done.exception()).__name__)
                task.add_done_callback(response_done)
            page.on('response', queue_response)

            async def start_and_capture():
                for frame in page.frames:
                    # Start real media, including players inside iframes/shadow roots.
                    for selector in ('video', 'mux-player'):
                        media = frame.locator(selector)
                        for player in await media.all():
                            try:
                                await player.evaluate('el => { el.muted = true; return el.play().catch(() => {}); }')
                            except Exception:
                                pass
                    play = frame.get_by_role('button', name=re.compile(r'play|reproduzir|assistir', re.I))
                    for button in await play.all():
                        if await button.is_visible():
                            try:
                                await button.click(timeout=1500)
                            except Exception:
                                pass
                            break
                await page.wait_for_timeout(8000)
                if pending_responses:
                    await asyncio.gather(*list(pending_responses), return_exceptions=True)

            async def lesson_metadata():
                for frame in reversed(page.frames):
                    headings = frame.locator('h1, h2, h3')
                    texts = [t.strip() for t in await headings.all_text_contents() if t.strip()]
                    if texts:
                        return {'title': texts[-1], 'lesson_url': page.url, 'module': None}
                return {'title': await page.title(), 'lesson_url': page.url, 'module': None}


            # Navigate to course
            await page.goto(self.course_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)

            login_button = page.get_by_role('button', name=re.compile(r'^(Entrar|Log in|Sign in)$', re.I))
            if await login_button.count() and await login_button.first.is_visible():
                if os.environ.get('WHOP_HEADLESS') == '1':
                    self.logger.error('Authentication required; open the visible browser first.')
                    await browser.close()
                    return []
                self.logger.info('Entre na Whop no navegador aberto (até 5 minutos).')
                try:
                    await login_button.first.click()
                    await page.wait_for_function("() => !Array.from(document.querySelectorAll('button')).some(b => /^(Entrar|Log in|Sign in)$/i.test(b.innerText.trim()))", timeout=300000)
                    # Dismissing a login modal is not proof of login. Reload the requested
                    # lesson and let the course content determine whether access exists.
                    await page.goto(self.course_url, wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_timeout(5000)
                    if await login_button.count() and await login_button.first.is_visible():
                        self.logger.error('A sessão ainda não está autenticada. Execute novamente após entrar.')
                        await browser.close()
                        return []
                except Exception:
                    self.logger.error('Não foi possível confirmar login no navegador.')
                    await browser.close()
                    return []

            # Check if we need to navigate to iframe content
            current_url = page.url
            self.logger.info(f"Initial URL: {current_url}")
            
            # Look for course iframe
            iframe_url = await page.evaluate("""
                () => {
                    const iframe = document.querySelector('iframe[src*="courses.apps.whop.com"]');
                    if (iframe) {
                        return iframe.src;
                    }
                    // Also check for redirect URLs
                    const redirectIframe = document.querySelector('iframe[src*="/core/app/launch/?redirect="]');
                    if (redirectIframe) {
                        return redirectIframe.src;
                    }
                    return null;
                }
            """)
            
            if iframe_url:
                self.logger.info(f"Found course iframe: {iframe_url[:100]}...")
                
                # If it's a relative URL, make it absolute
                if iframe_url.startswith('/'):
                    iframe_url = f"https://whop.com{iframe_url}"
                
                # Navigate to the iframe URL
                self.logger.info("Navigating to iframe content...")
                await page.goto(iframe_url, wait_until='networkidle')
                await page.wait_for_timeout(3000)
                
                self.logger.info(f"Now at: {page.url}")
            
            # Wait for page to stabilize
            await page.wait_for_timeout(5000)
            
            # Check for login requirement
            current_url = page.url
            if 'login' in current_url or 'signin' in current_url:
                if os.environ.get('WHOP_HEADLESS') == '1':
                    self.logger.error('Authentication required; no authenticated session available.')
                    await browser.close()
                    return []
                self.logger.info("Login required. Please log in manually in the browser window.")
                self.logger.info("Waiting for login completion...")
                
                # Wait for navigation away from login page
                max_wait = 300  # 5 minutes
                elapsed = 0
                while elapsed < max_wait:
                    await page.wait_for_timeout(2000)
                    elapsed += 2
                    
                    current_url = page.url
                    if 'login' not in current_url and 'signin' not in current_url:
                        self.logger.info("Login detected, proceeding...")
                        break
                    
                    if elapsed % 30 == 0:
                        self.logger.info(f"Still waiting for login... ({elapsed}s / {max_wait}s)")
                
                if elapsed >= max_wait:
                    self.logger.error("Login timeout. Please run again after logging in.")
                    await browser.close()
                    return []
            
            # Wait for first video to load
            self.logger.info("Waiting for course content to load...")
            await page.wait_for_timeout(5000)
            
            # Prefer explicit lesson links; keyboard arrows may just seek the video.
            lessons = []
            for frame in page.frames:
                links = await frame.locator('a[href*="/lessons/"], a[href*="lesn_"]').evaluate_all(
                    "els => els.map(e => ({url: e.href, title: e.innerText.trim()}))")
                for link in links:
                    if link['url'] and not any(x['url'] == link['url'] for x in lessons):
                        lessons.append(link)
            if not lessons:
                self.logger.info('No lesson links: using visible Next/Próximo buttons.')
                visited = set()
                for step in range(500):
                    active_lesson.clear()
                    active_lesson.update(await lesson_metadata())
                    before = (page.url, active_lesson['title'])
                    if before in visited:
                        break
                    visited.add(before)
                    self.logger.info('Scanning lesson %s: %s', step + 1, active_lesson['title'])
                    await start_and_capture()
                    next_button = None
                    for frame in page.frames:
                        candidates = frame.get_by_role('button', name=re.compile(r'^(Próximo|Next)(\s|»|$)', re.I))
                        for candidate in await candidates.all():
                            if await candidate.is_visible() and await candidate.is_enabled():
                                next_button = candidate
                                break
                        if next_button is not None:
                            break
                    if next_button is None:
                        break
                    await next_button.click()
                    for _ in range(15):
                        await page.wait_for_timeout(1000)
                        after = await lesson_metadata()
                        if (page.url, after['title']) != before:
                            break
                    else:
                        self.logger.warning('Next did not change the lesson. Stopping to avoid repeats.')
                        break
            else:
                for lesson in lessons:
                    active_lesson.clear()
                    active_lesson.update(title=lesson['title'] or 'Untitled',
                                         lesson_url=lesson['url'], module=None)
                    await page.goto(lesson['url'], wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_timeout(3000)
                    await start_and_capture()
            if pending_responses:
                await asyncio.gather(*list(pending_responses), return_exceptions=True)
            self.save_progress(video_data)

            try:
                await browser.close()
            except:
                pass  # Browser might already be closed
            
            self.logger.info(f"\nExtraction complete! Found {len(video_data)} videos")
            return video_data

    def download_video(self, video_info, index, total):
        """Download a single video using yt-dlp"""
        title = video_info['title']
        url = video_info['url']
        
        output_path = self.video_path(video_info, index)

        # Skip if already downloaded
        if output_path.exists() and output_path.stat().st_size > 0:
            self.logger.info(f"[{index}/{total}] Already downloaded: {title}")
            return True
        
        self.logger.info(f"[{index}/{total}] Downloading: {title}")
        
        # Try different format options in order of preference
        format_options = [
            'best[ext=mp4]/best',  # Original format
            'best',                # Any best format
            'bestvideo+bestaudio/best',  # Best video+audio
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # MP4 preferred
            'bestvideo*+bestaudio/best',  # Any video+audio format
        ]
        
        for format_option in format_options:
            # Build command with current format option
            cmd = [
                sys.executable, '-m', 'yt_dlp',
                '--no-warnings',
                '--quiet',
                '--progress',
                '--referer', 'https://whop.com/',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '-f', format_option,
                '-o', str(output_path),
                url
            ]
            
            # For m3u8 streams, add appropriate options
            if '.m3u8' in url:
                cmd.extend(['--concurrent-fragments', '4'])
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info(f"[{index}/{total}] ✓ Downloaded: {title}")
                    return True
                elif "Requested format is not available" in result.stderr:
                    # Try next format
                    if format_option != format_options[-1]:
                        self.logger.debug(f"Format '{format_option}' not available, trying next...")
                        continue
                else:
                    # Other error, log and continue
                    self.logger.error(f"[{index}/{total}] ✗ Failed with format '{format_option}': {title}")
                    self.logger.error(f"  Error: {result.stderr.strip()}")
                    continue
            except Exception as e:
                self.logger.error(f"[{index}/{total}] ✗ Exception: {title} - {e}")
                continue
        
        # If all formats failed, try one more time with the most permissive settings
        self.logger.info(f"[{index}/{total}] Attempting fallback download...")
        fallback_cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--no-warnings',
            '--quiet',
            '--progress',
            '--referer', 'https://whop.com/',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '--merge-output-format', 'mp4',
            '-o', str(output_path),
            url
        ]
        
        try:
            result = subprocess.run(fallback_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"[{index}/{total}] ✓ Downloaded (fallback): {title}")
                return True
        except:
            pass
        
        self.logger.error(f"[{index}/{total}] ✗ Failed all download attempts: {title}")
        return False

    async def run_download(self, force_reextract=False):
        """Extract and download all videos"""
        self.logger.info("=== Whop Course Downloader ===")
        self.logger.info(f"Course URL: {self.course_url}")
        self.logger.info(f"Target directory: {self.target_dir}")
        
        # Extract video URLs
        video_data = await self.extract_video_urls(force_reextract)
        
        if not video_data:
            self.logger.error("No videos found. Exiting.")
            return False
        
        # Check which videos already exist
        already_downloaded = []
        to_download = []
        
        for i, video_info in enumerate(video_data, 1):
            title = video_info['title']
            output_path = self.video_path(video_info, i)

            if output_path.exists() and output_path.stat().st_size > 0:
                video_info['downloaded'] = True
                already_downloaded.append(video_info)
            else:
                to_download.append((i, video_info))
        
        self.save_progress(video_data)

        # Show summary
        self.logger.info(f"\n=== Download Summary ===")
        self.logger.info(f"Total videos: {len(video_data)}")
        self.logger.info(f"Already downloaded: {len(already_downloaded)}")
        self.logger.info(f"To download: {len(to_download)}")
        
        if len(to_download) == 0:
            self.logger.info("\nAll videos already downloaded!")
            return True
        
        # Download videos
        self.logger.info(f"\nStarting download of {len(to_download)} videos...")
        
        failed_downloads = []
        for i, video_info in to_download:
            success = self.download_video(video_info, i, len(video_data))
            video_info['downloaded'] = success
            video_info['status'] = 'downloaded' if success else 'failed'
            self.save_progress(video_data)
            if not success:
                failed_downloads.append(video_info)
            
            # Small delay between downloads
            time.sleep(1)
        
        # Final summary
        self.logger.info("\n=== Final Results ===")
        self.logger.info(f"Total videos: {len(video_data)}")
        self.logger.info(f"Previously downloaded: {len(already_downloaded)}")
        self.logger.info(f"Newly downloaded: {len(to_download) - len(failed_downloads)}")
        self.logger.info(f"Failed: {len(failed_downloads)}")
        
        if failed_downloads:
            self.logger.info("\nFailed downloads:")
            for video in failed_downloads:
                self.logger.info(f"  - {video['title']}")
        
        self.logger.info(f"\nVideos saved to: {self.videos_dir}")
        return len(failed_downloads) == 0

    async def run_test(self, force_reextract=False):
        """Test extraction only (no downloads)"""
        self.logger.info("=== Whop Course Downloader - Test Mode ===")
        self.logger.info(f"Course URL: {self.course_url}")
        self.logger.info("\nExtracting video URLs only (no downloads)...")
        
        # Extract video URLs (uses cache if available)
        video_data = await self.extract_video_urls(force_reextract)
        
        if not video_data:
            self.logger.error("No videos found.")
            return False
        
        # Display results
        self.logger.info(f"\n✓ Extraction complete!")
        self.logger.info(f"Total videos found: {len(video_data)}")
        
        if video_data:
            self.logger.info("\nFirst 5 videos:")
            for video in video_data[:5]:
                self.logger.info(f"  {video['index']}. {video['title']} - ID: {video['video_id']}")
            
            if len(video_data) > 10:
                self.logger.info("\nLast 5 videos:")
                for video in video_data[-5:]:
                    self.logger.info(f"  {video['index']}. {video['title']} - ID: {video['video_id']}")
        
        # Save URLs for inspection
        urls_file = self.downloads_dir / "video_urls.json"
        self.logger.info(f"\nVideo URLs saved to: {urls_file}")
        
        return len(video_data) > 0


def download_command(course_url, target_dir=None, force_reextract=False):
    """Download all videos from a course"""
    downloader = WhopDownloader(course_url, target_dir)
    success = asyncio.run(downloader.run_download(force_reextract))
    return 0 if success else 1


def test_command(course_url, force_reextract=False):
    """Test extraction without downloading"""
    downloader = WhopDownloader(course_url, target_dir=None)  # Use current directory like download
    success = asyncio.run(downloader.run_test(force_reextract))
    return 0 if success else 1


def main():
    """Main entry point for uvx"""
    if len(sys.argv) < 3:
        print("Whop Course Downloader")
        print("\nUsage:")
        print("  uvx whop_downloader.py download <course_url> [target_directory] [--force]")
        print("  uvx whop_downloader.py test <course_url> [--force]")
        print("\nCommands:")
        print("  download - Extract and download all videos from the course")
        print("  test     - Extract video URLs only (no downloading)")
        print("\nOptions:")
        print("  --force  - Force re-extraction of video URLs even if cache exists")
        print("\nExamples:")
        print("  uvx whop_downloader.py download https://whop.com/course-name")
        print("  uvx whop_downloader.py download https://whop.com/course-name /path/to/save")
        print("  uvx whop_downloader.py download https://whop.com/course-name --force")
        print("  uvx whop_downloader.py test https://courses.apps.whop.com/experience/exp_xxx/")
        print("  uvx whop_downloader.py test https://whop.com/course-name --force")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    course_url = sys.argv[2]
    
    if command == "download":
        # Parse arguments
        target_dir = None
        force_reextract = False
        
        for arg in sys.argv[3:]:
            if arg == "--force":
                force_reextract = True
            elif not arg.startswith("--"):
                target_dir = arg
        
        sys.exit(download_command(course_url, target_dir, force_reextract))
    elif command == "test":
        # Parse --force flag for test command
        force_reextract = "--force" in sys.argv[3:]
        sys.exit(test_command(course_url, force_reextract))
    else:
        print(f"Unknown command: {command}")
        print("Use 'download' or 'test'")
        sys.exit(1)


if __name__ == "__main__":
    main()