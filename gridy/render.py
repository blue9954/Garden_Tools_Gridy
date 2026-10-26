from PIL import Image

from .config import Options
from .images import Source, reload_unchanged
from .layout import placement, rows


def compose(sources: list[Source], options: Options, *, full_resolution: bool = False):
    canvas = Image.new("RGB", (options.width, options.height), options.background)
    low_resolution = []
    for source, rect in zip(sources, rows(len(sources), options)):
        image = reload_unchanged(source) if full_resolution else source.preview
        _, _, enlargement = placement(source.size, rect, options.fit)
        if enlargement > 1.001:
            low_resolution.append(source.path.name)
        size, box, _ = placement(image.size, rect, options.fit)
        resized = image.resize(size, Image.Resampling.LANCZOS, box=box)
        x = rect.x + (rect.width - size[0]) // 2
        y = rect.y + (rect.height - size[1]) // 2
        canvas.paste(resized, (x, y), resized.getchannel("A"))
        if full_resolution:
            image.close()
    return canvas, low_resolution

