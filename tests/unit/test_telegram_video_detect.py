from types import SimpleNamespace

from src.parsers.telegram.parser import _message_is_video, _video_too_large
from src.static.settings import MAX_VIDEO_SIZE_MB


def _msg(mime=None, ext=None, size=None, name=None, has_file=True):
    # message.file is telethon's File helper: .mime_type, .name (DocumentAttributeFilename,
    # may carry its own extension), .ext (mime-derived extension), .size — all without
    # downloading. telethon names the download by the filename's ext first, mime second.
    file = SimpleNamespace(mime_type=mime, ext=ext, size=size, name=name) if has_file else None
    return SimpleNamespace(file=file)


# ---- _message_is_video: only media telethon saves as .mp4 counts as video --------

def test_mp4_video_detected():
    # Normal compressed Telegram video: mime video/mp4, no filename attr, mime-ext .mp4.
    assert _message_is_video(_msg(mime='video/mp4', ext='.mp4')) is True


def test_uppercase_ext_still_detected():
    # download_media names it clip.MP4; phase-2 _is_video lowercases, so must agree.
    assert _message_is_video(_msg(mime='video/mp4', ext='.MP4')) is True


def test_non_mp4_video_not_detected():
    # .mov/.webm/.mkv download with those extensions; phase-2 can't publish them as
    # video, so they must NOT be flagged (else they'd waste a pool slot / starve).
    for mime, ext in (('video/quicktime', '.mov'), ('video/webm', '.webm'),
                      ('video/x-matroska', '.mkv')):
        assert _message_is_video(_msg(mime=mime, ext=ext)) is False


def test_mp4_mime_but_mov_filename_not_detected():
    # Residual guard: telethon names the file by the filename attr's extension FIRST,
    # so a video/mp4 doc literally named clip.mov downloads as .mov -> phase-2 sees a
    # photo. Phase-1 must agree (NOT flag it video), or we reopen the starvation path.
    assert _message_is_video(_msg(mime='video/mp4', ext='.mp4', name='clip.mov')) is False


def test_mp4_filename_overrides_odd_mime():
    # Reverse: a video-mime doc named clip.mp4 downloads as .mp4; phase-1 agrees.
    assert _message_is_video(_msg(mime='video/quicktime', ext='.mov', name='clip.mp4')) is True


def test_photo_not_detected():
    assert _message_is_video(_msg(mime='image/jpeg', ext='.jpg')) is False


def test_audio_mp4_not_detected():
    # audio/mp4 saves as .m4a, not a publishable video.
    assert _message_is_video(_msg(mime='audio/mp4', ext='.m4a')) is False


def test_no_media_not_detected():
    assert _message_is_video(_msg(has_file=False)) is False


def test_missing_ext_not_detected():
    assert _message_is_video(_msg(mime='video/mp4', ext=None)) is False


# ---- _video_too_large: pre-download size gate ------------------------------------

def test_oversize_video_flagged():
    big = (MAX_VIDEO_SIZE_MB + 1) * 1024 * 1024
    assert _video_too_large(_msg(size=big)) is True


def test_normal_size_not_flagged():
    assert _video_too_large(_msg(size=5 * 1024 * 1024)) is False


def test_unknown_size_fails_open():
    # No size metadata => don't cut here; _large_video_size backstops post-download.
    assert _video_too_large(_msg(size=None)) is False
    assert _video_too_large(_msg(has_file=False)) is False
