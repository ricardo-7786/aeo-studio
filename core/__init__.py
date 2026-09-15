"""Core package — import submodules directly (e.g. core.telegram_notify).

Heavy deps (openai 등)는 submodule import 시에만 로드되도록
여기에서는 eager re-export 하지 않습니다.
"""
