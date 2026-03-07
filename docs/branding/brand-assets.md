# Brand Asset Pipeline

Use one command to regenerate all packaging icons and frontend logo assets from a source logo.

## Source asset

Drop a source file anywhere in the repo, then run one of these:

```bash
pnpm run brand:icons -- --source build/logo.png
pnpm run brand:icons -- --source path/to/new-logo.png
```

Supported source formats:
- `.png`
- `.jpg`
- `.jpeg`
- `.webp`
- `.svg` if `cairosvg` is installed

## Outputs

The command regenerates:
- `build/logo.png`
- `build/logo.svg` when the source is SVG
- `build/icon.ico`
- `build/icon.icns`
- `build/icons/*.png`
- `app/electron/frontend/src/assets/openwispr-logo.png`
- `app/electron/frontend/src/assets/openwispr-logo.svg` when the source is SVG

## Notes

- Electron Builder already reads icons from `build/`.
- Frontend branding uses the copied asset in `app/electron/frontend/src/assets/`.
- If you want SVG input support, install `cairosvg`; otherwise use PNG/WebP/JPG.
