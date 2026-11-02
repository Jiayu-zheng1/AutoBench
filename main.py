"""AutoBench — 串口测试自动化工具入口。"""

from app.application import Application

if __name__ == "__main__":
    app = Application()
    app.create()
    app.show()
    app.run()
