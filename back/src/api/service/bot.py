import json
import os
import random

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)

from src.consts.line import random_messages
from src.consts.system import root_path
from src.data import LendingRepositoryImpl, UserRepositoryImpl
from src.domain.use_case import LendingUseCase


class BotService:
    def __init__(self):
        self.line_bot_api = LineBotApi(os.environ.get('YOUR_CHANNEL_ACCESS_TOKEN'))
        self.handler = WebhookHandler(os.environ.get('YOUR_CHANNEL_SECRET'))
        self.lending_use_case = LendingUseCase(LendingRepositoryImpl(UserRepositoryImpl()))

        @self.handler.add(MessageEvent, message=TextMessage)
        def handle_message(event: MessageEvent):
            request_text: str = event.message.text
            print(request_text)
            split_request_text = request_text.split()

            if len(split_request_text) is not 2:
                self._response_random(event.reply_token)
                return

            request_message, lending_id = split_request_text

            lending = self.lending_use_case.fetch_lending(lending_id)
            is_confirming_returned = lending.is_confirming_returned
            borrower_id = lending.borrower_id

            if not is_confirming_returned:
                self._response_random(event.reply_token)
                return

            if request_message == 'はい':
                self.line_bot_api.reply_message(event.reply_token, TextSendMessage(text='返ってきてよかったチュン！'))
                self.line_bot_api.push_message(borrower_id, TextSendMessage(text='返してくれてありがとチュン！'))
                self.lending_use_case.register_return_lending(lending_id)
                self.lending_use_case.finish_confirming_returned(lending_id)

            elif request_message == 'いいえ':
                self.line_bot_api.reply_message(
                    event.reply_token, [
                        TextSendMessage(text='悲しいチュン...'),
                        TextSendMessage(text='早く返してって言ってくるチュン！')
                    ]
                )
                self.line_bot_api.push_message(
                    borrower_id,
                    TextSendMessage(
                        text='早く返して欲しいチュン!\n'
                             '（もし既に返してたら申し訳ないチュン...\n'
                             '借りた側に通知解除してって言って欲しいチュン...)'
                    )
                )
                self.lending_use_case.finish_confirming_returned(lending_id)

            else:
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text='「はい」か「いいえ」で答えて欲しいチュン。')
                )

    def _response_random(self, reply_token: str):
        self.line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=random.choice(random_messages))
        )

    def handle_hook(self, body, signature):
        self.handler.handle(body, signature)

    def send_message_for_deadline_lendings(self):
        deadline_lending_list = self.lending_use_case.fetch_deadline_lending_list()

        with open(f"{root_path}/src/api/service/confirm_message.json") as f:
            base_contents = json.load(f)

        for owner_id, lendings in deadline_lending_list.items():
            messages = []

            for lending in lendings:
                self.lending_use_case.start_confirming_returned(lending.id)
                contents = base_contents.copy()
                # コールバックのエンドポイントに送信されるデータの末尾に、空白区切りで貸借りidを追加する
                contents['footer']['contents'][0]['action']['text'] += f" {lending.id}"
                contents['footer']['contents'][1]['action']['text'] += f" {lending.id}"

                messages.append(FlexSendMessage(
                    alt_text=f"{lending.borrower_name}さんに貸した{lending.content}帰ってきたチュン？",
                    contents=contents
                ))

            self.line_bot_api.push_message(owner_id, messages)
