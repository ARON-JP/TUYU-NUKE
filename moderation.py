import os
import json
import asyncio
from datetime import timedelta

import discord

# スクリプト自身の場所を基準にする（どこから実行しても動くように）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve(path):
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


# 設定読み込み（TOKEN は config.json から）
with open(resolve("config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["token"]

# 「怪しいアカウント」判定の閾値（日数）。config.json で上書き可能。
NEW_ACCOUNT_DAYS = config.get("new_account_days", 7)   # 作成からこの日数以内＝新規垢
NEW_JOIN_DAYS = config.get("new_join_days", 2)         # 参加からこの日数以内＝新規参加

# メンバー列挙・BANにはMembers Intent（特権インテント）が必要。
# Developer Portal の Bot 設定で "Server Members Intent" を ON にしておくこと。
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


# ---- 入力ヘルパ -----------------------------------------------------------
# input() はブロッキングなので別スレッドで回し、Botのハートビートを止めない。

async def ask(prompt):
    return (await asyncio.to_thread(input, prompt)).strip()


async def pick(label, items, fmt, allow_back=False):
    """番号入力で1件選ばせる共通メニュー。allow_back=True なら 0 で None を返す。"""
    print(f"\n{label}:")
    if allow_back:
        print("[0] 戻る")
    for i, it in enumerate(items, 1):
        print(f"[{i}] {fmt(it)}")
    while True:
        raw = await ask(f"{label}> ")
        if not raw.isdigit():
            print("数字を入力してください")
            continue
        n = int(raw)
        if allow_back and n == 0:
            return None
        if 1 <= n <= len(items):
            return items[n - 1]
        print("範囲外です")


async def confirm(prompt):
    return (await ask(f"{prompt} [y/N] > ")).lower() in ("y", "yes")


# ---- 問題検出 -------------------------------------------------------------

def diagnose(member):
    """メンバーの「問題点」を文字列リストで返す。空なら特に問題なし。"""
    now = discord.utils.utcnow()
    flags = []

    age_days = (now - member.created_at).days
    if age_days <= NEW_ACCOUNT_DAYS:
        flags.append(f"新規垢({age_days}日)")

    if member.joined_at is not None:
        join_days = (now - member.joined_at).days
        if join_days <= NEW_JOIN_DAYS:
            flags.append(f"参加直後({join_days}日)")

    # @everyone 以外のロールが無い
    if len(member.roles) <= 1:
        flags.append("ロール無し")

    # デフォルトアイコンのまま
    if member.avatar is None:
        flags.append("アイコン未設定")

    # メンバーシップ審査が未完了
    if getattr(member, "pending", False):
        flags.append("審査未完了")

    return flags


# ---- 各種アクション -------------------------------------------------------

async def do_ban(guild, member):
    if not await confirm(f"本当に {member} を BAN しますか？"):
        print("中止しました")
        return
    days = await ask("直近メッセージ削除日数 (0-7, 既定0) > ")
    delete_days = int(days) if days.isdigit() and 0 <= int(days) <= 7 else 0
    reason = await ask("理由 > ") or "管理ツールによるBAN"
    try:
        await guild.ban(member, reason=reason,
                        delete_message_days=delete_days)
        print(f"BAN しました: {member}")
    except discord.Forbidden:
        print("権限不足でBANできません（Botのロール位置・権限を確認）")
    except Exception as e:
        print(f"失敗: {e}")


async def do_kick(guild, member):
    if not await confirm(f"本当に {member} をキックしますか？"):
        print("中止しました")
        return
    reason = await ask("理由 > ") or "管理ツールによるキック"
    try:
        await member.kick(reason=reason)
        print(f"キックしました: {member}")
    except discord.Forbidden:
        print("権限不足でキックできません")
    except Exception as e:
        print(f"失敗: {e}")


async def do_timeout(guild, member):
    mins = await ask("タイムアウト時間(分) > ")
    if not mins.isdigit() or int(mins) <= 0:
        print("中止しました")
        return
    reason = await ask("理由 > ") or "管理ツールによるタイムアウト"
    try:
        await member.timeout(timedelta(minutes=int(mins)), reason=reason)
        print(f"{mins}分間タイムアウトしました: {member}")
    except discord.Forbidden:
        print("権限不足でタイムアウトできません")
    except Exception as e:
        print(f"失敗: {e}")


async def member_actions(guild, member):
    """1人のメンバーに対する対処メニュー。"""
    while True:
        flags = diagnose(member)
        print(f"\n--- {member.display_name} ({member}) ---")
        print(f"  ID       : {member.id}")
        print(f"  作成      : {member.created_at:%Y-%m-%d}")
        if member.joined_at:
            print(f"  参加      : {member.joined_at:%Y-%m-%d}")
        print(f"  ロール    : {', '.join(r.name for r in member.roles[1:]) or 'なし'}")
        print(f"  検出      : {', '.join(flags) or '特になし'}")

        action = await pick(
            "対処",
            ["BAN", "キック", "タイムアウト"],
            lambda x: x,
            allow_back=True,
        )
        if action is None:
            return
        if action == "BAN":
            await do_ban(guild, member)
            return
        if action == "キック":
            await do_kick(guild, member)
            return
        if action == "タイムアウト":
            await do_timeout(guild, member)


async def scan_problems(guild):
    """問題のあるメンバーを検出して一覧表示し、選んで対処させる。"""
    flagged = [(m, diagnose(m)) for m in guild.members]
    flagged = [(m, f) for m, f in flagged if f and not m.bot]
    # 検出数が多い順に並べる
    flagged.sort(key=lambda mf: len(mf[1]), reverse=True)

    if not flagged:
        print("\n問題のあるメンバーは検出されませんでした")
        return

    print(f"\n=> {len(flagged)} 人のメンバーに問題を検出しました")
    while True:
        chosen = await pick(
            "問題メンバー",
            flagged,
            lambda mf: f"{mf[0].display_name} ({mf[0]}) … {', '.join(mf[1])}",
            allow_back=True,
        )
        if chosen is None:
            return
        await member_actions(guild, chosen[0])


async def browse_all(guild):
    """全メンバーから選んで対処する。"""
    members = sorted((m for m in guild.members if not m.bot),
                     key=lambda m: m.display_name.lower())
    while True:
        chosen = await pick(
            "全メンバー",
            members,
            lambda m: f"{m.display_name} ({m})",
            allow_back=True,
        )
        if chosen is None:
            return
        await member_actions(guild, chosen)


async def manage_bans(guild):
    """既存のBANを確認・解除する。"""
    bans = [entry async for entry in guild.bans()]
    if not bans:
        print("\nBANされているユーザーはいません")
        return
    while True:
        entry = await pick(
            "BAN一覧（選ぶと解除）",
            bans,
            lambda e: f"{e.user} … {e.reason or '理由なし'}",
            allow_back=True,
        )
        if entry is None:
            return
        if await confirm(f"{entry.user} のBANを解除しますか？"):
            try:
                await guild.unban(entry.user, reason="管理ツールによる解除")
                bans.remove(entry)
                print(f"解除しました: {entry.user}")
            except Exception as e:
                print(f"失敗: {e}")


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    g = await pick("Server", list(client.guilds), lambda x: x.name)

    # Botに必要権限があるか軽くチェック
    perms = g.me.guild_permissions
    if not perms.ban_members:
        print("⚠ このBotには Ban Members 権限がありません（BANできません）")
    if not perms.kick_members:
        print("⚠ このBotには Kick Members 権限がありません（キックできません）")

    while True:
        choice = await pick(
            f"メニュー（{g.name}）",
            [
                "問題のあるメンバーを検出",
                "全メンバーから選ぶ",
                "BAN一覧の確認・解除",
            ],
            lambda x: x,
            allow_back=True,
        )
        if choice is None:
            break
        if choice == "問題のあるメンバーを検出":
            await scan_problems(g)
        elif choice == "全メンバーから選ぶ":
            await browse_all(g)
        elif choice == "BAN一覧の確認・解除":
            await manage_bans(g)

    print("終了します")
    await client.close()


client.run(TOKEN)
