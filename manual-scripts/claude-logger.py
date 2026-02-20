#!/usr/bin/env python3
"""
Claude Logger Agent
     Claude API      .
     JSON  Markdown.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    import anthropic
except ImportError:
    print(" :   anthropic")
    print("   pip install anthropic")
    sys.exit(1)


class ClaudeLogger:
    """     Claude API"""

    def __init__(self, api_key: Optional[str] = None, log_dir: str = "../../logs/claude-sessions"):
        """
         

        Args:
            api_key: API  Anthropic (  ANTHROPIC_API_KEY  env)
            log_dir:    
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                " API   !\n"
                "     : export ANTHROPIC_API_KEY='your-key'\n"
                "        --api-key"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.log_dir = Path(__file__).parent / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        #   
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{self.session_id}.json"
        self.markdown_file = self.log_dir / f"session_{self.session_id}.md"

        self.conversation: List[Dict] = []
        self.model = "claude-sonnet-4-20250514"  #   Claude 3.5 Sonnet

        print(f"  : {self.session_id}")
        print(f" : {self.session_file}")
        print(f" Markdown: {self.markdown_file}")
        print()

    def save_logs(self):
        """   JSON  Markdown """
        #  JSON
        session_data = {
            "session_id": self.session_id,
            "started_at": self.session_id,
            "model": self.model,
            "conversation": self.conversation
        }

        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        #  Markdown
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
                f.write(f"###  User Prompt\n\n")
                f.write(f"```\n{prompt}\n```\n\n")
                f.write(f"###  Claude Response\n\n")
                f.write(f"{response}\n\n")
                f.write("---\n\n")

    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        """
           Claude API   

        Args:
            prompt:  
            system:   ()

        Returns:
             Claude
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"    Claude...")

        try:
            #    API
            messages = [{"role": "user", "content": prompt}]

            #   ,  
            kwargs = {"model": self.model, "max_tokens": 4096, "messages": messages}
            if system:
                kwargs["system"] = system

            #  
            message = self.client.messages.create(**kwargs)

            #  
            response = message.content[0].text

            #  
            self.conversation.append({
                "timestamp": timestamp,
                "prompt": prompt,
                "response": response,
                "model": self.model,
                "system": system
            })

            #  
            self.save_logs()

            return response

        except Exception as e:
            error_msg = f" : {str(e)}"
            self.conversation.append({
                "timestamp": timestamp,
                "prompt": prompt,
                "response": error_msg,
                "error": True
            })
            self.save_logs()
            return error_msg

    def interactive_mode(self, system: Optional[str] = None):
        """    Claude"""
        print("   Claude Logger")
        print("    'exit'  'quit'  ")
        print("    'history'   ")
        print("    'clear'   ")
        print()

        while True:
            try:
                #   
                user_input = input(" : ").strip()

                if not user_input:
                    continue

                # 
                if user_input.lower() in ["exit", "quit", "q"]:
                    print(f"\n  .    {self.session_file}")
                    break

                if user_input.lower() == "history":
                    print(f"\n  ({len(self.conversation)} ):")
                    for i, exchange in enumerate(self.conversation, 1):
                        print(f"\n--- Interaction {i} ---")
                        print(f"Prompt: {exchange['prompt'][:100]}...")
                        print(f"Response: {exchange['response'][:100]}...")
                    print()
                    continue

                if user_input.lower() == "clear":
                    self.conversation.clear()
                    print("   ")
                    continue

                #    Claude
                response = self.chat(user_input, system=system)

                #  
                print(f"\n Claude:\n{response}\n")

            except KeyboardInterrupt:
                print(f"\n\n  .    {self.session_file}")
                break
            except Exception as e:
                print(f"\n : {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Logger Agent -    Claude API"
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API  (  ANTHROPIC_API_KEY env variable)"
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help=" Claude   (default: claude-sonnet-4-20250514)"
    )
    parser.add_argument(
        "--system",
        help=" "
    )
    parser.add_argument(
        "--prompt",
        help="  (  )"
    )
    parser.add_argument(
        "--log-dir",
        default="../../logs/claude-sessions",
        help="   (default: ../../logs/claude-sessions)"
    )

    args = parser.parse_args()

    try:
        #  
        agent = ClaudeLogger(api_key=args.api_key, log_dir=args.log_dir)
        agent.model = args.model

        #     
        if args.prompt:
            response = agent.chat(args.prompt, system=args.system)
            print(response)
        else:
            agent.interactive_mode(system=args.system)

    except Exception as e:
        print(f"  : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
