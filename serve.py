#!/usr/bin/env python3
"""
简易 HTTP 服务器，用于本地运行 filter_demo.html
解决 file:// 协议下 Chart.js 加载被阻止的问题
"""
import http.server
import socketserver
import webbrowser
import threading
import time
import sys

PORT = 8000

def open_browser():
    """等待服务器启动后打开浏览器"""
    time.sleep(1.5)
    webbrowser.open(f'http://localhost:{PORT}/filter_demo.html')

def main():
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("=" * 60)
        print(f"HTTP 服务器启动在 http://localhost:{PORT}")
        print("正在打开浏览器...")
        print("按 Ctrl+C 停止服务器")
        print("=" * 60)

        # 在后台线程中打开浏览器
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")

if __name__ == "__main__":
    main()