from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import errno

from PIL import Image
import pytest

from gridy.config import GridyError, Options, PRESETS
from gridy.images import import_batch, read_source, source_anchor, SRGB_BYTES
from gridy.layout import rows
from gridy.render import compose
from gridy.export import save_collage, verify_output


@pytest.fixture
def photos(tmp_path):
    folder = tmp_path / "사진 원본"
    folder.mkdir()
    paths = []
    for name, color, size in [("photo10.png", "blue", (500, 300)),
                              ("photo2.png", "green", (300, 500)),
                              ("photo1.png", "red", (500, 500))]:
        path = folder / name
        Image.new("RGB", size, color).save(path)
        paths.append(str(path))
    return paths


def test_layout_reference_and_remainder():
    result = rows(3, Options())
    assert [(r.x, r.y, r.width, r.height) for r in result] == [
        (40, 40, 1000, 410), (40, 470, 1000, 410), (40, 900, 1000, 410)]
    odd = rows(3, Options(gap=19))
    assert [r.height for r in odd] == [411, 411, 410]
    assert odd[-1].y + odd[-1].height == 1310


@pytest.mark.parametrize("size", PRESETS.values())
@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("margin,gap", [(0, 0), (200, 200)])
def test_layout_boundary(size, count, margin, gap):
    options = Options(*size, margin, gap)
    result = rows(count, options)
    assert result[0].x == result[0].y == margin
    assert result[-1].y + result[-1].height == size[1] - margin
    assert all(r.width > 0 and r.height > 0 for r in result)
    assert all(b.y - (a.y + a.height) == gap for a, b in zip(result, result[1:]))


def test_import_transaction_order_duplicate(photos, tmp_path):
    sources, duplicates = import_batch(photos + [photos[0]], [])
    assert [s.path.name for s in sources] == ["photo1.png", "photo2.png", "photo10.png"]
    assert duplicates == 1
    added, duplicates = import_batch(photos, sources)
    assert not added and duplicates == 3
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    existing = sources[:1]
    with pytest.raises(GridyError):
        import_batch([photos[0], str(bad)], existing)
    assert existing == sources[:1]


def test_too_many_rejected(photos, tmp_path):
    fourth = tmp_path / "extra.png"
    Image.new("RGB", (5, 5)).save(fourth)
    with pytest.raises(GridyError, match="2~3"):
        import_batch(photos + [str(fourth)], [])


def test_mismatched_extension_and_animation(tmp_path):
    fake = tmp_path / "fake.jpg"
    Image.new("RGB", (8, 8)).save(fake, "PNG")
    with pytest.raises(GridyError, match="확장자"):
        read_source(fake)
    animated = tmp_path / "animated.png"
    Image.new("RGB", (8, 8), "red").save(animated, save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")], duration=100)
    with pytest.raises(GridyError, match="애니메이션"):
        read_source(animated)


def test_limits_before_decode(tmp_path, monkeypatch):
    import gridy.images as module
    path = tmp_path / "limit.png"
    Image.new("RGB", (30, 20)).save(path)
    monkeypatch.setattr(module, "MAX_PIXELS", 500)
    with pytest.raises(GridyError, match="60MP"):
        read_source(path)
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 10)
    with pytest.raises(GridyError, match="100MB"):
        read_source(path)


def test_orientation_and_profiles(tmp_path):
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 80), "red").save(path, exif=exif, icc_profile=SRGB_BYTES)
    image, _, _ = read_source(path)
    assert image.size == (80, 40)
    assert not image.info
    assert image.getpixel((20, 20))[0] > 250
    bad = tmp_path / "bad-profile.png"
    Image.new("RGB", (10, 10)).save(bad, icc_profile=b"bad profile")
    with pytest.raises(GridyError, match="変換|변환"):
        read_source(bad)
    cmyk = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (10, 10)).save(cmyk)
    with pytest.raises(GridyError, match="ICC"):
        read_source(cmyk)


def test_color_order_and_transparency(photos, tmp_path):
    sources, _ = import_batch(photos, [])
    image, _ = compose(sources, Options(background="#123456", fit="cover"))
    assert image.getpixel((0, 0)) == (18, 52, 86)
    assert image.getpixel((500, 200)) == (255, 0, 0)
    assert image.getpixel((500, 600)) == (0, 128, 0)
    assert image.getpixel((500, 1000)) == (0, 0, 255)
    assert image.getpixel((500, 455)) == (18, 52, 86)
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(path)
    transparent, _ = import_batch([str(path)], [])
    image, _ = compose(transparent, Options(background="#0000FF"))
    assert image.getpixel((540, 675)) == (128, 0, 127)


