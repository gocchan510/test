# TOCFL Novice 1 (準備一級) 聞き流しMP3生成パイプライン

TOCFL公式 華語八千詞 **準備一級 全160語**を、台湾華語(女声) → 日本語(男声) の順に
読み上げる音声ファイルをローカルで生成する。

## 出力

- `audio/words/<id>_zh.mp3` / `<id>_ja.mp3` … 単語ごとの個別MP3
- `audio/playlists/full_1.0x.mp3` … 全160語を連結したループ用MP3 (通常速度)
- `audio/playlists/full_0.7x.mp3` … 0.7倍速版
- `audio/playlists/full_1.3x.mp3` … 1.3倍速版

### 1単語あたりの再生パターン

```
[中文] 0.5秒 [中文(2回目)] 1.0秒 [日本語] 2.0秒 → 次の単語
```

シャドーイング用の間隔。`scripts/build_playlist.py` の `GAP_REPEAT / GAP_BETWEEN / GAP_NEXT` を編集すれば変えられる。

### 声

| 言語 | Voice ID | 性別 |
|---|---|---|
| 台湾華語 | `zh-TW-HsiaoChenNeural` | 女性 |
| 日本語 | `ja-JP-KeitaNeural` | 男性 |

`scripts/generate_audio.py` の `ZH_VOICE` / `JA_VOICE` で他の声に切替可。
利用可能voice一覧: `python3 -m edge_tts --list-voices | grep -E '(zh-TW|ja-JP)'`

## セットアップ

```bash
pip3 install edge-tts pypinyin
sudo apt-get install ffmpeg   # macOSは brew install ffmpeg
```

## 実行手順

```bash
# 1. 語彙データを生成 (data/vocabulary.json)
python3 scripts/build_data.py

# 2. 各単語のMP3を生成 (160 × 2 = 320ファイル)
#    edge-ttsはMicrosoftのオンラインTTSを使うのでネット接続必須
python3 scripts/generate_audio.py

# 3. 全160語を連結 + 0.7x/1.3x速度版を生成
python3 scripts/build_playlist.py
```

## データソース

- 語彙リスト: TOCFL公式 華語八千詞 (2023版) より準備一級 (`L0-1xxx`) 160語  
  出典: <https://github.com/ivankra/tocfl> / `tocfl-202307.csv`
- 拼音: 上記CSVの値（声調記号付き）
- 注音: 拼音から自動変換（`scripts/build_data.py` 内に変換テーブル内蔵）
- 日本語訳: 手動付与（基本語彙）

## ファイル構成

```
tocfl-novice1/
├── data/
│   ├── source-novice1.csv     # 元データ (160語)
│   └── vocabulary.json        # 加工済みデータ
├── scripts/
│   ├── build_data.py          # CSV → JSON, 注音生成
│   ├── generate_audio.py      # JSON → 個別MP3 (edge-tts)
│   └── build_playlist.py      # 個別MP3 → 連結MP3 + 速度版
└── audio/
    ├── words/                 # 個別MP3 (gitignore推奨)
    └── playlists/             # 連結済みMP3
```

## Androidでの聞き方

最終MP3 (`full_1.0x.mp3` 等) を端末にコピーして任意の音楽プレーヤーで再生。
1曲リピート機能で全160語ループが実現できる。
