"""Generate a topology-backed Proxmox bootstrap package for srv-gamayun."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = Path(__file__).resolve().parent
TOPOLOGY_TOOLS_DIR = SCRIPT_DIR.parent.parent.parent.parent
TEMPLATES_DIR = TOPOLOGY_TOOLS_DIR / "templates" / "bootstrap" / "proxmox"
MANUAL_SOURCE_DIR = TOPOLOGY_TOOLS_DIR.parent / "manual-scripts" / "bare-metal"
DEFAULT_OUTPUT_DIR = TOPOLOGY_TOOLS_DIR.parent / "generated" / "bootstrap" / "srv-gamayun"
PLACEHOLDER_ROOT_PASSWORD = "REPLACE_WITH_SHA512_PASSWORD_HASH"  # pragma: allowlist secret


class ProxmoxBootstrapGenerator:
    """Generate a safe bootstrap package for Proxmox auto-install."""

    def __init__(
        self,
        topology_path: str,
        output_dir: Path | None = None,
    ):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _render(self, template_name: str) -> str:
        template = self.env.get_template(template_name)
        return template.render(
            generation_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            topology_path=self.topology_path.as_posix(),
            package_root=self.output_dir.as_posix(),
            answer_file="answer.toml",
            answer_example="answer.toml.example",
            post_install_dir="post-install",
            usb_script="create-uefi-autoinstall-proxmox-usb.sh",
            device_id="srv-gamayun",
        )

    def _copy_required_sources(self) -> dict[str, str]:
        copied_paths: dict[str, str] = {}

        files_to_copy = [
            "create-uefi-autoinstall-proxmox-usb.sh",
        ]
        for filename in files_to_copy:
            source = MANUAL_SOURCE_DIR / filename
            target = self.output_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied_paths[filename] = str(target)

        post_install_source = MANUAL_SOURCE_DIR / "post-install"
        post_install_target = self.output_dir / "post-install"
        shutil.copytree(post_install_source, post_install_target, dirs_exist_ok=True)
        copied_paths["post-install"] = str(post_install_target)

        return copied_paths

    def _generate_answer_example(self) -> str:
        output_path = self.output_dir / "answer.toml.example"
        command = [
            sys.executable,
            str(TOPOLOGY_TOOLS_DIR / "generate-proxmox-answer.py"),
            str(self.topology_path),
            str(output_path),
        ]
        subprocess.run(command, cwd=TOPOLOGY_TOOLS_DIR.parent, check=True)

        content = output_path.read_text()
        content = re.sub(
            r'^root_password = ".*"$',
            f'root_password = "{PLACEHOLDER_ROOT_PASSWORD}"',
            content,
            flags=re.MULTILINE,
        )
        content = re.sub(
            r"^# DO NOT EDIT MANUALLY - Regenerate with topology-tools/generate-proxmox-answer.py$",
            "# Generated from topology. Materialize a local answer.toml before USB creation.",
            content,
            flags=re.MULTILINE,
        )
        output_path.write_text(content)
        return str(output_path)

    def generate(self) -> dict[str, str]:
        """Generate the Proxmox bootstrap package under generated/bootstrap/srv-gamayun."""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        generated_paths = self._copy_required_sources()
        generated_paths["answer.toml.example"] = self._generate_answer_example()

        readme_path = self.output_dir / "README.md"
        readme_path.write_text(self._render("README.md.j2"))
        generated_paths["README.md"] = str(readme_path)

        return generated_paths
