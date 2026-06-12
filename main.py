import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext


def ts() -> str:
    return datetime.now().strftime('%H:%M:%S')


class TelegramMassMessenger:
    def __init__(
        self,
        message: str,
        proxy: dict = None,
        delay: float = 3.0,
        max_chats: int = None,
        skip_groups: bool = True,
    ):
        self.user_data_dir = "./scrapper_data"
        self.message = message
        self.proxy = proxy or {}
        self.delay = delay
        self.max_chats = max_chats
        self.skip_groups = skip_groups

        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

        self.sent_count = 0
        self.failed_count = 0
        self.processed: set = set()

    async def setup_browser(self):
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            proxy=self.proxy if self.proxy else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
            locale="en-GB",
            timezone_id="Europe/Kiev",
        )
        self.page = await self.context.new_page()
        await self.page.goto("https://web.telegram.org/k/", wait_until="load")
        await self.page.wait_for_timeout(1500)

    async def wait_for_chat_list(self):
        await self.page.locator('#folders-container').wait_for(state='visible', timeout=20000)
        await self.page.wait_for_timeout(800)

    async def get_peer_id(self, chat_el) -> str | None:
        for attr in ('data-peer-id', 'data-peer', 'data-id'):
            val = await chat_el.get_attribute(attr)
            if val:
                return val
        try:
            a = chat_el.locator('a').first
            for attr in ('data-peer-id', 'data-peer', 'data-id'):
                val = await a.get_attribute(attr)
                if val:
                    return val
        except Exception:
            pass
        try:
            return (await chat_el.locator('.peer-title').first.inner_text()).strip()
        except Exception:
            return None

    async def is_group_chat(self, chat_el) -> bool:
        try:
            html = await chat_el.inner_html()
            return any(kw in html for kw in (
                'icon-channel', 'icon-group', 'avatar_with_icon--channel',
                'avatar_with_icon--group', 'is-broadcast',
            ))
        except Exception:
            return False

    async def get_title(self, chat_el) -> str:
        try:
            return (await chat_el.locator('.peer-title').first.inner_text()).strip()
        except Exception:
            return '(unknown)'

    async def send_message(self) -> bool:
        try:
            inp = self.page.locator(
                'div.input-message-input[contenteditable="true"]:not(.input-field-input-fake)'
            ).first
            await inp.wait_for(state='visible', timeout=5000)
            await inp.click()
            await self.page.wait_for_timeout(200)
            await self.page.keyboard.type(self.message, delay=25)
            await self.page.wait_for_timeout(200)
            send_btn = self.page.locator('button.btn-send').first
            await send_btn.wait_for(state='visible', timeout=3000)
            await send_btn.click()
            await self.page.wait_for_timeout(400)
            return True
        except Exception as e:
            print(f"  ⚠️  Ошибка: {e}")
            return False

    async def scroll_chat_list(self):
        try:
            await self.page.locator('.chatlist').first.evaluate(
                'el => el.scrollTop += 600'
            )
            await self.page.wait_for_timeout(600)
        except Exception:
            pass

    async def run(self):
        await self.setup_browser()
        await self.wait_for_chat_list()
        print(f"[{ts()}] Массовая отправка началась, все пизда → \"{self.message}\"")

        stale_scrolls = 0

        while True:
            if self.max_chats and self.sent_count >= self.max_chats:
                break

            chats = self.page.locator('.chatlist-chat')
            count = await chats.count()

            found_new = False
            for i in range(count):
                if self.max_chats and self.sent_count >= self.max_chats:
                    break

                chat = chats.nth(i)
                peer_id = await self.get_peer_id(chat)
                if not peer_id or peer_id in self.processed:
                    continue

                found_new = True
                self.processed.add(peer_id)
                title = await self.get_title(chat)

                if self.skip_groups and await self.is_group_chat(chat):
                    print(f"  ⏭️  Скип групу: {title}")
                    continue

                try:
                    await chat.scroll_into_view_if_needed()
                    await chat.click(timeout=3000)
                    await self.page.wait_for_timeout(500)

                    ok = await self.send_message()
                    if ok:
                        self.sent_count += 1
                        print(f"  ✅ [{self.sent_count}] {title}")
                    else:
                        self.failed_count += 1
                        print(f"  ❌ Ошибка: {title}")

                    await asyncio.sleep(self.delay)
                except Exception as e:
                    print(f"  ❌ Ошибка ({title}): {e}")

            if not found_new:
                if stale_scrolls >= 5:
                    print(f"[{ts()}] Больше чатов нет.")
                    break
                await self.scroll_chat_list()
                stale_scrolls += 1
            else:
                stale_scrolls = 0

        print(f"\n[{ts()}] Done - отправлено: {self.sent_count}, ошибка: {self.failed_count}")
        try:
            await self.context.close()
            await self.playwright.stop()
        except Exception:
            pass


if __name__ == "__main__":
    MESSAGE = "Hello! This is a test message."

    bot = TelegramMassMessenger(
        message=MESSAGE,
        proxy={},
        delay=3.0,       
        max_chats=None,
        skip_groups=False,
    )

    asyncio.run(bot.run())
