import logging
from rest_framework.decorators import action
from rest_framework.response import Response
from media_upload.utils.base_views import BaseViewSet

from media_upload.utils.comm import set_init_script
from .models import XiaoHongShuVideo
from .serializers import XiaoHongShuVideoSerializer
from playwright.async_api import Playwright, async_playwright, Page
import os
from playwright.sync_api import sync_playwright
import time
import asyncio


logger = logging.getLogger("upload")



async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.xiaohongshu.com/creator-micro/content/upload")
        try:
            await page.wait_for_url("https://creator.xiaohongshu.com/creator-micro/content/upload", timeout=5000)
        except:
            print("[+] 等待5秒 cookie 失效")
            await context.close()
            await browser.close()
            return False
        # 2024.06.17 抖音创作者中心改版
        if await page.get_by_text('手机号登录').count() or await page.get_by_text('扫码登录').count():
            print("[+] 等待5秒 cookie 失效")
            return False
        else:
            print("[+] cookie 有效")
            return True


async def xiaohongshu_setup(account_file, handle=False):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            # Todo alert message
            return False
        await xiaohongshu_cookie_gen(account_file)
    return True


async def xiaohongshu_cookie_gen(account_file):
    async with async_playwright() as playwright:
        options = {
            'headless': False
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


class VideoViewSet(BaseViewSet):
    serializer_class = XiaoHongShuVideoSerializer
    queryset = XiaoHongShuVideo.objects.all()
        # self.title = title  # 视频标题
        # self.file_path = file_path
        # self.tags = tags
        # self.publish_date = publish_date
        # self.account_file = account_file
        # self.date_format = '%Y年%m月%d日 %H:%M'
        # self.local_executable_path = LOCAL_CHROME_PATH
        # self.thumbnail_path = thumbnail_path
        # self.browser = None

    @staticmethod
    def set_schedule_time(page, publish_date):
        # 点击 "定时发布" 复选框
        label_element = page.locator("label:has-text('定时发布')")
        label_element.click()
        time.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        time.sleep(1)
        page.locator('.el-input__inner[placeholder="选择日期和时间"]').click()
        page.keyboard.press("Control+A")
        page.keyboard.type(str(publish_date_hour))
        page.keyboard.press("Enter")
        time.sleep(1)

    def handle_upload_error(self, page):
        page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request, *args, **kwargs):
        account_file = request.data.get("account_file")
        title = request.data.get("title", "")
        tags = request.data.get("tags", [])
        publish_date = request.data.get("publish_date")
        file_path = request.data.get("file_path", "")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                storage_state=f"{account_file}"
            )

            # 如果有初始化脚本逻辑，这里要改成同步版本
            context = set_init_script(context)

            page = context.new_page()
            page.goto("https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")
            page.wait_for_url("https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")

            # 上传视频
            page.locator("div[class^='upload-content'] input[class='upload-input']").set_input_files(file_path)

            # 等待上传完成
            while True:
                try:
                    upload_input = page.wait_for_selector('input.upload-input', timeout=3000)
                    preview_new = upload_input.query_selector(
                        'xpath=following-sibling::div[contains(@class, "preview-new")]')
                    if preview_new:
                        stage_elements = preview_new.query_selector_all('div.stage')
                        upload_success = False
                        for stage in stage_elements:
                            text_content = page.evaluate('(element) => element.textContent', stage)
                            if '上传成功' in text_content:
                                upload_success = True
                                break
                        if upload_success:
                            break
                    else:
                        time.sleep(1)
                except Exception:
                    time.sleep(0.5)

            # 填充标题
            time.sleep(1)
            title_container = page.locator('div.plugin.title-container').locator('input.d-text')
            if title_container.count():
                title_container.fill(title[:30])
            else:
                titlecontainer = page.locator(".notranslate")
                titlecontainer.click()
                page.keyboard.press("Backspace")
                page.keyboard.press("Control+KeyA")
                page.keyboard.press("Delete")
                page.keyboard.type(title)
                page.keyboard.press("Enter")

            # 填充话题
            css_selector = ".ql-editor"
            for tag in tags:
                page.type(css_selector, "#" + tag)
                page.press(css_selector, "Space")

            # 设置定时/发布
            if publish_date:
                self.set_schedule_time(page, publish_date)

            while True:
                try:
                    if publish_date:
                        page.locator('button:has-text("定时发布")').click()
                    else:
                        page.locator('button:has-text("发布")').click()
                    page.wait_for_url("https://creator.xiaohongshu.com/publish/success?**", timeout=3000)
                    break
                except:
                    page.screenshot(full_page=True)
                    time.sleep(0.5)

            context.storage_state(path=account_file)
            time.sleep(2)
            context.close()
            browser.close()

        return Response({"code": "0000", "message": "上传成功"})

    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        if thumbnail_path:
            await page.click('text="选择封面"')
            await page.wait_for_selector("div.semi-modal-content:visible")
            await page.click('text="设置竖封面"')
            await page.wait_for_timeout(2000)  # 等待2秒
            # 定位到上传区域并点击
            await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(
                thumbnail_path)
            await page.wait_for_timeout(2000)  # 等待2秒
            await page.locator("div[class^='extractFooter'] button:visible:has-text('完成')").click()


    async def set_location(self, page: Page, location: str = "青岛市"):
        loc_ele = await page.wait_for_selector('div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap')
        await loc_ele.click()

        # 输入位置名称
        await page.wait_for_timeout(1000)
        await page.keyboard.type(location)

        # 等待下拉列表加载
        dropdown_selector = 'div.d-popover.d-popover-default.d-dropdown.--size-min-width-large'
        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_selector(dropdown_selector, timeout=3000)
        except:
            raise Exception("下拉列表未按预期显示，可能结构已变化")

        # 增加等待时间以确保内容加载完成
        await page.wait_for_timeout(1000)

        # 尝试更灵活的XPath选择器
        flexible_xpath = (
            f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
            f'//div[contains(@class, "d-options-wrapper")]'
            f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
            f'//div[contains(@class, "name") and text()="{location}"]'
        )
        await page.wait_for_timeout(3000)
        try:
            # 先尝试使用更灵活的选择器
            location_option = await page.wait_for_selector(
                flexible_xpath,
                timeout=3000
            )

            if location_option:
                print(f"使用灵活选择器定位成功: {location_option}")
            else:
                location_option = await page.wait_for_selector(
                    f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    f'//div[contains(@class, "d-options-wrapper")]'
                    f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    f'/div[1]//div[contains(@class, "name") and text()="{location}"]',
                    timeout=2000
                )

            # 滚动到元素并点击
            await location_option.scroll_into_view_if_needed()

            # 增加元素可见性检查
            is_visible = await location_option.is_visible()

            # 点击元素
            await location_option.click()
            return True

        except Exception as e:
            try:
                all_options = await page.query_selector_all(
                    '//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    '//div[contains(@class, "d-options-wrapper")]'
                    '//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    '/div'
                )

                # 打印前3个选项的文本内容
                for i, option in enumerate(all_options[:3]):
                    option_text = await option.inner_text()

            except Exception as e:
                print(f"获取选项列表失败: {e}")

            # 截图保存（取消注释使用）
            # await page.screenshot(path=f"location_error_{location}.png")
            return False
