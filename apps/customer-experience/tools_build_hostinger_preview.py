from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys
import zipfile


ROOT = Path(__file__).resolve().parent
ALLOWED_ROOT_SUFFIXES = {".html", ".css", ".svg", ".webmanifest"}
ALLOWED_NESTED_SUFFIXES = {".mjs", ".json"}
HOSTINGER_LANDING_SOURCE = ROOT / "ruby-storefront-progress.html"
ENGINEERING_LANDING_SOURCE = ROOT / "index.html"
ALLOWED_FETCH_TARGETS = {
    "./fixtures/first-party-quick-pickup.json",
    "./fixtures/quick-pickup-inventory-snapshot.json",
    "./fixtures/quick-pickup-capacity-snapshot.json",
    "./fixtures/quick-pickup-disable-control.json",
    "./fixtures/catalog.json",
    "./fixtures/final-confirmation.json",
    "./fixtures/payment-provider.json",
    "./fixtures/pickup-policy.json",
}
PREVIEW_MARKER = "PHIL_AI_OS_PREPRODUCTION_PREVIEW"
ROBOTS_META = '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">'
BANNER = (
    '<div class="phil-preview-boundary" role="status" aria-label="Pre-production preview notice">'
    '<strong>PRE-PRODUCTION PREVIEW</strong> · No live orders, payments, SMS, inventory, or WooCommerce writes.'
    '</div>'
)
BANNER_STYLE = """<style id="phil-preview-boundary-style">
.phil-preview-boundary{position:relative;z-index:99999;padding:.65rem 1rem;text-align:center;background:#2b2020;color:#fff;font:600 13px/1.4 system-ui,-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;letter-spacing:.01em}
.phil-preview-boundary strong{letter-spacing:.06em}
</style>"""
ENGINEERING_LINK = '<p class="engineering-link"><a href="./engineering-preview.html">Open engineering flow preview</a></p>'
EXISTING_PREVIEW_BOUNDARY_RE = re.compile(
    r'class=["\'][^"\']*\bpreview-strip\b[^"\']*["\']',
    flags=re.IGNORECASE,
)


def _rewrite_browser_module_refs(text: str) -> str:
    """Use .js in the deployable bundle so shared hosting serves module MIME reliably."""
    return text.replace(".mjs", ".js")


