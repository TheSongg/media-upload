import logging
import re
from pickle import FALSE

from rest_framework.decorators import action
from rest_framework.response import Response
from media_upload.utils.base_views import BaseViewSet

from django.db import transaction
from media_upload.utils.comm import set_init_script


from datetime import datetime
from .models import XiaoHongShuVideo
from .serializers import XiaoHongShuVideoSerializer
from playwright.async_api import Playwright, async_playwright, Page
import os
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

    async def set_schedule_time_xiaohongshu(self, page, publish_date):
        print("  [-] 正在设置定时发布时间...")
        print(f"publish_date: {publish_date}")

        # 使用文本内容定位元素
        # element = await page.wait_for_selector(
        #     'label:has-text("定时发布")',
        #     timeout=5000  # 5秒超时时间
        # )
        # await element.click()

        # # 选择包含特定文本内容的 label 元素
        label_element = page.locator("label:has-text('定时发布')")
        # # 在选中的 label 元素下点击 checkbox
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        print(f"publish_date_hour: {publish_date_hour}")

        await asyncio.sleep(1)
        await page.locator('.el-input__inner[placeholder="选择日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")

        await asyncio.sleep(1)

    async def handle_upload_error(self, page):
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    @action(detail=False, methods=['post'], url_path='upload')
    async def upload(self, request, *args, **kwargs) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        print(121111)
        print(request.data)
        account_file = request.data.get("account_file")
        local_executable_path = request.data.get("local_executable_path")

        if not account_file:
            return Response({"error": "缺少 account_file"}, status=400)
        playwright = Playwright()
        browser = await playwright.chromium.launch(headless=False)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            storage_state=f"{account_file}"
        )
        context = await set_init_script(context)

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        await page.wait_for_url("https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")
        # 点击 "上传视频" 按钮
        await page.locator("div[class^='upload-content'] input[class='upload-input']").set_input_files(self.file_path)

        # 等待页面跳转到指定的 URL 2025.01.08修改在原有基础上兼容两种页面
        while True:
            try:
                # 等待upload-input元素出现
                upload_input = await page.wait_for_selector('input.upload-input', timeout=3000)
                # 获取下一个兄弟元素
                preview_new = await upload_input.query_selector(
                    'xpath=following-sibling::div[contains(@class, "preview-new")]')
                if preview_new:
                    # 在preview-new元素中查找包含"上传成功"的stage元素
                    stage_elements = await preview_new.query_selector_all('div.stage')
                    upload_success = False
                    for stage in stage_elements:
                        text_content = await page.evaluate('(element) => element.textContent', stage)
                        if '上传成功' in text_content:
                            upload_success = True
                            break
                    if upload_success:
                        break
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                await asyncio.sleep(0.5)

        # 填充标题和话题
        # 检查是否存在包含输入框的元素
        # 这里为了避免页面变化，故使用相对位置定位：作品标题父级右侧第一个元素的input子元素
        await asyncio.sleep(1)
        title_container = page.locator('div.plugin.title-container').locator('input.d-text')
        if await title_container.count():
            await title_container.fill(title[:30])
        else:
            titlecontainer = page.locator(".notranslate")
            await titlecontainer.click()
            await page.keyboard.press("Backspace")
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.press("Delete")
            await page.keyboard.type(title)
            await page.keyboard.press("Enter")
        css_selector = ".ql-editor"  # 不能加上 .ql-blank 属性，这样只能获取第一次非空状态
        for index, tag in enumerate(tags, start=1):
            await page.type(css_selector, "#" + tag)
            await page.press(css_selector, "Space")

        if publish_date != 0:
            await set_schedule_time_xiaohongshu(page, publish_date)

        # 判断视频是否发布成功
        while True:
            try:
                # 等待包含"定时发布"文本的button元素出现并点击
                if publish_date != 0:
                    await page.locator('button:has-text("定时发布")').click()
                else:
                    await page.locator('button:has-text("发布")').click()
                await page.wait_for_url(
                    "https://creator.xiaohongshu.com/publish/success?**",
                    timeout=3000
                )  # 如果自动跳转到作品页面，则代表发布成功
                break
            except:
                await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

        await context.storage_state(path=account_file)  # 保存cookie
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

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

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)