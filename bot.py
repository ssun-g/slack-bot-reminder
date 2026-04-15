import os
import re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
REACTION_EMOJI = os.environ.get("REACTION_EMOJI", "white_check_mark")
REMIND_TYPE = os.environ.get("REMIND_TYPE", "dm")  # "dm" or "channel"

client = WebClient(token=SLACK_BOT_TOKEN)


def get_latest_message_with_mentions(channel_id: str) -> tuple[dict | None, list[str]]:
    """채널의 최신 메시지 중 멘션이 포함된 것을 반환."""
    try:
        response = client.conversations_history(channel=channel_id, limit=20)
    except SlackApiError as e:
        print(f"[ERROR] 채널 메시지 조회 실패: {e.response['error']}")
        return None, []

    for msg in response["messages"]:
        text = msg.get("text", "")
        # <@USERID> 또는 <@USERID|displayname> 패턴
        mentions = re.findall(r"<@([A-Z0-9]+)(?:\|[^>]*)?>", text)
        if mentions:
            return msg, mentions

    return None, []


def get_reacted_users(channel_id: str, message_ts: str, emoji: str) -> set[str]:
    """특정 메시지에서 특정 이모지를 누른 유저 ID 집합 반환."""
    try:
        response = client.reactions_get(channel=channel_id, timestamp=message_ts)
    except SlackApiError as e:
        print(f"[ERROR] 리액션 조회 실패: {e.response['error']}")
        return set()

    reactions = response["message"].get("reactions", [])
    for reaction in reactions:
        if reaction["name"] == emoji:
            return set(reaction["users"])

    return set()


def get_user_display_name(user_id: str) -> str:
    """유저 ID로 표시 이름 조회."""
    try:
        response = client.users_info(user=user_id)
        profile = response["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name", user_id)
    except SlackApiError:
        return user_id


def send_reminder_dm(user_id: str, channel_id: str, message_ts: str) -> None:
    """유저에게 DM으로 리마인드 전송."""
    message_link = f"https://slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"
    try:
        client.chat_postMessage(
            channel=user_id,
            text=(
                f"안녕하세요! :wave:\n"
                f"<#{channel_id}> 채널의 <{message_link}|메시지>에 "
                f":{REACTION_EMOJI}: 리액션을 아직 달지 않으셨어요.\n"
                f"확인 후 리액션 부탁드립니다! :pray:"
            ),
        )
        print(f"  → DM 전송 완료: {user_id}")
    except SlackApiError as e:
        print(f"  → DM 전송 실패 ({user_id}): {e.response['error']}")


def send_reminder_channel(channel_id: str, pending_user_ids: list[str], message_ts: str) -> None:
    """채널 스레드에 리마인드 메시지 전송."""
    mentions = " ".join(f"<@{uid}>" for uid in pending_user_ids)
    try:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=(
                f"{mentions}\n"
                f"위 메시지에 :{REACTION_EMOJI}: 리액션을 아직 달지 않으셨어요. "
                f"확인 후 리액션 부탁드립니다! :pray:"
            ),
        )
        print(f"  → 채널 스레드 리마인드 전송 완료")
    except SlackApiError as e:
        print(f"  → 채널 리마인드 전송 실패: {e.response['error']}")


def main() -> None:
    print(f"[INFO] 채널 {CHANNEL_ID} 확인 중...")

    # 1. 멘션이 포함된 최신 메시지 조회
    message, mentioned_users = get_latest_message_with_mentions(CHANNEL_ID)

    if not message:
        print("[INFO] 멘션이 포함된 메시지를 찾지 못했습니다.")
        return

    print(f"[INFO] 대상 메시지: {message['text'][:80].strip()}...")
    print(f"[INFO] 멘션된 유저: {mentioned_users}")

    # 2. 해당 메시지의 리액션 누른 유저 조회
    reacted_users = get_reacted_users(CHANNEL_ID, message["ts"], REACTION_EMOJI)
    print(f"[INFO] :{REACTION_EMOJI}: 리액션 누른 유저: {reacted_users or '없음'}")

    # 3. 리액션을 누르지 않은 멘션 유저 필터링
    pending_users = [uid for uid in mentioned_users if uid not in reacted_users]

    if not pending_users:
        print("[INFO] 모든 멘션된 유저가 리액션을 완료했습니다.")
        return

    print(f"[INFO] 리마인드 대상 ({len(pending_users)}명): {pending_users}")

    # 4. 리마인드 전송
    if REMIND_TYPE == "channel":
        send_reminder_channel(CHANNEL_ID, pending_users, message["ts"])
    else:
        for user_id in pending_users:
            name = get_user_display_name(user_id)
            print(f"  리마인드 전송 중: {name} ({user_id})")
            send_reminder_dm(user_id, CHANNEL_ID, message["ts"])

    print("[INFO] 완료")


if __name__ == "__main__":
    main()
