"""Print the report to PDF with a locally installed Chromium browser (Edge or Chrome).

html_to_pdf(html_path, pdf_path) -> (ok, message). No Python dependencies: it
runs the browser headless with --print-to-pdf. Set SEO_GAP_BROWSER to a browser
executable to override discovery.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

CANDIDATES = {
    "win32": [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
              r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
              r"%LocalAppData%\Google\Chrome\Application\chrome.exe"],
    "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
               "/Applications/Chromium.app/Contents/MacOS/Chromium"],
}
PATH_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"]


def find_browser():
    env = os.environ.get("SEO_GAP_BROWSER")
    if env and os.path.isfile(env):
        return env
    for p in CANDIDATES.get(sys.platform, []):
        p = os.path.expandvars(p)
        if os.path.isfile(p):
            return p
    for name in PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf(html_path, pdf_path, timeout=240):
    browser = find_browser()
    if not browser:
        return False, "no Chrome/Edge found (set SEO_GAP_BROWSER) — open report.html and use Print > Save as PDF"
    url = Path(os.path.abspath(html_path)).as_uri()
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
           f"--print-to-pdf={os.path.abspath(pdf_path)}", url]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"browser print failed: {exc}"
    if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0:
        return True, pdf_path
    return False, "browser ran but produced no PDF — open report.html and use Print > Save as PDF"
