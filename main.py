import asyncio
import re
import time as tme
from datetime import datetime, time, timedelta
from playwright.async_api import async_playwright, Page, BrowserContext


class TelegramGiftBot:
    def __init__(self, user_data_dir, proxy, stars_limit=10000, check_interval=2):
        self.user_data_dir = user_data_dir
        self.proxy = proxy
        self.stars_balance = 0
        self.stars_limit = stars_limit
        self.check_interval = check_interval
        self.mil_sec_wait = 475

        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

        self.gifts_selector = "div._gridItem_1shbt_20"
        self.suitable_gifts = []
        self.gifts_updated_at: datetime | None = None

        self.page_lock = asyncio.Lock()


    def _parse_int_from_text(self, txt: str) -> int | None:
        if not txt:
            return None
        m = re.search(r"(\d[\d\.\,\s\u202f]*)", txt)
        if not m:
            return None
        digits = re.sub(r"\D", "", m.group(1))
        return int(digits) if digits else None


    async def close_all_popups(self, max_loops: int = 6):
        try:
            for _ in range(max_loops):
                active = self.page.locator(
                    ".popup.active, .modal, .popup-send-gift.active, .popup-star-gift-info.active"
                )
                visible = False
                count = await active.count()
                for i in range(count):
                    if await active.nth(i).is_visible():
                        visible = True
                        break

                if not visible:
                    return

                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(200)
        except Exception as e:
            print(f"⚠️ Ошибка в close_all_popups: {e}")


    async def proceed_to_telegram(self):
        if "/k/" not in self.page.url:
            await self.page.goto("https://web.telegram.org/k/", wait_until="load")
        else:
            await self.page.wait_for_load_state("load")
        await self.page.wait_for_timeout(400)
        await self.page.locator('xpath=//*[@id="folders-container"]').wait_for(
            state="visible", timeout=15000
        )

    async def proceed_to_chat(self):
        await self.close_all_popups()
        first_chat = self.page.locator(
            'xpath=//*[@id="folders-container"]/div[1]/div[2]/ul/a[1]'
        ).first
        await first_chat.wait_for(state="visible", timeout=5000)
        try:
            await first_chat.scroll_into_view_if_needed()
        except Exception:
            pass
        await first_chat.click(timeout=5000)
        await self.page.wait_for_timeout(self.mil_sec_wait)


    async def setup_browser(self):
        if self.playwright is None:
            self.playwright = await async_playwright().start()

        try:
            if self.context:
                await self.context.close()
        except:
            pass

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=True,
            proxy=self.proxy,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1200, "height": 700},
            java_script_enabled=True,
            locale="en-GB",
            timezone_id="Europe/Kiev",
        )
        self.page = await self.context.new_page()
        await self.page.goto("https://web.telegram.org/k/", wait_until="load")
        await self.page.wait_for_timeout(800)

    async def restart_browser(self, reopen_gifts: bool = True):
        print(f"♻️ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Перезапуск браузера после краша/разрыва")
        try:
            if self.context:
                await self.context.close()
        except:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        self.context = None
        self.page = None
        self.playwright = None

        await self.setup_browser()
        try:
            await self.proceed_to_telegram()
            await self.close_all_popups()
            await self.proceed_to_chat()
            if reopen_gifts:
                await self.open_gift_screen()
        except Exception as e:
            print(f"⚠️ Ошибка при восстановлении сессии после рестарта: {e}")

    async def safe_action(self, func, *args, **kwargs):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                text = str(e)
                transient = (
                    "Connection closed" in text
                    or "pipe closed" in text
                    or "Target page" in text
                    or "Connection reset" in text
                    or "Target crashed" in text
                    or "Target closed" in text
                )
                if transient:
                    print(f"⚠️ Попытка {attempt}/{max_retries} — восстановление после ошибки: {e}")
                    await self.restart_browser(reopen_gifts=True)
                    continue
                raise
        print("❌ Лимит попыток safe_action исчерпан")
        return None


    async def update_balance(self):
        async with self.page_lock:
            try:
                await self.proceed_to_telegram()
                await self.page.wait_for_timeout(800)

                await self.proceed_to_chat()

                menu_btn = self.page.locator(
                    'xpath=//*[@id="column-center"]/div[1]/div/div[2]/div[1]/div[2]/button[8]'
                )
                await menu_btn.click()
                await self.page.wait_for_timeout(400)

                stars_btn = self.page.locator(
                    'xpath=//*[@id="column-center"]/div[1]/div/div[2]/div[1]/div[2]/button[8]/div[3]/div[3]'
                )
                await stars_btn.click()
                await self.page.wait_for_timeout(600)

                selectors = [
                    "xpath=/html/body/div[8]/div/div[2]/span/b",
                    "xpath=/html/body/div[last()]/div/div[2]/span/b",
                    "xpath=//div[contains(@class,'popup') or contains(@class,'modal')][last()]//span//b",
                ]
                text = None
                for sel in selectors:
                    loc = self.page.locator(sel)
                    try:
                        await loc.first.wait_for(state="visible", timeout=2000)
                        t = await loc.first.inner_text()
                        if self._parse_int_from_text(t) is not None:
                            text = t
                            break
                    except Exception:
                        continue

                value = self._parse_int_from_text(text or "")
                if value is None:
                    raise RuntimeError("Не удалось прочитать баланс")

                self.stars_balance = value
                print(f"💰 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Баланс: {self.stars_balance}")

                await self.page.press("body", "Escape")
                await self.page.wait_for_timeout(200)
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ошибка update_balance: {e}")

    async def open_gift_screen(self) -> bool:
        for attempt in (1, 2):
            try:
                await self.close_all_popups()
    
                menu_btn = self.page.locator(
                    'xpath=//*[@id="column-center"]/div[1]/div/div[2]/div[1]/div[2]/button[8]'
                )
                await menu_btn.wait_for(state="visible", timeout=15000)
                await menu_btn.click(timeout=5000)
                await self.page.wait_for_timeout(self.mil_sec_wait)
    
                stars_btn = self.page.locator(
                    'xpath=//*[@id="column-center"]/div[1]/div/div[2]/div[1]/div[2]/button[8]/div[3]/div[3]'
                )
                await stars_btn.wait_for(state="visible", timeout=10000)
                await stars_btn.click(timeout=5000)
    
                await self.page.locator(self.gifts_selector).first.wait_for(
                    state="visible", timeout=15000
                )
                return True
            except Exception as e:
                print(f"Ошибка open_gift_screen (попытка {attempt}/2): {e}")
                if attempt == 1:
                    try:
                        await self.page.reload(wait_until="load")
                        await self.proceed_to_chat()
                        await self.page.wait_for_timeout(600)
                    except Exception as e2:
                        print(f"Reload не удался: {e2}")
                else:
                    return False


    async def refresh_suitable_gifts(self, print_stats: bool = True):
        try:
            gifts = self.page.locator(self.gifts_selector)
            count = await gifts.count()

            premium_count = 0
            limited_count = 0
            sold_out_count = 0
            suitable_gifts = []
            prices = []

            for i in range(count):
                gift = gifts.nth(i)
                text = await gift.inner_text()
                price_match = re.search(r"\d+", text)
                if not price_match:
                    continue

                price = int(price_match.group())
                prices.append(price)

                low = text.lower()
                is_premium = "premium" in low
                is_limited = "limited" in low
                is_sold_out = "sold out" in low

                if is_premium:
                    premium_count += 1
                if is_limited:
                    limited_count += 1
                if is_sold_out:
                    sold_out_count += 1

                if price <= self.stars_limit and (is_premium or is_limited):
                    suitable_gifts.append((gift, price))

            suitable_gifts.sort(key=lambda x: x[1], reverse=True)

            self.suitable_gifts = suitable_gifts
            self.gifts_updated_at = datetime.now()

            if print_stats:
                checkkk = "✅" if prices else "❌"
                print(
                    f"📊 [{self.gifts_updated_at.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"Статистика: premium={premium_count}, limited={limited_count}, sold_out={sold_out_count}, проверка={checkkk}"
                )

            return suitable_gifts
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ошибка при обновлении списка подарков: {e}")
            self.suitable_gifts = []
            return []

    async def buy_gift(self, gift, price):
        if price > self.stars_balance:
            print(f"⛔ Недостаточно звёзд для {price}")
            return False

        for attempt in range(1, 2):
            try:
                await gift.click()
                send_btns = await self.page.locator("button.popup-send-gift-form-send").all()
                for btn in send_btns:
                    if str(price) in (await btn.inner_text()):
                        await btn.click()
                        self.stars_balance -= price
                        print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Куплен подарок за {price}")
                        return True
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ошибка покупки (попытка {attempt}/1): {e}")
        print(f"⚠️ Подарок {price} звёзд уже куплен/недоступен")
        return False


    async def check_new_gifts(self):
        async with self.page_lock:
            start = tme.time()
            try:
                await self.safe_action(self.proceed_to_telegram)
                await self.proceed_to_chat()
                await self.close_all_popups()

                opened = await self.safe_action(self.open_gift_screen)
                if not opened:
                    print("⚠️ Экран подарков не открылся, ждём до следующей проверки")
                    return

                await self.refresh_suitable_gifts(print_stats=True)

                while self.suitable_gifts and self.stars_balance > 0:
                    bought_any = False
                    for gift, price in self.suitable_gifts:
                        if price <= self.stars_balance:
                            print(f"🎁 Попытка купить: {price} звёзд")
                            bought = await self.buy_gift(gift, price)
                            if bought:
                                reopened = await self.safe_action(self.open_gift_screen)
                                if not reopened:
                                    print("⚠️ Не смогли переоткрыть экран после покупки")
                                    return
                                await self.refresh_suitable_gifts(print_stats=False)
                                bought_any = True
                                break
                    if not bought_any:
                        break
            except Exception as e:
                print(f"❌ Ошибка в check_new_gifts: {e}")
                await self.restart_browser(reopen_gifts=True)
            finally:
                elapsed = tme.time() - start
                print(f"⏱ check_new_gifts занял {elapsed:.2f}с")

                if elapsed > 15:
                    print(f"♻️ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"Перезапуск Playwright (elapsed={elapsed:.2f}с)")
                    await self.restart_browser(reopen_gifts=True)


    async def scheduler(self):
        while True:
            now = datetime.now()
            target = datetime.combine(now.date(), time(9, 0))
            if now > target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            await self.update_balance()


    async def gift_checker(self):
        while True:
            try:
                await self.check_new_gifts()
            except BaseException as e:
                print(f"❌ Критическая ошибка в gift_checker: {e!r} — перезапускаю браузер")
                try:
                    await self.restart_browser(reopen_gifts=True)
                except Exception as e2:
                    print(f"❌ Ошибка при restart_browser из gift_checker: {e2!r}")
            await asyncio.sleep(self.check_interval)


    async def run(self):
        await self.setup_browser()
        await self.update_balance()
        asyncio.create_task(self.scheduler())
        await self.gift_checker()


if __name__ == "__main__":
    proxy_settings = {}

    while True:
        try:
            bot = TelegramGiftBot(user_data_dir="./data", proxy=proxy_settings)
            asyncio.run(bot.run())
        except BaseException as e:
            print(f"💥 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Процесс упал: {e!r}. Перезапуск через 1с…")
            try:
                tme.sleep(1)
            except Exception:
                pass
            continue

