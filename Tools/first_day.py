"""Replay the first weekday menu reached after the opening's six scripts."""


def _layer(name, x, y, width, height, source=None):
    layer = {
        "image": f"assets/{name}",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }
    if source is not None:
        layer.update(zip(("sourceX", "sourceY", "sourceWidth", "sourceHeight"), source))
    return layer


def _choices(*options):
    return [{"text": label, "target": target} for label, target in options]


def first_day(background, layers, music, script7):
    """Build the original weekday choices and return to the common story."""
    home = {
        "background": background or "assets/Bg_1.png",
        "layers": list(layers or ()),
        "music": music,
        "sceneHeight": 336,
    }

    # vDrawMainWeekDays in mode 0 uses vProcessRepose for the second
    # option. Paid work is a separate mode that appears later.
    back = _choices(("돌아가기", "weekday"))
    beats = {
        "weekday": {
            **home,
            "text": "3월 2일",
            "choices": _choices(
                ("성장", "weekday-grow"),
                ("휴식", "weekday-rest-confirm"),
                ("인벤토리", "weekday-inventory"),
                ("모바일", "weekday-phone"),
            ),
        },
        "weekday-rest-confirm": {
            **home,
            "text": "휴식을 하시겠습니까?",
            "choices": _choices(("예", "weekday-rest"), ("아니오", "weekday")),
        },
        "weekday-rest": {
            **home,
            "text": "휴식",
            "delay": 20 / 30,
            "next": script7,
        },
        "weekday-inventory": {
            **home,
            "text": "인벤토리",
            "layers": [
                *home["layers"],
                _layer("ui_inven_1.png", 32, 60, 296, 70, (2, 2, 355, 84)),
                _layer("ui_inven_1.png", 65, 152, 224, 36, (2, 198, 225, 38)),
            ],
            "choices": back,
        },
        "weekday-phone": {
            **home,
            "text": "모바일",
            "layers": [
                *home["layers"],
                _layer("ui_hm_13.png", 78, 23, 204, 278, (0, 0, 204, 278)),
                _layer("ui_hm_13.png", 107, 83, 147, 33, (206, 2, 143, 36)),
                _layer("ui_hm_13.png", 107, 140, 147, 33, (206, 44, 143, 36)),
            ],
            "choices": back,
        },
    }

    # vWeekGrowKey's four actions select the matching animation sheet.
    # The native player applies the original growth table on entry.
    growth = (
        ("학습", "study", "grow_1_1.png", (0, 0, 104, 173)),
        ("운동", "exercise", "grow_2_1.png", (0, 0, 123, 120)),
        ("매력", "charm", "grow_3_1.png", (0, 0, 104, 170)),
        ("감성", "sensibility", "grow_4_1.png", (0, 0, 114, 171)),
    )
    beats["weekday-grow"] = {
        **home,
        "text": "성장",
        "choices": _choices(
            *((label, f"weekday-{activity}-confirm") for label, activity, _, _ in growth),
            ("돌아가기", "weekday"),
        ),
    }
    for stat, (label, activity, sprite, source) in enumerate(growth):
        target = f"weekday-{activity}"
        beats[f"{target}-confirm"] = {
            **home,
            "text": f"{label}을 하시겠습니까?",
            "choices": _choices(("예", target), ("아니오", "weekday-grow")),
        }
        width, height = source[2:]
        beats[target] = {
            **home,
            "text": label,
            "growthStat": stat,
            "layers": [
                *home["layers"],
                _layer(sprite, (360 - width) / 2, 250 - height, width, height, source),
            ],
            "next": script7,
        }
    return beats