def test_contain_retains_edges_and_cover_crops(tmp_path):
    path = tmp_path / "edges.png"
    image = Image.new("RGB", (200, 100), "green")
    image.paste("red", (0, 0, 10, 100))
    image.paste("blue", (190, 0, 200, 100))
    image.save(path)
    sources, _ = import_batch([str(path)], [])
    contained, _ = compose(sources, Options())
    assert contained.getpixel((45, 675)) == (255, 0, 0)
    assert contained.getpixel((1034, 675)) == (0, 0, 255)
    covered, _ = compose(sources, Options(fit="cover"))
    assert covered.getpixel((45, 675)) == (0, 128, 0)
    assert covered.getpixel((1034, 675)) == (0, 128, 0)


@pytest.mark.parametrize("size", PRESETS.values())
@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_export_roundtrip_and_originals(photos, size, format):
    sources, _ = import_batch(photos, [])
    before = [(sha256(s.path.read_bytes()).hexdigest(), s.path.stat().st_mtime_ns) for s in sources]
    options = Options(*size, format=format)
    output = save_collage(sources, options)
    assert output.parent == sources[0].path.parent
    verify_output(output, options)
    with Image.open(output) as result:
        assert result.size == size
        assert result.mode == "RGB" and not result.getexif()
    assert before == [(sha256(s.path.read_bytes()).hexdigest(), s.path.stat().st_mtime_ns) for s in sources]
    assert not list(output.parent.glob(".gridy-*.tmp"))


def test_anchor_stable_after_reorder(photos, tmp_path):
    sources, _ = import_batch(photos[:1], [])
    other = tmp_path / "other.png"
    Image.new("RGB", (40, 40)).save(other)
    added, _ = import_batch([str(other)], sources)
    sources.extend(added)
    sources.reverse()
    assert source_anchor(sources).path == Path(photos[0])
    assert save_collage(sources, Options()).parent == Path(photos[0]).parent
    assert source_anchor(sources[:1]).path == other


def test_collision_and_race(photos, monkeypatch):
    import gridy.export as module
    sources, _ = import_batch(photos, [])
    now = datetime(2026, 10, 9, 15, 30, 45)
    first = save_collage(sources, Options(), now=now)
    original = first.read_bytes()
    second = save_collage(sources, Options(), now=now)
    assert second.stem.endswith("_001") and first.read_bytes() == original
    real_publish = module._publish
    injected = []
    def collision(temp, destination):
        if destination.name.endswith("_002.jpg") and not injected:
            destination.write_bytes(b"another writer")
            injected.append(destination)
        real_publish(temp, destination)
    monkeypatch.setattr(module, "_publish", collision)
    third = save_collage(sources, Options(), now=now)
    assert third.stem.endswith("_003")
    assert injected[0].read_bytes() == b"another writer"


def test_changed_missing_source_and_invalid_count(photos):
    sources, _ = import_batch(photos, [])
    with pytest.raises(GridyError, match="2~3"):
        save_collage(sources[:1], Options())
    source = sources[0]
    Image.new("RGB", (15, 15)).save(source.path)
    with pytest.raises(GridyError, match="변경"):
        save_collage(sources, Options())
    source.path.unlink()
    with pytest.raises(GridyError):
        save_collage(sources, Options())


@pytest.mark.parametrize("failure", [errno.ENOSPC, errno.EACCES])
def test_write_failure_preserves_sources_and_cleans_temp(photos, monkeypatch, failure):
    sources, _ = import_batch(photos, [])
    before = [s.path.read_bytes() for s in sources]
    def fail(*args, **kwargs):
        raise OSError(failure, "injected storage failure")
    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(GridyError, match="저장하지 못했습니다"):
        save_collage(sources, Options())
    assert [s.path.read_bytes() for s in sources] == before
    assert not list(sources[0].path.parent.glob(".gridy-*.tmp"))


def test_output_validator_rejects_wrong_dimensions(tmp_path):
    path = tmp_path / "wrong.png"
    Image.new("RGB", (10, 10)).save(path, icc_profile=SRGB_BYTES)
    with pytest.raises(GridyError, match="크기"):
        verify_output(path, Options(format="PNG"))


def test_extremely_narrow_cover_does_not_allocate_giant_resize(tmp_path):
    path = tmp_path / "narrow.png"
    Image.new("RGB", (1, 10000), "red").save(path)
    sources, _ = import_batch([str(path)], [])
    image, low = compose(sources, Options(fit="cover"), full_resolution=True)
    assert image.size == (1080, 1350)
    assert image.getpixel((540, 675)) == (255, 0, 0)
    assert low

