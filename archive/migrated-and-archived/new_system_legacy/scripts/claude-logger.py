#!/usr/bin/env python3
"""
Claude Logger Agent
Интерактивный агент для общения с Claude API с логированием всех промптов и ответов.
Сохраняет историю локально в файлы JSON и Markdown.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import anthropic
except ImportError:
    print("❌ Ошибка: установите библиотеку anthropic")
    print("   pip install anthropic")
    sys.exit(1)


class ClaudeLogger:
    """Агент для логирования взаимодействий с Claude API"""

    def __init__(self, api_key: Optional[str] = None, log_dir: str = "../../logs/claude-sessions"):
        """
        Инициализация агента

        Args:
            api_key: API ключ Anthropic (или использует ANTHROPIC_API_KEY из env)
            log_dir: Директория для сохранения логов
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "❌ API ключ не найден!\n"
                "   Установите переменную окружения: export ANTHROPIC_API_KEY='your-key'\n"
                "   Или передайте ключ через параметр --api-key"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.log_dir = Path(__file__).parent / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Создаем новую сессию
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{self.session_id}.json"
        self.markdown_file = self.log_dir / f"session_{self.session_id}.md"

        self.conversation: List[Dict] = []
        self.model = "claude-sonnet-4-20250514"  # Последняя модель Claude 3.5 Sonnet

        print(f"✅ Сессия начата: {self.session_id}")
        print(f"📁 Логи: {self.session_file}")
        print(f"📄 Markdown: {self.markdown_file}")
        print()

    def save_logs(self):
        """Сохраняет логи в JSON и Markdown форматах"""
        # Сохранение JSON
        session_data = {
            "session_id": self.session_id,
            "started_at": self.session_id,
            "model": self.model,
            "conversation": self.conversation,
        }

        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        # Сохранение Markdown
        with open(self.markdown_file, "w", encoding="utf-8") as f:
            f.write(f"# Claude Session {self.session_id}\n\n")
            f.write(f"**Model:** {self.model}\n\n")
            f.write(f"**Started:** {self.session_id}\n\n")
            f.write("---\n\n")

            for i, exchange in enumerate(self.conversation, 1):
                timestamp = exchange.get("timestamp", "")
                prompt = exchange.get("prompt", "")
                response = exchange.get("response", "")

                f.write(f"## Interaction {i}\n\n")
                f.write(f"**Time:** {timestamp}\n\n")
                f.write(f"### 🙋 User Prompt\n\n")
                f.write(f"```\n{prompt}\n```\n\n")
                f.write(f"### 🤖 Claude Response\n\n")
                f.write(f"{response}\n\n")
                f.write("---\n\n")

    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Отправляет промпт в Claude API и логирует взаимодействие

        Args:
            prompt: Промпт пользователя
            system: Системный промпт (опционально)

        Returns:
            Ответ Claude
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"⏳ Отправка запроса в Claude...")

        try:
            # Формируем сообщения для API
            messages = [{"role": "user", "content": prompt}]

            # Добавляем системный промпт, если указан
            kwargs = {"model": self.model, "max_tokens": 4096, "messages": messages}
            if system:
                kwargs["system"] = system

            # Отправляем запрос
            message = self.client.messages.create(**kwargs)

            # Извлекаем ответ
            response = message.content[0].text

            # Логируем взаимодействие
            self.conversation.append(
                {"timestamp": timestamp, "prompt": prompt, "response": response, "model": self.model, "system": system}
            )

            # Сохраняем логи
            self.save_logs()

            return response

        except Exception as e:
            error_msg = f"❌ Ошибка: {str(e)}"
            self.conversation.append({"timestamp": timestamp, "prompt": prompt, "response": error_msg, "error": True})
            self.save_logs()
            return error_msg

    def interactive_mode(self, system: Optional[str] = None):
        """Интерактивный режим общения с Claude"""
        print("🤖 Интерактивный режим Claude Logger")
        print("   Введите 'exit' или 'quit' для выхода")
        print("   Введите 'history' для просмотра истории")
        print("   Введите 'clear' для очистки истории")
        print()

        while True:
            try:
                # Читаем ввод пользователя
                user_input = input("🙋 Вы: ").strip()

                if not user_input:
                    continue

                # Команды
                if user_input.lower() in ["exit", "quit", "q"]:
                    print(f"\n👋 Сессия завершена. Логи сохранены в {self.session_file}")
                    break

                if user_input.lower() == "history":
                    print(f"\n📜 История ({len(self.conversation)} взаимодействий):")
                    for i, exchange in enumerate(self.conversation, 1):
                        print(f"\n--- Interaction {i} ---")
                        print(f"Prompt: {exchange['prompt'][:100]}...")
                        print(f"Response: {exchange['response'][:100]}...")
                    print()
                    continue

                if user_input.lower() == "clear":
                    self.conversation.clear()
                    print("🗑️  История очищена")
                    continue

                # Отправляем запрос в Claude
                response = self.chat(user_input, system=system)

                # Выводим ответ
                print(f"\n🤖 Claude:\n{response}\n")

            except KeyboardInterrupt:
                print(f"\n\n👋 Сессия прервана. Логи сохранены в {self.session_file}")
                break
            except Exception as e:
                print(f"\n❌ Ошибка: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Claude Logger Agent - логирование взаимодействий с Claude API")
    parser.add_argument("--api-key", help="Anthropic API ключ (или используйте ANTHROPIC_API_KEY env variable)")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Модель Claude для использования (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument("--system", help="Системный промпт")
    parser.add_argument("--prompt", help="Одиночный промпт (без интерактивного режима)")
    parser.add_argument(
        "--log-dir",
        default="../../logs/claude-sessions",
        help="Директория для логов (default: ../../logs/claude-sessions)",
    )

    args = parser.parse_args()

    try:
        # Создаем агента
        agent = ClaudeLogger(api_key=args.api_key, log_dir=args.log_dir)
        agent.model = args.model

        # Одиночный промпт или интерактивный режим
        if args.prompt:
            response = agent.chat(args.prompt, system=args.system)
            print(response)
        else:
            agent.interactive_mode(system=args.system)

    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
