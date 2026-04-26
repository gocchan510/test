"""Build vocabulary.json from TOCFL Novice 1 source CSV + Japanese translations.

Inputs:
  data/source-novice1.csv  (id, traditional, simplified, pinyin, pos, variants)
Output:
  data/vocabulary.json     (full data with zhuyin + Japanese translation)
"""
import csv
import json
from pathlib import Path

from pypinyin import pinyin, Style

# Pinyin syllable → bopomofo (zhuyin). Order matters: longest initials/finals first.
# Reference: standard pinyin-bopomofo table.
_PY_INITIALS = [
    ("zh", "ㄓ"), ("ch", "ㄔ"), ("sh", "ㄕ"),
    ("b", "ㄅ"), ("p", "ㄆ"), ("m", "ㄇ"), ("f", "ㄈ"),
    ("d", "ㄉ"), ("t", "ㄊ"), ("n", "ㄋ"), ("l", "ㄌ"),
    ("g", "ㄍ"), ("k", "ㄎ"), ("h", "ㄏ"),
    ("j", "ㄐ"), ("q", "ㄑ"), ("x", "ㄒ"),
    ("r", "ㄖ"), ("z", "ㄗ"), ("c", "ㄘ"), ("s", "ㄙ"),
]
_PY_FINALS = [
    ("iang", "ㄧㄤ"), ("iong", "ㄩㄥ"), ("uang", "ㄨㄤ"), ("ueng", "ㄨㄥ"),
    ("ang", "ㄤ"), ("eng", "ㄥ"), ("ing", "ㄧㄥ"), ("ong", "ㄨㄥ"),
    ("iao", "ㄧㄠ"), ("uai", "ㄨㄞ"), ("ian", "ㄧㄢ"), ("uan", "ㄨㄢ"),
    ("üan", "ㄩㄢ"), ("uei", "ㄨㄟ"),
    ("an", "ㄢ"), ("en", "ㄣ"), ("in", "ㄧㄣ"), ("un", "ㄨㄣ"), ("ün", "ㄩㄣ"),
    ("ai", "ㄞ"), ("ei", "ㄟ"), ("ao", "ㄠ"), ("ou", "ㄡ"),
    ("ia", "ㄧㄚ"), ("ie", "ㄧㄝ"), ("iu", "ㄧㄡ"),
    ("ua", "ㄨㄚ"), ("uo", "ㄨㄛ"), ("ui", "ㄨㄟ"),
    ("üe", "ㄩㄝ"),
    ("er", "ㄦ"),
    ("a", "ㄚ"), ("o", "ㄛ"), ("e", "ㄜ"), ("i", "ㄧ"), ("u", "ㄨ"), ("ü", "ㄩ"),
]
_TONE_MAP = {
    1: "", 2: "ˊ", 3: "ˇ", 4: "ˋ", 5: "˙",
}
# Vowel-with-diacritic → (plain, tone)
_TONE_VOWELS = {
    "ā":("a",1),"á":("a",2),"ǎ":("a",3),"à":("a",4),
    "ē":("e",1),"é":("e",2),"ě":("e",3),"è":("e",4),
    "ī":("i",1),"í":("i",2),"ǐ":("i",3),"ì":("i",4),
    "ō":("o",1),"ó":("o",2),"ǒ":("o",3),"ò":("o",4),
    "ū":("u",1),"ú":("u",2),"ǔ":("u",3),"ù":("u",4),
    "ǖ":("ü",1),"ǘ":("ü",2),"ǚ":("ü",3),"ǜ":("ü",4),
    "ü":("ü",5),
}


def _strip_tone(syl: str) -> tuple[str, int]:
    """Return (toneless syllable with ü preserved, tone 1-5)."""
    out = []
    tone = 5
    for ch in syl:
        if ch in _TONE_VOWELS:
            base, t = _TONE_VOWELS[ch]
            out.append(base)
            if t != 5:
                tone = t
        else:
            out.append(ch)
    return "".join(out), tone


