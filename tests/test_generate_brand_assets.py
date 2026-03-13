import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image

MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "generate" / "generate_brand_assets.py"
)
spec = importlib.util.spec_from_file_location("generate_brand_assets", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class GenerateBrandAssetsTests(unittest.TestCase):
    def test_write_png_trims_transparent_padding_for_icons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            for x in range(35, 65):
                for y in range(35, 65):
                    source.putpixel((x, y), (255, 255, 255, 255))

            destination = Path(temp_dir) / "icon.png"
            module.write_png(
                module.trim_to_alpha_bounds(source), destination, 128, module.ICON_PADDING_RATIO
            )

            with Image.open(destination) as icon_file:
                generated = icon_file.convert("RGBA")
            bbox = generated.getchannel("A").getbbox()
            assert bbox is not None
            visible_width = bbox[2] - bbox[0]
            visible_height = bbox[3] - bbox[1]
            self.assertGreaterEqual(visible_width / generated.width, 0.8)
            self.assertGreaterEqual(visible_height / generated.height, 0.8)

    def test_write_ico_keeps_large_visible_area(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            for x in range(35, 65):
                for y in range(35, 65):
                    source.putpixel((x, y), (255, 255, 255, 255))

            destination = Path(temp_dir) / "icon.ico"
            module.write_ico(
                module.trim_to_alpha_bounds(source),
                destination,
                (16, 32, 64, 128, 256),
                module.ICON_PADDING_RATIO,
            )

            with Image.open(destination) as icon_file:
                generated = icon_file.convert("RGBA")
            bbox = generated.getchannel("A").getbbox()
            assert bbox is not None
            visible_width = bbox[2] - bbox[0]
            visible_height = bbox[3] - bbox[1]
            self.assertGreaterEqual(visible_width / generated.width, 0.8)
            self.assertGreaterEqual(visible_height / generated.height, 0.8)


if __name__ == "__main__":
    unittest.main()
