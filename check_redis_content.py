#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查Redis中的流式内容存储"""

import redis
import json
import sys
import os

# 设置UTF-8编码输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_redis_content():
    try:
        # 连接Redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # 获取所有task相关的keys
        task_keys = r.keys("task:*")
        print(f"[INFO] 找到 {len(task_keys)} 个任务相关键")

        for key in sorted(task_keys):
            print(f"\n[KEY] {key}")

            # 检查键类型
            key_type = r.type(key)
            print(f"      类型: {key_type}")

            if key_type == 'hash':
                # 获取hash的所有字段
                hash_data = r.hgetall(key)
                for field, value in hash_data.items():
                    if len(value) > 100:
                        print(f"      {field}: {value[:100]}...")
                    else:
                        print(f"      {field}: {value}")

            elif key_type == 'list':
                # 获取list的长度和内容
                list_length = r.llen(key)
                print(f"      长度: {list_length}")
                if list_length > 0:
                    # 获取前5个和后5个元素
                    if list_length <= 10:
                        items = r.lrange(key, 0, -1)
                    else:
                        start_items = r.lrange(key, 0, 4)
                        end_items = r.lrange(key, -5, -1)
                        items = start_items + ["..."] + end_items

                    for i, item in enumerate(items):
                        if item == "...":
                            print(f"      [{i}]: ...")
                        elif len(item) > 80:
                            print(f"      [{i}]: {item[:80]}...")
                        else:
                            print(f"      [{i}]: {item}")

            elif key_type == 'string':
                value = r.get(key)
                if len(value) > 100:
                    print(f"      值: {value[:100]}...")
                else:
                    print(f"      值: {value}")

        print(f"\n[SUCCESS] Redis连接正常，共检查了 {len(task_keys)} 个键")

    except redis.ConnectionError:
        print("[ERROR] 无法连接到Redis服务器")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 检查Redis时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_redis_content()