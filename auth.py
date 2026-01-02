import asyncio
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

cloud_password = ''
number_phone = ""

proxy = {
        "server": "http://unwinned.com:50100",
        "username": "",
        "password": ""
    }

ua = UserAgent()
chrome_ua = ua.chrome

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
        user_data_dir="./scrapper_data",
        headless=True,
        # proxy = proxy,
        user_agent = chrome_ua,
        viewport={"width": 1800, "height": 950},
        java_script_enabled=True,
        locale="en-US",
        timezone_id="Europe/London")

        page = await browser.new_page()

        await page.goto("https://web.telegram.org/k/")
        
        await page.locator('//*[@id="auth-pages"]/div[2]/div[2]/div[3]/div/div[2]/button').click()
        await page.wait_for_timeout(2000)
        await page.locator('//*[@id="auth-pages"]/div[2]/div[2]/div[2]/div/div[3]/div[2]/div[1]').click()
        await page.wait_for_timeout(5000)
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(number_phone)
        
        await page.wait_for_timeout(2000)
        await page.locator('//*[@id="auth-pages"]/div[2]/div[2]/div[2]/div/div[3]/button[1]').click()
        await page.wait_for_timeout(2000)
        number = str(input("Введи код с телеги, быдло: "))
        await page.locator('//*[@id="auth-pages"]/div[2]/div[2]/div[4]/div/div[3]/div/input').fill(number)
        await page.wait_for_timeout(2000)
        await page.locator('//*[@id="auth-pages"]/div[2]/div[2]/div[5]/div/div[2]/div/input[2]').click()
        await page.type('//*[@id="auth-pages"]/div[2]/div[2]/div[5]/div/div[2]/div/input[2]', cloud_password, delay=100)
        await page.wait_for_timeout(2000)
        await page.locator('//*[@id="auth-pages"]/div[2]/div[2]/div[5]/div/div[2]/button').click()
        await page.wait_for_timeout(10000)

        print("enter done, session will be saved")

        await browser.close()

asyncio.run(main())
