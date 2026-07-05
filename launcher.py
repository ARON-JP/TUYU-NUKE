import os
import json
import asyncio
import time
import discord
from discord import FFmpegPCMAudio

# スクリプト自身の場所を基準にする（どこから実行しても動くように）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve(path):
    """相対パスをスクリプトの場所基準で絶対パスに変換。"""
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


# 設定読み込み（TOKEN等は config.json に外出し）
with open(resolve("config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["token"]
FFMPEG = resolve(config.get("ffmpeg", "ffmpeg.exe"))
MUSIC = resolve(config.get("music", "music/sample.mp3"))
LYRICS = resolve(config.get("lyrics", "lyrics/sample.json"))
VC_STATUS = config.get("vc_status", "いつかオトナになれるといいね。")

# 起動時のモード選択
#   1) リハーサル … 歌詞のタイミング確認用。通知オフ・終了処理なし
#   2) 本番       … VCステータス設定・@everyone通知・終了後にCh非表示＆VCキック
print("Mode:")
print("[1] リハーサル（歌詞テスト）")
print("[2] 本番")
PRODUCTION = input("Mode> ").strip() == "2"
print("=> 本番モード" if PRODUCTION else "=> リハーサルモード")

intents = discord.Intents.default()
client = discord.Client(intents=intents)


def pick(label, items, fmt):
    """番号入力で1件選ばせる共通メニュー。"""
    print(f"\n{label}:")
    for i, it in enumerate(items, 1):
        print(f"[{i}] {fmt(it)}")
    return items[int(input(f"{label}> ")) - 1]


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    g = pick("Server", list(client.guilds), lambda x: x.name)
    vc = pick("VC", g.voice_channels, lambda x: x.name)
    tc = pick("Text", g.text_channels, lambda x: f"#{x.name}")

    voice = await vc.connect()

    # VCステータス（本番のみ）
    if PRODUCTION:
        try:
            await client.http.edit_voice_channel_status(VC_STATUS, channel_id=vc.id)
        except Exception as e:
            print(f"VCステータス設定に失敗: {e}")

        # 選択したテキストCh・VC以外を、あらかじめ管理者以外に非表示にする
        for ch in g.channels:
            if ch == tc or ch == vc:
                continue
            try:
                overwrite = ch.overwrites_for(g.default_role)
                overwrite.view_channel = False
                await ch.set_permissions(
                    g.default_role,
                    overwrite=overwrite,
                    reason="ライブ開始",
                )
            except Exception as e:
                print(f"{ch.name} の非表示に失敗: {e}")

    print("りくぜ引退ライブ！！！" if PRODUCTION else "リハーサル開始")

    voice.play(FFmpegPCMAudio(MUSIC, executable=FFMPEG))

    # 歌詞読み込み
    with open(LYRICS, "r", encoding="utf-8") as f:
        lyrics = json.load(f)

    # 本番のみ @everyone 等の通知を有効化（リハーサルでは鳴らさない）
    mentions = discord.AllowedMentions(
        everyone=PRODUCTION,
        roles=PRODUCTION,
        users=PRODUCTION,
    )

    start = time.perf_counter()

    # 歌詞同期
    for line in lyrics:
        while time.perf_counter() - start < line["time"]:
            await asyncio.sleep(0.01)
        await tc.send(line["text"], allowed_mentions=mentions)

    # 歌詞JSONが最後まで行ったら（曲の終了は待たない）処理（本番のみ）
    if PRODUCTION:
        # テキストチャンネルとVCを管理者以外には非表示にする
        for ch in (tc, vc):
            try:
                overwrite = ch.overwrites_for(g.default_role)
                overwrite.view_channel = False
                await ch.set_permissions(
                    g.default_role,
                    overwrite=overwrite,
                    reason="ライブ終了",
                )
            except Exception as e:
                print(f"{ch.name} の非表示に失敗: {e}")

        # VCから全員キック（切断）
        for member in list(vc.members):
            if member == client.user:
                continue
            try:
                await member.move_to(None, reason="ライブ終了")
            except Exception as e:
                print(f"{member} のキックに失敗: {e}")

    print("GG Guys...")

    await voice.disconnect()
    await client.close()


client.run(TOKEN)
