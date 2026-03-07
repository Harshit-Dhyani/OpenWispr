from pathlib import Path

from PIL import Image

from scripts.generate_brand_assets import generate_brand_assets


def test_generate_brand_assets_creates_packaging_and_frontend_outputs(tmp_path, monkeypatch):
    repo_root = tmp_path / 'repo'
    build_dir = repo_root / 'build'
    frontend_assets = repo_root / 'app' / 'electron' / 'frontend' / 'src' / 'assets'
    build_dir.mkdir(parents=True)
    frontend_assets.mkdir(parents=True)

    source = tmp_path / 'source-logo.png'
    Image.new('RGBA', (512, 512), (32, 24, 68, 255)).save(source)

    monkeypatch.setattr('scripts.generate_brand_assets.REPO_ROOT', repo_root)
    monkeypatch.setattr('scripts.generate_brand_assets.BUILD_DIR', build_dir)
    monkeypatch.setattr('scripts.generate_brand_assets.FRONTEND_ASSETS_DIR', frontend_assets)
    monkeypatch.setattr('scripts.generate_brand_assets.LINUX_ICON_DIR', build_dir / 'icons')

    generated = generate_brand_assets(source)

    expected = [
        build_dir / 'logo.png',
        build_dir / 'icon.ico',
        build_dir / 'icon.icns',
        build_dir / 'icons' / '16x16.png',
        build_dir / 'icons' / '512x512.png',
        frontend_assets / 'openwispr-logo.png',
    ]

    for path in expected:
        assert path.exists(), f'missing generated asset: {path}'

    assert frontend_assets / 'openwispr-logo.svg' not in generated