def pinyin_syllable_to_bopomofo(syl: str) -> str:
    """Convert one toned pinyin syllable (e.g., 'wǒ', 'de', 'guò') to bopomofo."""
    raw, tone = _strip_tone(syl)
    raw = raw.lower()
    # Spelling normalization for zero-initial syllables (y-, w-) into
    # the same form they take after a consonant initial (where pinyin uses
    # -iu/-ui/-un for underlying -iou/-uei/-uen).
    _Y_FIXED = {
        "yi": "i", "yin": "in", "ying": "ing",
        "yu": "ü", "yue": "üe", "yuan": "üan", "yun": "ün",
        "you": "iu",
    }
    _W_FIXED = {
        "wu": "u", "wei": "ui", "wen": "un",
    }
    if raw in _Y_FIXED:
        raw = _Y_FIXED[raw]
    elif raw in _W_FIXED:
        raw = _W_FIXED[raw]
    elif raw.startswith("y"):
        raw = "i" + raw[1:]
    elif raw.startswith("w"):
        raw = "u" + raw[1:]
    # j/q/x + u → j/q/x + ü
    if raw[:1] in ("j", "q", "x") and raw[1:2] == "u":
        raw = raw[0] + "ü" + raw[2:]
    # Strip initial
    initial = ""
    rest = raw
    for sp, bp in _PY_INITIALS:
        if rest.startswith(sp):
            initial = bp
            rest = rest[len(sp):]
            break
    # zh/ch/sh/r/z/c/s + i → empty final (ㄓ/ㄔ/ㄕ/ㄖ/ㄗ/ㄘ/ㄙ + i = no extra symbol)
    if rest == "i" and initial in ("ㄓ", "ㄔ", "ㄕ", "ㄖ", "ㄗ", "ㄘ", "ㄙ"):
        rest = ""
    # Match exact final only — if leftover remains, the input was not a single syllable.
    final_bp = ""
    if rest:
        for sp, bp in _PY_FINALS:
            if rest == sp:
                final_bp = bp
                rest = ""
                break
        if rest:
            raise ValueError(f"Unparseable pinyin syllable: {syl!r} (residue {rest!r})")
    return initial + final_bp + _TONE_MAP[tone]


def pinyin_to_zhuyin(py: str) -> str:
    """Convert space-separated multi-syllable pinyin to space-separated bopomofo."""
    return " ".join(pinyin_syllable_to_bopomofo(s) for s in py.split() if s)


def split_pinyin_syllables(py: str) -> list[str]:
    """Split a concatenated pinyin string like 'wǒmen' or 'méiyǒu' into syllables.

    Strategy: walk left-to-right, greedily matching the longest valid initial+final.
    """
    result = []
    s = py.strip()
    i = 0
    while i < len(s):
        # Try lengths from longest to shortest at this position.
        matched = None
        for length in range(min(7, len(s) - i), 0, -1):
            candidate = s[i:i + length]
            try:
                pinyin_syllable_to_bopomofo(candidate)
                # Validate: must contain a vowel-with-diacritic OR be a neutral-tone syllable.
                # Use a stricter check: require at least one vowel character.
                if any(c in "aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ" for c in candidate.lower()):
                    matched = candidate
                    break
            except Exception:
                pass
        if matched is None:
            raise ValueError(f"Cannot split pinyin: {py!r} at position {i}")
        result.append(matched)
        i += len(matched)
    return result

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "source-novice1.csv"
OUT = ROOT / "data" / "vocabulary.json"

