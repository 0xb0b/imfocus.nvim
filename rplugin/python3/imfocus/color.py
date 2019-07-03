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

