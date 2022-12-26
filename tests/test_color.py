from random import seed, randint
from isee.color import (color_distance2, term_to_rgb, rgb_to_closest_term,
                        blend_rgb, decompose_rgb, rgb_to_vim_color, rgb_to_vim_color_safe_chars)


def test_term_to_rgb():
    # ANSI 16 color
    assert term_to_rgb(0) == [0, 0, 0]
    assert term_to_rgb(7) == [0xc0, 0xc0, 0xc0]
    assert term_to_rgb(12) == [0, 0, 0xff]
    assert term_to_rgb(15) == [0xff, 0xff, 0xff]
    # 6x6x6 colors cube
    assert term_to_rgb(16) == [0, 0, 0]
    assert term_to_rgb(115) == [0x87, 0xd7, 0xaf]
    assert term_to_rgb(231) == [0xff, 0xff, 0xff]
    # grayscale
    assert term_to_rgb(232) == [0x08, 0x08, 0x08]
    assert term_to_rgb(243) == [0x76, 0x76, 0x76]
    assert term_to_rgb(255) == [0xee, 0xee, 0xee]


def test_color_distance2():
    navy_blue = [0, 0, 0x80]
    gray = [0x7f, 0x7f, 0x7f]
    blue = [0, 0, 0xff]
    red = [0xff, 0, 0]
    weights = (2, 4, 3)
    assert color_distance2(navy_blue, navy_blue) == 0
    assert color_distance2(navy_blue, navy_blue, weights) == 0
    assert color_distance2(navy_blue, blue) < color_distance2(navy_blue, red)
    assert color_distance2(gray, blue) == color_distance2(gray, red)


def test_rgb_to_closest_term():
    assert 0 == rgb_to_closest_term(term_to_rgb(0))
    assert 12 == rgb_to_closest_term(term_to_rgb(12))
    assert 115 == rgb_to_closest_term(term_to_rgb(115))
    assert 243 == rgb_to_closest_term(term_to_rgb(243))

    seed(4321)
    for i in range(1000):
        random_rgb = [randint(0, 255), randint(0, 255), randint(0, 255)]
        term_color = rgb_to_closest_term(random_rgb)
        distance_sq = color_distance2(random_rgb, term_to_rgb(term_color))
        min_distance_sq = distance_sq
        for term_color in range(256):
            d_sq = color_distance2(random_rgb, term_to_rgb(term_color))
            min_distance_sq = min(d_sq, min_distance_sq)
        assert min_distance_sq == distance_sq


def test_blend_rgb():
    black = [0, 0, 0]
    white = [255, 255, 255]

    gray = blend_rgb(black, white, 0.5)
    assert gray[0] == 128 and gray[1] == gray[0] and gray[2] == gray[0]

    assert blend_rgb(black, white, -1.0) == black
    assert blend_rgb(black, white, 0.0) == black
    assert blend_rgb(black, white, 1.0) == white
    assert blend_rgb(black, white, 2.0) == white


def test_decompose_rgb():
    assert decompose_rgb(0) == [0, 0, 0]
    assert decompose_rgb(0xffffff) == [0xff, 0xff, 0xff]
    assert decompose_rgb(0x1a2b3c) == [0x1a, 0x2b, 0x3c]


def test_rgb_to_vim_color():
    assert rgb_to_vim_color([0, 0, 0]) == '#000000'
    assert rgb_to_vim_color([15, 31, 63]) == '#0f1f3f'
    assert rgb_to_vim_color([0, 0x2b, 0x3c]) == '#002b3c'


def test_rgb_to_vim_color_safe_chars():
    assert rgb_to_vim_color_safe_chars([0, 0, 0]) == '000000'
    assert rgb_to_vim_color_safe_chars([15, 31, 63]) == '0f1f3f'
    assert rgb_to_vim_color_safe_chars([0, 0x2b, 0x3c]) == '002b3c'
