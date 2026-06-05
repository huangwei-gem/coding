"""数据库操作模块 - MySQL建表 + CRUD"""
import json
from datetime import datetime
from typing import Optional

import pymysql
from pymysql.cursors import DictCursor
from loguru import logger

from config import DB_CONFIG, RUN_MODE


class MockStore:
    """demo 模式下的内存存储，模拟数据库行为"""

    def __init__(self):
        self.owners = []
        self.sms_records = []
        self.replies = []
        self.intentions = []
        self.filter_logs = []
        self.evidences = []
        self._owner_id_seq = 0
        self._sms_id_seq = 0
        self._reply_id_seq = 0
        self._intention_id_seq = 0
        self._filter_id_seq = 0
        self._evidence_id_seq = 0

    def _next_id(self, seq_attr):
        val = getattr(self, seq_attr) + 1
        setattr(self, seq_attr, val)
        return val


class Database:
    """数据库操作封装，自动适配 demo/production 模式"""

    def __init__(self):
        self.mock = MockStore()
        self._conn: Optional[pymysql.Connection] = None

    def connect(self):
        if RUN_MODE == "demo":
            logger.info("[数据库] demo 模式，使用内存存储")
            return
        try:
            self._conn = pymysql.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                charset="utf8mb4",
                cursorclass=DictCursor,
            )
            logger.info("[数据库] MySQL 连接成功")
            self._init_tables()
        except pymysql.Error as e:
            logger.error(f"[数据库] 连接失败: {e}")
            raise

    def _init_tables(self):
        """生产模式自动建表"""
        sqls = [
            """CREATE TABLE IF NOT EXISTS owners (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                building VARCHAR(10) DEFAULT '',
                room VARCHAR(20) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_phone (phone)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS sms_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id INT NOT NULL,
                phone VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                msg_id VARCHAR(100) DEFAULT '',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES owners(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS replies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id INT,
                phone VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                received_at DATETIME NOT NULL,
                is_duplicate TINYINT(1) DEFAULT 0,
                raw_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_phone (phone),
                INDEX idx_received (received_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS intention_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id INT,
                reply_id INT,
                intention INT DEFAULT -1 COMMENT '1=同意 0=不同意 -1=待确认',
                method VARCHAR(20) DEFAULT '',
                confidence DECIMAL(5,2) DEFAULT 0.00,
                raw_reply TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS filter_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reply_id INT,
                filter_type VARCHAR(20) DEFAULT '',
                action_taken VARCHAR(50) DEFAULT '',
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS evidence (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id INT,
                reply_id INT,
                screenshot_path VARCHAR(500) DEFAULT '',
                reply_content TEXT,
                received_at DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ]
        with self._conn.cursor() as cur:
            for sql in sqls:
                cur.execute(sql)
        self._conn.commit()
        logger.info("[数据库] 表结构初始化完成")

    # ---- 业主操作 ----

    def batch_insert_owners(self, owners: list[dict]) -> list[int]:
        """批量插入业主，返回 id 列表"""
        ids = []
        if RUN_MODE == "demo":
            for o in owners:
                self.mock._owner_id_seq += 1
                o["id"] = self.mock._owner_id_seq
                self.mock.owners.append(dict(o))
                ids.append(o["id"])
            logger.info(f"[数据库] demo 写入 {len(ids)} 条业主记录")
            return ids

        sql = """INSERT INTO owners (name, phone, building, room)
                 VALUES (%(name)s, %(phone)s, %(building)s, %(room)s)"""
        with self._conn.cursor() as cur:
            for o in owners:
                cur.execute(sql, o)
                ids.append(cur.lastrowid)
            self._conn.commit()
        return ids

    def get_all_owners(self) -> list[dict]:
        if RUN_MODE == "demo":
            return list(self.mock.owners)
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM owners")
            return cur.fetchall()

    def get_owner_by_phone(self, phone: str) -> Optional[dict]:
        if RUN_MODE == "demo":
            for o in self.mock.owners:
                if o["phone"] == phone:
                    return o
            return None
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM owners WHERE phone = %s", (phone,))
            return cur.fetchone()

    # ---- 短信记录 ----

    def insert_sms_record(self, owner_id: int, phone: str, content: str,
                          status: str = "pending", msg_id: str = "") -> int:
        if RUN_MODE == "demo":
            self.mock._sms_id_seq += 1
            rec = {"id": self.mock._sms_id_seq, "owner_id": owner_id,
                   "phone": phone, "content": content, "status": status,
                   "msg_id": msg_id, "sent_at": datetime.now()}
            self.mock.sms_records.append(rec)
            return rec["id"]
        sql = """INSERT INTO sms_records (owner_id, phone, content, status, msg_id)
                 VALUES (%s, %s, %s, %s, %s)"""
        with self._conn.cursor() as cur:
            cur.execute(sql, (owner_id, phone, content, status, msg_id))
            self._conn.commit()
            return cur.lastrowid

    def update_sms_status(self, record_id: int, status: str, msg_id: str = ""):
        if RUN_MODE == "demo":
            for r in self.mock.sms_records:
                if r["id"] == record_id:
                    r["status"] = status
                    if msg_id:
                        r["msg_id"] = msg_id
                    break
            return
        sql = "UPDATE sms_records SET status=%s, msg_id=%s WHERE id=%s"
        with self._conn.cursor() as cur:
            cur.execute(sql, (status, msg_id, record_id))
            self._conn.commit()

    # ---- 回复操作 ----

    def insert_reply(self, phone: str, content: str, received_at: datetime,
                     is_duplicate: bool = False, raw_data: dict = None) -> int:
        """写入回复，自动关联业主"""
        owner = self.get_owner_by_phone(phone)
        owner_id = owner["id"] if owner else None

        if RUN_MODE == "demo":
            self.mock._reply_id_seq += 1
            rep = {"id": self.mock._reply_id_seq, "owner_id": owner_id,
                   "phone": phone, "content": content, "received_at": received_at,
                   "is_duplicate": 1 if is_duplicate else 0,
                   "raw_data": raw_data or {}}
            self.mock.replies.append(rep)
            return rep["id"]

        sql = """INSERT INTO replies (owner_id, phone, content, received_at, is_duplicate, raw_data)
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        with self._conn.cursor() as cur:
            cur.execute(sql, (owner_id, phone, content, received_at, int(is_duplicate),
                              json.dumps(raw_data, ensure_ascii=False)))
            self._conn.commit()
            return cur.lastrowid

    def is_duplicate_reply(self, phone: str, content: str) -> bool:
        """检查是否为重复回复"""
        if RUN_MODE == "demo":
            for r in self.mock.replies:
                if r["phone"] == phone and r["content"].strip() == content.strip():
                    return True
            return False
        sql = "SELECT COUNT(*) AS cnt FROM replies WHERE phone=%s AND content=%s"
        with self._conn.cursor() as cur:
            cur.execute(sql, (phone, content.strip()))
            row = cur.fetchone()
            return row["cnt"] > 0

    def get_all_replies(self) -> list[dict]:
        if RUN_MODE == "demo":
            return list(self.mock.replies)
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM replies WHERE is_duplicate=0")
            return cur.fetchall()

    def get_unprocessed_replies(self) -> list[dict]:
        """获取尚未做意愿分析的回复"""
        if RUN_MODE == "demo":
            analyzed_ids = {r["reply_id"] for r in self.mock.intentions}
            return [r for r in self.mock.replies
                    if not r["is_duplicate"] and r["id"] not in analyzed_ids]
        sql = """SELECT r.* FROM replies r
                 LEFT JOIN intention_results i ON r.id = i.reply_id
                 WHERE r.is_duplicate=0 AND i.id IS NULL"""
        with self._conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    # ---- 意愿结果 ----

    def insert_intention(self, owner_id: int, reply_id: int, intention: int,
                         method: str, confidence: float, raw_reply: str = "") -> int:
        if RUN_MODE == "demo":
            self.mock._intention_id_seq += 1
            rec = {"id": self.mock._intention_id_seq, "owner_id": owner_id,
                   "reply_id": reply_id, "intention": intention,
                   "method": method, "confidence": confidence,
                   "raw_reply": raw_reply, "analyzed_at": datetime.now()}
            self.mock.intentions.append(rec)
            return rec["id"]
        sql = """INSERT INTO intention_results
                 (owner_id, reply_id, intention, method, confidence, raw_reply)
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        with self._conn.cursor() as cur:
            cur.execute(sql, (owner_id, reply_id, intention, method,
                              confidence, raw_reply))
            self._conn.commit()
            return cur.lastrowid

    def get_unverified_intentions(self) -> list[dict]:
        """获取准确率低于阈值、需要人工复核的长难句结果"""
        if RUN_MODE == "demo":
            return [r for r in self.mock.intentions
                    if r["confidence"] < 0.95]
        sql = """SELECT * FROM intention_results
                 WHERE confidence < 0.95
                 ORDER BY confidence ASC"""
        with self._conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def get_intention_statistics(self) -> dict:
        """获取意愿统计汇总"""
        if RUN_MODE == "demo":
            total = len(self.mock.intentions)
            agree = sum(1 for r in self.mock.intentions if r["intention"] == 1)
            disagree = sum(1 for r in self.mock.intentions if r["intention"] == 0)
            pending = sum(1 for r in self.mock.intentions if r["intention"] == -1)
        else:
            with self._conn.cursor() as cur:
                cur.execute("""SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN intention=1 THEN 1 ELSE 0 END) AS agree,
                    SUM(CASE WHEN intention=0 THEN 1 ELSE 0 END) AS disagree,
                    SUM(CASE WHEN intention=-1 THEN 1 ELSE 0 END) AS pending
                    FROM intention_results""")
                row = cur.fetchone()
                total = row["total"]
                agree = row["agree"] or 0
                disagree = row["disagree"] or 0
                pending = row["pending"] or 0

        return {
            "total": total,
            "agree": agree,
            "disagree": disagree,
            "pending": pending,
            "agree_rate": round(agree / total * 100, 2) if total > 0 else 0.0,
        }

    # ---- 过滤日志 ----

    def insert_filter_log(self, reply_id: int, filter_type: str,
                          action_taken: str, details: str = ""):
        if RUN_MODE == "demo":
            self.mock._filter_id_seq += 1
            self.mock.filter_logs.append({
                "id": self.mock._filter_id_seq, "reply_id": reply_id,
                "filter_type": filter_type, "action_taken": action_taken,
                "details": details, "created_at": datetime.now(),
            })
            return
        sql = """INSERT INTO filter_logs (reply_id, filter_type, action_taken, details)
                 VALUES (%s, %s, %s, %s)"""
        with self._conn.cursor() as cur:
            cur.execute(sql, (reply_id, filter_type, action_taken, details))
            self._conn.commit()

    # ---- 证据 ----

    def insert_evidence(self, owner_id: int, reply_id: int,
                        screenshot_path: str, reply_content: str,
                        received_at: datetime) -> int:
        if RUN_MODE == "demo":
            self.mock._evidence_id_seq += 1
            self.mock.evidences.append({
                "id": self.mock._evidence_id_seq, "owner_id": owner_id,
                "reply_id": reply_id, "screenshot_path": screenshot_path,
                "reply_content": reply_content, "received_at": received_at,
                "created_at": datetime.now(),
            })
            return self.mock._evidence_id_seq
        sql = """INSERT INTO evidence (owner_id, reply_id, screenshot_path, reply_content, received_at)
                 VALUES (%s, %s, %s, %s, %s)"""
        with self._conn.cursor() as cur:
            cur.execute(sql, (owner_id, reply_id, screenshot_path,
                              reply_content, received_at))
            self._conn.commit()
            return cur.lastrowid

    def close(self):
        if self._conn and not RUN_MODE == "demo":
            self._conn.close()
            logger.info("[数据库] 连接已关闭")
