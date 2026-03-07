from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = None
BUILD_DIR = REPO_ROOT / 'build'
FRONTEND_ASSETS_DIR = REPO_ROOT / 'app' / 'electron' / 'frontend' / 'src' / 'assets'
LINUX_ICON_DIR = BUILD_DIR / 'icons'
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICNS_SIZES = (16, 32, 64, 128, 256, 512, 1024)
RASTER_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
VECTOR_EXTENSIONS = {'.svg'}


DEFAULT_SOURCE_CANDIDATES = (
    REPO_ROOT / 'build' / 'logo.png',
    REPO_ROOT / 'build' / 'logo.svg',
    REPO_ROOT / 'app' / 'electron' / 'frontend' / 'src' / 'assets' / 'openwispr-logo.png',
    REPO_ROOT / 'app' / 'electron' / 'frontend' / 'src' / 'assets' / 'openwispr-logo.svg',
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Generate OpenWispr packaging icons and frontend logo assets from a source logo.'
    )
    parser.add_argument(
        '--source',
        default=None,
        help='Path to the source logo. Raster formats are supported directly; SVG requires cairosvg.',
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def resolve_source(source_arg: str | None) -> Path:
    if source_arg:
        return Path(source_arg).resolve()
    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        'No source logo found. Pass --source or add build/logo.png or frontend/src/assets/openwispr-logo.png.'
    )


def load_source_image(source: Path) -> Image.Image:
    suffix = source.suffix.lower()
    if suffix in RASTER_EXTENSIONS:
        with Image.open(source) as image:
            return image.convert('RGBA')
    if suffix in VECTOR_EXTENSIONS:
        return render_svg_to_image(source)
    raise ValueError(f'Unsupported source format: {source.suffix}')


def render_svg_to_image(source: Path) -> Image.Image:
    try:
        import cairosvg  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            'SVG input requires cairosvg. Install it or provide a PNG/WebP/JPG source.'
        ) from exc

    png_bytes = cairosvg.svg2png(url=str(source))
    from io import BytesIO

    return Image.open(BytesIO(png_bytes)).convert('RGBA')


def write_png(image: Image.Image, destination: Path, size: int) -> None:
    ensure_parent(destination)
    resized = image.copy()
    resized.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    x = (size - resized.width) // 2
    y = (size - resized.height) // 2
    canvas.paste(resized, (x, y), resized)
    canvas.save(destination, format='PNG')


def write_ico(image: Image.Image, destination: Path, sizes: Iterable[int]) -> None:
    ensure_parent(destination)
    base = image.copy()
    base.save(destination, format='ICO', sizes=[(size, size) for size in sizes])


def write_icns(image: Image.Image, destination: Path, size: int) -> None:
    ensure_parent(destination)
    square = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    resized = image.copy()
    resized.thumbnail((size, size), Image.Resampling.LANCZOS)
    square.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2), resized)
    square.save(destination, format='ICNS')


def copy_source_assets(source: Path) -> None:
    build_png = BUILD_DIR / 'logo.png'
    build_svg = BUILD_DIR / 'logo.svg'
    ensure_parent(build_png)
    if source.suffix.lower() in RASTER_EXTENSIONS and source.resolve() != build_png.resolve():
        shutil.copy2(source, build_png)
    if source.suffix.lower() in VECTOR_EXTENSIONS and source.resolve() != build_svg.resolve():
        shutil.copy2(source, build_svg)


def generate_brand_assets(source: Path) -> list[Path]:
    if not source.exists():
        raise FileNotFoundError(f'Source logo not found: {source}')

    image = load_source_image(source)
    copy_source_assets(source)

    generated: list[Path] = []

    frontend_png = FRONTEND_ASSETS_DIR / 'openwispr-logo.png'
    write_png(image, frontend_png, 512)
    generated.append(frontend_png)

    if source.suffix.lower() in VECTOR_EXTENSIONS:
        frontend_svg = FRONTEND_ASSETS_DIR / 'openwispr-logo.svg'
        ensure_parent(frontend_svg)
        shutil.copy2(source, frontend_svg)
        generated.append(frontend_svg)

    for size in PNG_SIZES:
        icon_path = LINUX_ICON_DIR / f'{size}x{size}.png'
        write_png(image, icon_path, size)
        generated.append(icon_path)

    ico_path = BUILD_DIR / 'icon.ico'
    write_ico(image, ico_path, ICO_SIZES)
    generated.append(ico_path)

    icns_path = BUILD_DIR / 'icon.icns'
    write_icns(image, icns_path, max(ICNS_SIZES))
    generated.append(icns_path)

    build_png = BUILD_DIR / 'logo.png'
    if build_png not in generated:
        generated.append(build_png)
    if (BUILD_DIR / 'logo.svg').exists():
        generated.append(BUILD_DIR / 'logo.svg')

    return generated


def main() -> int:
    args = parse_args()
    source = resolve_source(args.source)
    try:
        generated = generate_brand_assets(source)
    except Exception as exc:
        print(f'[brand:icons] {exc}', file=sys.stderr)
        return 1

    print(f'[brand:icons] source={source}')
    for path in generated:
        print(f'[brand:icons] wrote={path.relative_to(REPO_ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
