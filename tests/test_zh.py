from highscore.zh import to_tw


def test_simplified_to_traditional():
    assert to_tw("动作") == "動作"
    assert to_tw("纪录") == "紀錄"
    assert to_tw("剧情・惊悚") == "劇情・驚悚"


def test_taiwan_vocabulary():
    assert to_tw("网络") == "網路"
    assert to_tw("软件") == "軟體"


def test_traditional_text_unchanged():
    assert to_tw("熊家餐館") == "熊家餐館"
    assert to_tw("女兒在街頭被拐走") == "女兒在街頭被拐走"


def test_non_chinese_unchanged():
    assert to_tw("참교육") == "참교육"
    assert to_tw("Toy Story 5") == "Toy Story 5"


def test_empty_and_none():
    assert to_tw("") == ""
    assert to_tw(None) is None
