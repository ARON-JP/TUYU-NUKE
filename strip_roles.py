import os
import json
import discord

# スクリプト自身の場所を基準にする（どこから実行しても動くように）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve(path):
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


# 設定読み込み（TOKEN は config.json から）
with open(resolve("config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["token"]

# 全メンバー列挙にはMembers Intent（特権インテント）が必要
intents = discord.Intents.default()
intents.members = True
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

    members = sorted(g.members, key=lambda m: m.display_name.lower())
    keep = pick("User (このユーザーは残す)", members,
                lambda m: f"{m.display_name} ({m})")

    print(f"\n=> {keep.display_name} 以外の全員からロールを剥奪します")

    me = g.me
    for member in members:
        if member == keep or member == me:
            continue

        # 剥奪できるロールだけ抽出：
        #   @everyone（既定ロール）・bot連携等の管理ロール・bot自身より上位のロールは除外
        removable = [
            r for r in member.roles
            if not r.is_default() and not r.managed and r < me.top_role
        ]
        if not removable:
            continue

        try:
            await member.remove_roles(*removable, reason="ライブ終了：ロール剥奪")
            print(f"剥奪: {member.display_name} ({len(removable)}個)")
        except Exception as e:
            print(f"失敗: {member.display_name} -> {e}")

    print("完了")
    await client.close()


client.run(TOKEN)