# (canonical Taiwan form to display/speak, Japanese translation for display+TTS)
ENTRIES: dict[str, tuple[str, str]] = {
    "L0-1001": ("我", "私"),
    "L0-1002": ("你", "あなた"),
    "L0-1003": ("他", "彼"),
    "L0-1004": ("我們", "私たち"),
    "L0-1005": ("你們", "あなたたち"),
    "L0-1006": ("他們", "彼ら"),
    "L0-1007": ("您", "あなた様"),
    "L0-1008": ("誰", "誰"),
    "L0-1009": ("姓名", "氏名"),
    "L0-1010": ("人", "人"),
    "L0-1011": ("國", "国"),
    "L0-1012": ("中國", "中国"),
    "L0-1013": ("美國", "アメリカ"),
    "L0-1014": ("日本", "日本"),
    "L0-1015": ("台灣", "台湾"),
    "L0-1016": ("名字", "名前"),
    "L0-1017": ("家", "家"),
    "L0-1018": ("電話", "電話"),
    "L0-1019": ("時間", "時間"),
    "L0-1020": ("小時", "時間、アワー"),
    "L0-1021": ("現在", "今"),
    "L0-1022": ("今年", "今年"),
    "L0-1023": ("今天", "今日"),
    "L0-1024": ("明天", "明日"),
    "L0-1025": ("昨天", "昨日"),
    "L0-1026": ("早上", "朝"),
    "L0-1027": ("上午", "午前"),
    "L0-1028": ("中午", "正午"),
    "L0-1029": ("下午", "午後"),
    "L0-1030": ("晚上", "夜"),
    "L0-1031": ("一", "一、いち"),
    "L0-1032": ("二", "二、に"),
    "L0-1033": ("三", "三、さん"),
    "L0-1034": ("四", "四、よん"),
    "L0-1035": ("五", "五、ご"),
    "L0-1036": ("六", "六、ろく"),
    "L0-1037": ("七", "七、なな"),
    "L0-1038": ("八", "八、はち"),
    "L0-1039": ("九", "九、きゅう"),
    "L0-1040": ("十", "十、じゅう"),
    "L0-1041": ("兩", "二つ"),
    "L0-1042": ("時候", "時、ころ"),
    "L0-1043": ("百", "百"),
    "L0-1044": ("半", "半分"),
    "L0-1045": ("千", "千"),
    "L0-1046": ("爸爸", "お父さん"),
    "L0-1047": ("媽媽", "お母さん"),
    "L0-1048": ("哥哥", "兄"),
    "L0-1049": ("弟弟", "弟"),
    "L0-1050": ("姊姊", "姉"),
    "L0-1051": ("妹妹", "妹"),
    "L0-1052": ("小孩", "子供"),
    "L0-1053": ("的", "の、修飾の助詞"),
    "L0-1054": ("第", "第"),
    "L0-1055": ("分", "分、ふん"),
    "L0-1056": ("點", "時、じ"),
    "L0-1057": ("個", "個、量詞"),
    "L0-1058": ("歲", "歳"),
    "L0-1059": ("年", "年"),
    "L0-1060": ("住", "住む"),
    "L0-1061": ("來", "来る"),
    "L0-1062": ("是", "である"),
    "L0-1063": ("姓", "という姓である"),
    "L0-1064": ("覺得", "と思う、感じる"),
    "L0-1065": ("喜歡", "好きである"),
    "L0-1066": ("打電話", "電話をかける"),
    "L0-1067": ("漂亮", "綺麗"),
    "L0-1068": ("高", "高い、背が高い"),
    "L0-1069": ("老", "年をとっている"),
    "L0-1070": ("好", "良い"),
    "L0-1071": ("很", "とても"),
    "L0-1072": ("真", "本当に"),
    "L0-1073": ("電腦", "パソコン"),
    "L0-1074": ("老師", "先生"),
    "L0-1075": ("買", "買う"),
    "L0-1076": ("忙", "忙しい"),
    "L0-1077": ("學生", "学生"),
    "L0-1078": ("大學", "大学"),
    "L0-1079": ("學校", "学校"),
    "L0-1080": ("中文", "中国語"),
    "L0-1081": ("同學", "クラスメート"),
    "L0-1082": ("字", "字、文字"),
    "L0-1083": ("筆", "ペン"),
    "L0-1084": ("學", "学ぶ"),
    "L0-1085": ("問", "尋ねる"),
    "L0-1086": ("說", "言う、話す"),
    "L0-1087": ("寫", "書く"),
    "L0-1088": ("聽", "聞く"),
    "L0-1089": ("對", "正しい"),
    "L0-1090": ("能", "できる"),
    "L0-1091": ("可以", "してもよい"),
    "L0-1092": ("上課", "授業に出る"),
    "L0-1093": ("知道", "知っている"),
    "L0-1094": ("電視", "テレビ"),
    "L0-1095": ("水", "水"),
    "L0-1096": ("久", "長い時間"),
    "L0-1097": ("早", "早い"),
    "L0-1098": ("再", "再び、もう一度"),
    "L0-1099": ("書", "本"),
    "L0-1100": ("電影", "映画"),
    "L0-1101": ("以前", "以前"),
    "L0-1102": ("以後", "以後"),
    "L0-1103": ("走", "歩く、行く"),
    "L0-1104": ("等", "待つ"),
    "L0-1105": ("看", "見る"),
    "L0-1106": ("就", "すぐに、もう"),
    "L0-1107": ("什麼", "何"),
    "L0-1108": ("朋友", "友達"),
    "L0-1109": ("東西", "物"),
    "L0-1110": ("吧", "でしょう、語気の助詞"),
    "L0-1111": ("呢", "は、語気の助詞"),
    "L0-1112": ("嗎", "か、疑問の助詞"),
    "L0-1113": ("找", "探す"),
    "L0-1114": ("做", "する、作る"),
    "L0-1115": ("再見", "さようなら"),
    "L0-1116": ("怎麼樣", "どう、いかが"),
    "L0-1117": ("叫", "と呼ぶ、と言う"),
    "L0-1118": ("謝謝", "ありがとう"),
    "L0-1119": ("對不起", "ごめんなさい"),
    "L0-1120": ("請問", "お尋ねします"),
    "L0-1121": ("這", "これ"),
    "L0-1122": ("那", "それ、あれ"),
    "L0-1123": ("公車", "バス"),
    "L0-1124": ("車子", "車"),
    "L0-1125": ("到", "到着する、まで"),
    "L0-1126": ("去", "行く"),
    "L0-1127": ("回", "帰る"),
    "L0-1128": ("坐", "座る、乗る"),
    "L0-1129": ("這裡", "ここ"),
    "L0-1130": ("那裡", "そこ、あそこ"),
    "L0-1131": ("哪裡", "どこ"),
    "L0-1132": ("開車", "運転する"),
    "L0-1133": ("錢", "お金"),
    "L0-1134": ("多少", "どのくらい、いくら"),
    "L0-1135": ("給", "あげる、与える"),
    "L0-1136": ("貴", "高い、値段が高い"),
    "L0-1137": ("便宜", "安い"),
    "L0-1138": ("大", "大きい"),
    "L0-1139": ("小", "小さい"),
    "L0-1140": ("難", "難しい"),
    "L0-1141": ("容易", "簡単"),
    "L0-1142": ("有", "ある、いる"),
    "L0-1143": ("想", "したい、思う"),
    "L0-1144": ("幾", "いくつ"),
    "L0-1145": ("塊", "元、量詞"),
    "L0-1146": ("位", "名、人を数える量詞"),
    "L0-1147": ("飯", "ご飯"),
    "L0-1148": ("吃", "食べる"),
    "L0-1149": ("請", "どうぞ、招く"),
    "L0-1150": ("也", "も"),
    "L0-1151": ("不", "ない、否定"),
    "L0-1152": ("沒", "ない、過去の否定"),
    "L0-1153": ("都", "みんな、全部"),
    "L0-1154": ("只", "だけ"),
    "L0-1155": ("可是", "しかし"),
    "L0-1156": ("還是", "それとも、やはり"),
    "L0-1157": ("了", "完了の助詞"),
    "L0-1158": ("得", "補語の助詞"),
    "L0-1159": ("過", "経験の助詞"),
    "L0-1160": ("沒有", "ない"),
}


