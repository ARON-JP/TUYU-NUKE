import json
import asyncio
import time
import discord
from discord import FFmpegPCMAudio

TOKEN = "Tokenhere"

intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    # サーバー一覧
    print("\nServers:")
    guilds = list(client.guilds)
    for i, g in enumerate(guilds, 1):
        print(f"[{i}] {g.name}")

    g = guilds[int(input("Server> ")) - 1]

    # VC一覧
    print("\nVoice Channels:")
    vcs = g.voice_channels
    for i, c in enumerate(vcs, 1):
        print(f"[{i}] {c.name}")

    vc = vcs[int(input("VC> ")) - 1]

    # テキストチャンネル一覧
    print("\nText Channels:")
    tcs = g.text_channels
    for i, c in enumerate(tcs, 1):
        print(f"[{i}] #{c.name}")

    tc = tcs[int(input("Text> ")) - 1]

    print("\n@everyone")
    voice = await vc.connect()

    print("りくぜ引退ライブ！！！")

    voice.play(
        FFmpegPCMAudio(
            "music/sample.mp3",
            executable="C:\\Users\\kanat\\node_modules\\ffmpeg-static\\ffmpeg.exe"
        )
    )

    # 歌詞読み込み
    with open("lyrics/sample.json", "r", encoding="utf-8") as f:
        lyrics = json.load(f)

    start = time.perf_counter()

    # 歌詞同期
    for line in lyrics:
        while time.perf_counter() - start < line["time"]:
            await asyncio.sleep(0.01)

        await tc.send(
            line["text"],
            allowed_mentions=discord.AllowedMentions(
                everyone=True,
                roles=True,
                users=True
            )
        )

    # 曲終了待ち
    while voice.is_playing():
        await asyncio.sleep(1)

    print("GG Guys...")

    await voice.disconnect()
    await client.close()


client.run(TOKEN)