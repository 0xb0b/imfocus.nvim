from isee.rplugin import plugin_name, make_hl_group_name


def test_make_hl_group_name():
    shadow_hl_group = make_hl_group_name([0x8f, 0x8f, 0x8f], [0x1a, 0x2b, 0x3c])
    soft_shadow_hl_group = make_hl_group_name(
        [0x70, 0x71, 0x72], [0x1a, 0x2b, 0x3c], 2)

    assert shadow_hl_group == plugin_name + '#8f8f8f#1a2b3cNone'
    assert soft_shadow_hl_group == plugin_name + '#707172#1a2b3c2'

