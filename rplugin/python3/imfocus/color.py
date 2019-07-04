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


def cterm_to_rgb(index):
    if index < 16:
        return ansi16[index]
    elif index < 232:
        # 6x6x6 RGB colors 16 - 231
        index -= 16
        b = index % 6
        index /= 6
        g = index % 6
        r = index / 6
        return tuple([95 + (c - 1) * 40 if c > 0 else 0 for c in (r, g, b)])
    else:
        # grayscale colors 232 - 255
        return tuple([8 + (index - 232) * 10] * 3)


def rgb_blend(rgb_a, rgb_b, coeff):
    # blending coefficient 0 results in pure color1, coefficient 1 results in pure color2
    # linear
    return [round((1 - coeff) * channel_a + coeff * channel_b)
            for channel_a, channel_b in zip(rgb_a, rgb_b)]


def rgb_decompose(color):
    color = int(color)
    r = (color >> 16) & 0xff
    g = (color >> 8) & 0xff
    b = color & 0xff
    return r, g, b


def rgb_to_vim_color(rgb):
    r, g, b = rgb
    color = (((r << 8) | g) << 8) | b
    return "#{:x}".format(color)

