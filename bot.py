import os
import re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

client = WebClient(token=SLACK_BOT_TOKEN)


def get_channel_members(channel_id: str) -> list[str]:
    """채널의 모든 멤버 ID 목록 반환."""
    try:
        response = client.conversations_members(channel=channel_id)
        return response["members"]
    except SlackApiError as e:
        print(f"[ERROR] 채널 멤버 조회 실패: {e.response['error']}")
        return []


def get_bot_user_id() -> str | None:
    """봇 자신의 유저 ID 반환."""
    try:
        response = client.auth_test()
        return response["user_id"]
    except SlackApiError:
        return None


def get_latest_message_with_mentions(channel_id: str) -> tuple[dict | None, list[str], bool]:
    """
    채널의 최신 메시지 중 멘션이 포함된 것을 반환.
    Returns: (message, mentioned_user_ids, is_channel_mention)
    """
    try:
        response = client.conversations_history(channel=channel_id, limit=20)
    except SlackApiError as e:
        print(f"[ERROR] 채널 메시지 조회 실패: {e.response['error']}")
        return None, [], False

    for msg in response["messages"]:
        # 앱/봇이 보낸 메시지는 제외
        if msg.get("bot_id") or msg.get("subtype") == "bot_message":
            continue

        text = msg.get("text", "")

        # @channel 또는 @here 체크
        if "<!channel>" in text or "<!here>" in text:
            return msg, [], True

        # <@USERID> 또는 <@USERID|displayname> 패턴
        mentions = re.findall(r"<@([A-Z0-9]+)(?:\|[^>]*)?>", text)
        if mentions:
            return msg, mentions, False

    return None, [], False


def get_reacted_users(channel_id: str, message_ts: str) -> set[str]:
    """특정 메시지에 리액션을 누른 모든 유저 ID 집합 반환."""
    try:
        response = client.reactions_get(channel=channel_id, timestamp=message_ts)
    except SlackApiError as e:
        print(f"[ERROR] 리액션 조회 실패: {e.response['error']}")
        return set()

    reactions = response["message"].get("reactions", [])

    # 모든 리액션의 유저를 합집합으로
    all_users = set()
    for reaction in reactions:
        all_users.update(reaction["users"])

    return all_users


def send_reminder(channel_id: str, pending_user_ids: list[str], message_ts: str) -> None:
    """원본 메시지 스레드에 미완료 유저를 멘션하여 리마인드 전송."""
    mentions = " ".join(f"<@{uid}>" for uid in pending_user_ids)
    try:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=(
                f"{mentions}\n"
                f"위 메시지에 리액션을 아직 달지 않으셨어요. 확인 후 리액션 부탁드립니다! :pray:"
            ),
        )
        print(f"  → 스레드 리마인드 전송 완료 ({len(pending_user_ids)}명 멘션)")
    except SlackApiError as e:
        print(f"  → 리마인드 전송 실패: {e.response['error']}")


def main() -> None:
    print(f"[INFO] 채널 {CHANNEL_ID} 확인 중...")

    # 1. 멘션이 포함된 최신 메시지 조회
    message, mentioned_users, is_channel_mention = get_latest_message_with_mentions(CHANNEL_ID)

    if not message:
        print("[INFO] 멘션이 포함된 메시지를 찾지 못했습니다.")
        return

    print(f"[INFO] 대상 메시지: {message['text'][:80].strip()}...")

    # 2. @channel/@here인 경우 채널 전체 멤버 조회
    if is_channel_mention:
        print("[INFO] @channel/@here 멘션 감지 → 채널 멤버 전체 조회")
        mentioned_users = get_channel_members(CHANNEL_ID)

        # 메시지 작성자는 제외 (본인이 올린 공지에 본인이 리액션 안 해도 됨)
        author_id = message.get("user")
        if author_id and author_id in mentioned_users:
            mentioned_users.remove(author_id)

        # 봇 자신도 제외
        bot_id = get_bot_user_id()
        if bot_id and bot_id in mentioned_users:
            mentioned_users.remove(bot_id)

    print(f"[INFO] 대상 유저 ({len(mentioned_users)}명): {mentioned_users}")

    # 3. 해당 메시지의 리액션 누른 유저 조회 (모든 이모지)
    reacted_users = get_reacted_users(CHANNEL_ID, message["ts"])
    print(f"[INFO] 리액션 누른 유저: {reacted_users or '없음'}")

    # 4. 리액션을 누르지 않은 멘션 유저 필터링
    pending_users = [uid for uid in mentioned_users if uid not in reacted_users]

    if not pending_users:
        print("[INFO] 모든 멘션된 유저가 리액션을 완료했습니다.")
        return

    print(f"[INFO] 리마인드 대상 ({len(pending_users)}명): {pending_users}")

    # 5. 원본 메시지 스레드에 리마인드 전송
    send_reminder(CHANNEL_ID, pending_users, message["ts"])

    print("[INFO] 완료")


if __name__ == "__main__":
    main()