def _inject_preview_boundary(text: str) -> str:
    lower = text.lower()
    if "<head" not in lower or "<body" not in lower:
        raise ValueError("HTML preview source must contain head and body elements")

    text = re.sub(
        r'<meta\s+name=["\']robots["\'][^>]*>',
        ROBOTS_META,
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    if ROBOTS_META.lower() not in text.lower():
        text = re.sub(r"</head>", f"  {ROBOTS_META}\n</head>", text, count=1, flags=re.IGNORECASE)

    if PREVIEW_MARKER not in text:
        has_visible_boundary = EXISTING_PREVIEW_BOUNDARY_RE.search(text) is not None
        marker = f"<!-- {PREVIEW_MARKER} -->\n"
        if not has_visible_boundary:
            marker += f"{BANNER_STYLE}\n{BANNER}\n"
        text = re.sub(r"(<body[^>]*>)", r"\1\n" + marker, text, count=1, flags=re.IGNORECASE)
    return text


def _write_preview_html(source: Path, target: Path) -> None:
    target.write_text(
        _rewrite_browser_module_refs(
            _inject_preview_boundary(source.read_text(encoding="utf-8"))
        ),
        encoding="utf-8",
    )


def _write_hostinger_landing(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")
    if "engineering-preview.html" not in text:
        text, replacements = re.subn(
            r"</main>",
            f"  {ENGINEERING_LINK}\n  </main>",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        if replacements != 1:
            raise ValueError("Hostinger landing source must contain a main element")
    target.write_text(
        _rewrite_browser_module_refs(_inject_preview_boundary(text)),
        encoding="utf-8",
    )


def _copy_browser_module(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _rewrite_browser_module_refs(source.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


def _copy_bundle_tree(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    for source in ROOT.iterdir():
        if source.is_file() and source.suffix in ALLOWED_ROOT_SUFFIXES:
            target = destination / source.name
            if source.suffix == ".html":
                _write_preview_html(source, target)
            else:
                shutil.copy2(source, target)

    # Keep the repository's source index as the isolated engineering app shell,
    # but promote the branded Ruby storefront to the temporary Hostinger preview
    # landing. The engineering shell remains directly reachable from that landing.
    _write_preview_html(ENGINEERING_LANDING_SOURCE, destination / "engineering-preview.html")
    _write_hostinger_landing(HOSTINGER_LANDING_SOURCE, destination / "index.html")

    for dirname in ("src", "fixtures"):
        source_dir = ROOT / dirname
        if not source_dir.exists():
            continue
        for source in source_dir.rglob("*"):
            if not source.is_file() or source.suffix not in ALLOWED_NESTED_SUFFIXES:
                continue
            relative = source.relative_to(ROOT)
            if source.suffix == ".mjs":
                target = destination / relative.with_suffix(".js")
                _copy_browser_module(source, target)
            else:
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    (destination / "PREVIEW_BOUNDARY.txt").write_text(
        "PRE-PRODUCTION ONLY\n"
        "No live orders, payments, SMS, inventory changes, WooCommerce writes, DNS changes, or production publication are authorized.\n",
        encoding="utf-8",
    )


def _validate_script_network_calls(text: str, script_name: str) -> None:
    lower = text.lower()
    if "xmlhttprequest" in lower:
        raise ValueError(f"network-capable browser call found in preview bundle: {script_name}")

    fetch_calls = list(re.finditer(r"\bfetch\s*\(", text, flags=re.IGNORECASE))
    literal_fetches = list(
        re.finditer(r"\bfetch\s*\(\s*([\"'])([^\"']+)\1", text, flags=re.IGNORECASE)
    )

    # Direct fetch calls must use an allowlisted bundled fixture. A small local
    # helper may call fetch(path) only when every call site passes an allowlisted
    # literal fixture path; this preserves the fail-closed boundary without
    # rejecting the existing cart preview's fixture loader abstraction.
    dynamic_fetches = len(fetch_calls) - len(literal_fetches)
    if dynamic_fetches:
        helper_match = re.search(
            r"async\s+function\s+fetchFixture\s*\(\s*path\s*\)\s*\{(?P<body>.*?)\n\}",
            text,
            flags=re.DOTALL,
        )
        if dynamic_fetches != 1 or helper_match is None or not re.search(r"\bfetch\s*\(\s*path\s*,", helper_match.group("body")):
            raise ValueError(f"dynamic or unverified fetch call found in preview bundle: {script_name}")
        without_helper = text[: helper_match.start()] + text[helper_match.end() :]
        helper_calls = re.findall(r"\bfetchFixture\s*\(\s*([\"'])([^\"']+)\1\s*\)", without_helper)
        all_helper_calls = re.findall(r"\bfetchFixture\s*\(", without_helper)
        if len(helper_calls) != len(all_helper_calls):
            raise ValueError(f"dynamic or unverified fixture helper call found in preview bundle: {script_name}")
        for _, target in helper_calls:
            if target not in ALLOWED_FETCH_TARGETS:
                raise ValueError(f"external or unapproved fixture helper target found in preview bundle: {script_name}")

    for match in literal_fetches:
        target = match.group(2)
        if target not in ALLOWED_FETCH_TARGETS:
            raise ValueError(f"external or unapproved fetch target found in preview bundle: {script_name}")


def _validate_bundle(destination: Path) -> None:
    html_files = sorted(destination.glob("*.html"))
    if not html_files or not (destination / "index.html").exists():
        raise ValueError("preview bundle must contain index.html and HTML preview pages")

    for html in html_files:
        text = html.read_text(encoding="utf-8")
        lower = text.lower()
        if PREVIEW_MARKER not in text:
            raise ValueError(f"missing preview boundary marker: {html.name}")
        if 'name="robots"' not in lower or "noindex" not in lower or "noarchive" not in lower:
            raise ValueError(f"missing strict robots policy: {html.name}")
        if "rubyscakedelights.shop" in lower:
            raise ValueError(f"production hostname must not be embedded in preview bundle: {html.name}")
        if ".mjs" in text:
            raise ValueError(f"Hostinger preview HTML must use .js browser modules: {html.name}")

    module_files = sorted((destination / "src").glob("*.js"))
    if not module_files:
        raise ValueError("preview bundle must contain Hostinger-compatible .js browser modules")
    if any((destination / "src").glob("*.mjs")):
        raise ValueError("preview bundle must not contain .mjs browser modules")

    for script in module_files:
        text = script.read_text(encoding="utf-8")
        if ".mjs" in text:
            raise ValueError(f"Hostinger preview module import must use .js: {script.name}")
        _validate_script_network_calls(text, script.name)


def build(output_zip: Path) -> Path:
    workdir = output_zip.parent / f".{output_zip.stem}-build"
    if workdir.exists():
        shutil.rmtree(workdir)
    preview_root = workdir / "preview"
    try:
        _copy_bundle_tree(preview_root)
        _validate_bundle(preview_root)
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        if output_zip.exists():
            output_zip.unlink()
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(preview_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(workdir))
        return output_zip
    finally:
        if workdir.exists():
            shutil.rmtree(workdir)


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "ruby-cx-hostinger-preview.zip"
    built = build(output.resolve())
    print(f"PHIL_AI_OS_HOSTINGER_PREVIEW_BUNDLE_GREEN path={built}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
