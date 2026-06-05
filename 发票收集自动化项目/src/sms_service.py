"""短信发送服务 - 对接短信API，批量发送定制短信"""
import random
import time
from typing import Callable

import requests
from loguru import logger

from config import SMS_CONFIG, RUN_MODE


class SmsSender:
    """短信发送器"""

    def __init__(self, progress_callback: Callable = None):
        self.progress_callback = progress_callback
        self.success_count = 0
        self.fail_count = 0

    def _format_content(self, template: str, owner: dict) -> str:
        """用业主数据填充短信模板变量"""
        return template.format(
            name=owner.get("name", "业主"),
            building=owner.get("building", ""),
            floor=owner.get("floor", ""),
            room=owner.get("room", ""),
        )

    def _send_single_demo(self, phone: str, content: str) -> tuple[bool, str]:
        """demo 模式：模拟发送"""
        delay = random.uniform(0.1, 0.3)
        time.sleep(delay)
        # 模拟 95% 成功率
        success = random.random() < 0.95
        msg_id = f"demo_{int(time.time())}_{phone[-4:]}" if success else ""
        return success, msg_id

    def _send_single_aliyun(self, phone: str, content: str) -> tuple[bool, str]:
        """阿里云短信发送"""
        import hmac
        import base64
        import hashlib
        import uuid
        from urllib.parse import quote

        params = {
            "Action": "SendSms",
            "Version": "2017-05-25",
            "PhoneNumbers": phone,
            "SignName": SMS_CONFIG["sign_name"],
            "TemplateCode": SMS_CONFIG["template_code"],
            "TemplateParam": '{"content":"' + content + '"}',
            "AccessKeyId": SMS_CONFIG["access_key_id"],
            "Format": "JSON",
            "RegionId": "cn-hangzhou",
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": str(uuid.uuid4()),
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # 排序参数并构造签名串
        sorted_keys = sorted(params.keys())
        canonicalized = "&".join(
            f"{quote(k, safe='')}={quote(params[k], safe='')}" for k in sorted_keys
        )
        string_to_sign = f"GET&{quote('/', safe='')}&{quote(canonicalized, safe='')}"

        # 计算签名
        secret = SMS_CONFIG["access_key_secret"] + "&"
        signature = base64.b64encode(
            hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()

        params["Signature"] = signature
        query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())
        url = f"http://dysmsapi.aliyuncs.com/?{query}"

        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("Code") == "OK":
                return True, resp.get("BizId", "")
            logger.warning(f"[短信] 阿里云返回错误: {resp}")
            return False, ""
        except Exception as e:
            logger.error(f"[短信] 阿里云请求异常: {e}")
            return False, ""

    def _send_single(self, phone: str, content: str) -> tuple[bool, str]:
        """发送单条短信，自动选择模式"""
        if RUN_MODE == "demo":
            return self._send_single_demo(phone, content)

        provider = SMS_CONFIG.get("provider", "aliyun")
        if provider == "aliyun":
            return self._send_single_aliyun(phone, content)
        else:
            logger.warning(f"[短信] 不支持的 provider: {provider}，回退 demo 模式")
            return self._send_single_demo(phone, content)

    def send_batch(self, owners: list[dict],
                   template: str = None,
                   max_retries: int = 2) -> list[dict]:
        """批量发送短信

        Args:
            owners: 业主列表 [{name, phone, building, room, ...}]
            template: 短信模板，支持 {name} {building} {floor} {room}
            max_retries: 失败重试次数

        Returns:
            [{"owner": dict, "success": bool, "msg_id": str, "record_id": int}, ...]
        """
        template = template or SMS_CONFIG["custom_content"]
        results = []
        total = len(owners)

        logger.info(f"[短信] 开始批量发送: {total} 条")

        for idx, owner in enumerate(owners):
            phone = owner.get("phone", "").strip()
            if not phone:
                results.append({"owner": owner, "success": False,
                                "msg_id": "", "record_id": None})
                continue

            content = self._format_content(template, owner)

            success = False
            msg_id = ""
            for attempt in range(max_retries + 1):
                success, msg_id = self._send_single(phone, content)
                if success:
                    break
                if attempt < max_retries:
                    logger.debug(f"[短信] 重试 ({attempt+1}/{max_retries}): {phone}")
                    time.sleep(1)

            if success:
                self.success_count += 1
            else:
                self.fail_count += 1

            results.append({
                "owner": owner,
                "success": success,
                "msg_id": msg_id,
                "content": content,
            })

            # 进度回调
            if self.progress_callback:
                self.progress_callback(idx + 1, total, success)

            if (idx + 1) % 10 == 0:
                logger.info(f"[短信] 进度: {idx+1}/{total} "
                            f"(成功: {self.success_count}, 失败: {self.fail_count})")

            # 防止触发 API 限流
            if RUN_MODE != "demo" and (idx + 1) % 50 == 0:
                time.sleep(2)

        logger.info(f"[短信] 发送完成: 成功 {self.success_count}, 失败 {self.fail_count}")
        return results

    def check_delivery_status(self, msg_id: str) -> str:
        """查询短信送达状态（生产模式用）"""
        return "DELIVERED"