def to_zhuyin_from_pinyin(py: str) -> str:
    """Convert toned pinyin (possibly with spaces between words) to bopomofo."""
    sylls: list[str] = []
    for chunk in py.split():
        sylls.extend(split_pinyin_syllables(chunk))
    return " ".join(pinyin_syllable_to_bopomofo(s) for s in sylls)


# Pinyin overrides for entries whose canonical form does not map cleanly from CSV
# (parentheses indicate optional characters; we choose one explicit form).
PINYIN_OVERRIDE = {
    "L0-1052": "xiǎohái",   # 小孩(子) → 小孩
    "L0-1094": "diànshì",   # 電視(機) → 電視
    "L0-1124": "chēzi",     # 車(子) → 車子
}


def main() -> None:
    rows: list[dict] = []
    with SRC.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for cols in reader:
            wid = cols[0]
            tw_canonical, ja = ENTRIES[wid]
            pos = cols[4]
            if wid in PINYIN_OVERRIDE:
                py = PINYIN_OVERRIDE[wid]
            else:
                # CSV pinyin may contain "/" for variants; pick first form.
                py = cols[3].split("/")[0].strip()
            rows.append({
                "id": wid,
                "tw": tw_canonical,
                "pinyin": py,
                "zhuyin": to_zhuyin_from_pinyin(py),
                "ja": ja,
                "pos": pos,
            })
    assert len(rows) == 160, f"Expected 160 entries, got {len(rows)}"
    OUT.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} entries to {OUT}")


if __name__ == "__main__":
    main()
