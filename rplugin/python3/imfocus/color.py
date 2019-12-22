from itertools import chain


# look-up table for the first 16 of 256 terminal colors
ansi16 = (
    # ANSI normal 0 - 7
    (0, 0, 0),
    (128, 0, 0),
    (0, 128, 0),
    (128,128, 0),
    (0, 0, 128),
    (128, 0, 128),
    (0, 128, 128),
    (192, 192, 192),
    # ANSI highlight 8 - 15
    (128, 128, 128),
    (255, 0, 0),
    (0, 255, 0),
    (255, 255, 0),
    (0, 0, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255)
)


def term_to_rgb(index):
    if index < 16:
        return ansi16[index]
    elif index < 232:
        # 6x6x6 rgb colors: 16 - 231
        # each channel in terminal color cube has one of the 6 values:
        # 0, 0x5f, 0x87, 0xaf, 0xd7, 0xff
        index -= 16
        b = index % 6
        index //= 6
        g = index % 6
        r = index // 6
        return [95 + (c - 1) * 40 if c > 0 else 0 for c in (r, g, b)]
    else:
        # grayscale colors: 232 - 255
        return [8 + (index - 232) * 10] * 3


def color_distance(rgb1, rgb2, weights=(1, 1, 1)):
    return sum([w * (ch1 - ch2)**2 for w, ch1, ch2 in zip(weights, rgb1, rgb2)])


def rgb_to_closest_term(rgb):
    index = 0
    min_distance = None
    # check ansi16 and grayscale colors
    for i in chain(range(16), range(232, 256)):
        distance = color_distance(rgb, term_to_rgb(i))
        if min_distance is None or distance < min_distance:
            min_distance = distance
            index = i
    # check the closest color in 6x6x6 terminal color cube
    def get_channel216(c):
        if c < 95:
            return round(c / 95)
        else:
            return round((c - 95) / 40) + 1
    r216, g216, b216 = map(get_channel216, rgb)
    i = (r216 * 6 + g216) * 6 + b216
    if color_distance(rgb, term_to_rgb(i)) < min_distance:
        index = i
    return index


def blend_rgb(rgb1, rgb2, coeff):
    # blending coefficient 0 results in pure color1,
    # coefficient 1 results in pure color2
    # linear
    return [round((1 - coeff) * ch1 + coeff * ch2)
            for ch1, ch2 in zip(rgb1, rgb2)]


def decompose_rgb(color):
    r = (color >> 16) & 0xff
    g = (color >> 8) & 0xff
    b = color & 0xff
    return r, g, b


def rgb_to_vim_color(rgb):
    r, g, b = rgb
    color = (((r << 8) | g) << 8) | b
    return f"#{color:06x}"


def vim_color_to_rgb(vim_color):
    color = int(vim_color.replace("#", "0x"), 0)
    return decompose_rgb(color)

