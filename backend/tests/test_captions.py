from app.services.captions import build_english_captions, pick_lines


def test_caption_line_count_in_contract():
    for dur, lo, hi in ((5, 3, 3), (12, 4, 4), (30, 5, 5), (50, 6, 6)):
        lines = pick_lines(dur)
        assert lo <= len(lines) <= hi
        srt = build_english_captions(dur)
        assert srt.count("-->") == len(lines)
        assert all(len(line.split()) <= 8 for line in lines)
