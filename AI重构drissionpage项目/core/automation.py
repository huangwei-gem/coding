"""自动化流程模块（严格对齐源文件流程）"""
import time
from datetime import datetime
from pathlib import Path
from DrissionPage import ChromiumPage

import config


class LogMixin:
    @staticmethod
    def log(msg: str):
        dt = datetime.now().strftime("%m-%d %H:%M:%S")
        line = f"[{dt}] {msg}"
        print(line)
        try:
            with open(config.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


class JobService(LogMixin):
    """岗位搜索与解析"""

    def __init__(self, page: ChromiumPage):
        self.page = page

    def search(self, job_keyword: str, city_code: str):
        """搜索岗位"""
        url = f"{config.JOB_SEARCH_URL}?query={job_keyword}&city={city_code}&industry=&position="
        self.log(f"搜索岗位: 「{job_keyword}」城市代码: {city_code}")
        self.log(f"请求 URL: {url}")
        self.page.set.timeouts(page_load=20)
        self.page.get(url, timeout=20)
        self.log(f"页面加载完成，等待 2s 渲染...")
        time.sleep(2)

    def load_more(self, times: int = config.SCROLL_TIMES):
        """滑到底部加载更多"""
        self.log(f"开始滚动加载，共 {times} 次")
        for i in range(times):
            try:
                self.page.scroll.to_bottom()
                self.page.wait(2)
            except Exception:
                self.log("⚠ 页面被刷新，等待页面加载完成后重试...")
                self.page.wait(3)
                self.page.scroll.to_bottom()
                self.page.wait(2)
            self.log(f"滚动加载 第 {i + 1}/{times} 次完成")
        self.log("滚动加载全部结束")

    def parse_jobs(self) -> list[dict]:
        """解析岗位数据 — 严格对齐源文件"""
        # 岗位链接
        job_elements = self.page.eles(".job-name")
        urls = []
        base = "https://www.zhipin.com"
        for elem in job_elements:
            href = elem.attr("href")
            if href:
                if href.startswith("/"):
                    href = base + href
                urls.append(href)
        self.log(f"获取到 {len(urls)} 个岗位链接元素")

        # 岗位文字
        try:
            job_name_list = self.page.ele(".rec-job-list").texts()
            self.log(f"获取到岗位列表容器，内含 {len(job_name_list)} 条文本块")
        except Exception as e:
            self.log(f"获取岗位列表容器失败: {e}")
            return []

        jobs = []
        for i, job_str in enumerate(job_name_list):
            parts = job_str.split("\n")
            if len(parts) < 4:
                self.log(f"  跳过第 {i} 条: 字段不足 ({len(parts)} < 4)")
                continue

            job_info = {
                "job_name": "",
                "salary": "",
                "experience": parts[1] if len(parts) > 1 else "",
                "education": parts[2] if len(parts) > 2 else "",
                "company_location": parts[3] if len(parts) > 3 else "",
                "url": urls[i] if i < len(urls) else "",
            }

            # 分离职位名和薪资（源文件逻辑）
            first_part = parts[0]
            salary_markers = ["K", "元/月", "元/天", "薪"]
            salary_start = len(first_part)
            for marker in salary_markers:
                idx = first_part.find(marker)
                if idx != -1 and idx < salary_start:
                    salary_start = idx
            if salary_start < len(first_part):
                job_info["job_name"] = first_part[:salary_start].strip()
                job_info["salary"] = first_part[salary_start:].strip()
            else:
                job_info["job_name"] = first_part

            jobs.append(job_info)

        self.log(f"解析完成: 共 {len(jobs)} 个有效岗位")
        if jobs:
            self.log(f"  首个岗位: {jobs[0]['job_name']} | {jobs[0]['salary']} | {jobs[0]['company_location']}")
        return jobs


class AutomationEngine(LogMixin):
    """自动化引擎 — 严格对齐源文件流程"""

    def __init__(self, page: ChromiumPage):
        self.page = page
        self.job_svc = JobService(page)
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def run(
        self,
        city_dict: dict[str, str],
        job_keywords: list[str] | None = None,
        city: str = config.DEFAULT_CITY,
        message: str = config.DEFAULT_MESSAGE,
        image_dir: str | None = None,
        scroll_times: int = config.SCROLL_TIMES,
    ):
        """按岗位列表依次执行自动化"""
        self._running = True
        open(config.LOG_FILE, "w").close()
        processed = skipped = failed = 0
        image_paths = self._get_images(image_dir)
        keywords = job_keywords or [config.DEFAULT_JOB]

        self.log("=" * 50)
        self.log(f"自动化引擎启动")
        self.log(f"目标城市: {city}")
        self.log(f"搜索岗位 ({len(keywords)} 个): {', '.join(keywords)}")
        self.log(f"滚动加载: {scroll_times} 次")
        self.log(f"图片素材: {len(image_paths)} 张")
        self.log(f"消息模板: {message[:50]}...")
        self.log("=" * 50)

        try:
            # ===== 选择城市 =====
            if city not in city_dict:
                self.log(f"城市 「{city}」 不在热门列表中")
                city = next(iter(city_dict))
                self.log(f"已自动切换至: {city}")
            code = city_dict[city]
            self.log(f"城市: {city} (code: {code}), 共 {len(keywords)} 个岗位关键词")

            # ===== 遍历每个岗位关键词 =====
            for kw_idx, job_keyword in enumerate(keywords, 1):
                if not self._running:
                    break

                self.log("─" * 40)
                self.log(f"[{kw_idx}/{len(keywords)}] 开始处理岗位: 「{job_keyword}」")
                self.log("─" * 40)

                # 搜索
                self.job_svc.search(job_keyword, code)
                self.job_svc.load_more(scroll_times)

                # 解析
                jobs = self.job_svc.parse_jobs()
                if not jobs:
                    self.log(f"「{job_keyword}」未找到任何岗位，跳过")
                    continue

                self.log(f"「{job_keyword}」共找到 {len(jobs)} 个岗位，开始逐一沟通")

                # 遍历岗位并沟通
                for job_idx, url_data in enumerate(jobs, 1):
                    if not self._running:
                        self.log("自动化已手动停止")
                        break

                    url = url_data.get("url", "")
                    if not url:
                        self.log(f"  第 {job_idx} 个岗位缺少链接，跳过")
                        continue

                    job_name = url_data.get("job_name", "未知岗位")
                    salary = url_data.get("salary", "")
                    company = url_data.get("company_location", "")

                    self.log("─" * 30)
                    self.log(f"  [{processed + 1}] 处理岗位: {job_name}")
                    if salary:
                        self.log(f"  薪资: {salary}")
                    if company:
                        self.log(f"  地点: {company}")

                    # ---- 源文件 141-142行: print(url); dp.get(url) ----
                    self.log(f"  访问岗位详情页: {url}")
                    try:
                        self.page.set.timeouts(page_load=15)
                        self.page.get(url, timeout=15)
                        self.log(f"  页面加载完成")
                    except Exception as e:
                        self.log(f"  页面访问失败: {e}")
                        failed += 1
                        continue

                    # ---- 源文件 143-145行: 检查是否已沟通 ----
                    try:
                        dp_text = self.page.ele(".btn btn-startchat").text
                        self.log(f"  沟通按钮文本: 「{dp_text}」")
                    except Exception:
                        dp_text = ""
                        self.log(f"  未找到沟通按钮元素")

                    if "继续沟通" in dp_text:
                        self.log(f"  ⚠ 之前已经沟通过，跳过")
                        skipped += 1
                        continue

                    # ---- 源文件 147-155行: 获取详情 ----
                    try:
                        t = self.page.ele(".boss-active-time").text
                        self.log(f"  活跃度: {t}")
                    except Exception:
                        pass
                    try:
                        t = self.page.ele(".icon-scale").text
                        self.log(f"  公司规模: {t}")
                    except Exception:
                        pass
                    try:
                        t = self.page.ele(".job-sec-text").text
                        self.log(f"  职位描述: {t[:80]}...")
                    except Exception:
                        pass
                    try:
                        t = self.page.ele(".salary").text
                        self.log(f"  薪资信息: {t}")
                    except Exception:
                        pass

                    # ---- 源文件 164行: 二次访问 ----
                    self.log(f"  二次访问岗位页面: {url}")
                    try:
                        self.page.set.timeouts(page_load=15)
                        self.page.get(url, timeout=15)
                        self.log(f"  二次加载完成")
                    except Exception as e:
                        self.log(f"  二次访问失败: {e}")
                        failed += 1
                        continue

                    # ---- 源文件 165-180行: 沟通流程 ----
                    self.log(f"  点击「沟通」按钮...")
                    try:
                        self.page.ele(".btn btn-startchat").click()
                        self.log(f"  沟通按钮已点击")
                    except Exception as e:
                        self.log(f"  沟通按钮点击失败: {e}")
                        failed += 1
                        continue

                    self.log(f"  输入打招呼消息...")
                    try:
                        # 依次尝试多个定位方式找到输入框
                        for selector in [".input-area", "chat-input", ".chat-input", "#chat-input"]:
                            try:
                                el = self.page.ele(selector, timeout=2)
                                if not el:  # NoneElement 是假值，跳过
                                    continue
                                self.log(f"  定位到输入框: {selector}")
                                el.input(message)
                                # 发送按钮可能不出现，直接在输入框按 Enter 发送
                                self.page.wait(1)
                                el.input("\n")
                                break
                            except Exception:
                                continue
                        else:
                            raise Exception("无法定位到消息输入框")
                        self.log(f"  ✅ 文字消息已发送成功")
                    except Exception as e:
                        self.log(f"  发送消息失败: {e}")
                        failed += 1
                        continue

                    # 关闭对话框
                    try:
                        self.page.ele(".icon-close").click()
                        self.log(f"  对话框已关闭")
                        self.page.ele(".btn btn-startchat").click()
                    except Exception:
                        pass

                    # ---- 源文件 168-171行: 上传图片 ----
                    if image_paths:
                        self.log(f"  准备上传图片（共 {len(image_paths)} 张）...")
                    for img_path in image_paths:
                        if not img_path.exists():
                            self.log(f"  图片不存在，跳过: {img_path.name}")
                            continue
                        try:
                            self.page.ele(
                                ".toolbar-btn-content icon btn-sendimg tooltip tooltip-top"
                            ).click.to_upload(str(img_path))
                            self.log(f"  🖼 图片已上传: {img_path.name}")
                        except Exception as e:
                            self.log(f"  图片上传失败: {img_path.name} - {e}")

                    processed += 1
                    self.log(f"  ✅ 第 {processed} 个岗位沟通完成")
                    self.log(f"  ─ 等待 2s 避免操作频繁...")
                    time.sleep(2)  # 请求间隔，避免频繁操作

                # 结束当前关键词
                self.log(f"「{job_keyword}」 处理完毕")

        except Exception as e:
            self.log(f"!" * 40)
            self.log(f"自动化流程异常: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.log(f"!" * 40)

        finally:
            self._running = False
            self.log("=" * 50)
            self.log(f"自动化执行完毕")
            self.log(f"  成功沟通: {processed} 个")
            self.log(f"  已跳过:   {skipped} 个（之前沟通过）")
            self.log(f"  失败:     {failed} 个")
            self.log(f"  总计处理: {processed + skipped + failed} 个")
            self.log("=" * 50)

    def stop(self):
        self._running = False
        self.log("收到停止信号，等待当前任务完成后停止...")

    @staticmethod
    def _get_images(image_dir: str | None) -> list[Path]:
        if not image_dir:
            return []
        img_dir = Path(image_dir)
        if not img_dir.exists():
            return []
        return sorted(img_dir.glob("*.png")) + sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.jpeg"))
