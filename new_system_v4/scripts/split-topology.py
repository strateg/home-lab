#!/usr/bin/env python3
"""
Split topology.yaml into modular files (preserving comments and formatting)
"""

import re
from pathlib import Path

def extract_section(lines, start_pattern, end_pattern=None):
    """Extract a section from lines, preserving formatting"""
    result = []
    in_section = False
    indent_level = None

    for i, line in enumerate(lines):
        # Check if this is the start of our section
        if re.match(start_pattern, line):
            in_section = True
            # Find the indent level (number of spaces before the key)
            indent_level = len(line) - len(line.lstrip())
            continue  # Skip the section header itself

        # If we're in the section
        if in_section:
            # Check if we've reached the next top-level section
            if line.strip() and not line.startswith('#') and not line.startswith(' '):
                # This is a new top-level key, stop
                break

            # Check if this line is at the same or lower indent level (new section)
            if line.strip() and not line.startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level:
                    break

            # Add the line (dedent by removing section indent)
            if line.strip():  # Non-empty line
                if line.startswith(' ' * indent_level):
                    result.append(line[indent_level:])  # Remove indent
                else:
                    result.append(line)  # Keep as is (comments, etc.)
            else:
                result.append(line)  # Empty line

    return result

def split_topology():
    """Split topology.yaml into modular structure"""

    # Read topology.yaml
    with open('topology.yaml') as f:
        lines = f.readlines()

    # Create topology/ directory
    topology_dir = Path('topology')
    topology_dir.mkdir(exist_ok=True)

    # Define sections to extract (pattern, output filename, header)
    sections = [
        (r'^metadata:', 'metadata.yaml', 'Metadata'),
        (r'^physical_topology:', 'physical.yaml', 'Physical Topology'),
        (r'^logical_topology:', 'logical.yaml', 'Logical Topology'),
        (r'^compute:', 'compute.yaml', 'Compute Resources'),
        (r'^storage:', 'storage.yaml', 'Storage Configuration'),
        (r'^services:', 'services.yaml', 'Services'),
        (r'^ansible:', 'ansible.yaml', 'Ansible Configuration'),
        (r'^workflows:', 'workflows.yaml', 'Workflows'),
        (r'^security:', 'security.yaml', 'Security Configuration'),
        (r'^backup:', 'backup.yaml', 'Backup Configuration'),
        (r'^monitoring:', 'monitoring.yaml', 'Monitoring Configuration'),
        (r'^documentation:', 'documentation.yaml', 'Documentation'),
        (r'^notes:', 'notes.yaml', 'Notes'),
    ]

    # Extract version
    version = '3.0.0'
    for line in lines:
        if line.startswith('version:'):
            version = line.split(':', 1)[1].strip().strip('"\'')
            break

    # Extract each section
    for pattern, filename, title in sections:
        section_lines = extract_section(lines, pattern)

        if section_lines:
            output_path = topology_dir / filename

            # Create header
            header = f"# {title}\n"
            header += f"# Part of Home Lab Topology v{version}\n"
            header += f"# This file is part of the modular topology structure\n"
            header += f"# Edit this file then regenerate: python3 scripts/regenerate-all.py\n"
            header += "\n"

            # Write file
            with open(output_path, 'w') as f:
                f.write(header)
                f.writelines(section_lines)

            # Count lines
            line_count = len([l for l in section_lines if l.strip()])
            print(f"OK Created: {output_path} ({line_count} lines)")

    print(f"\n Split topology into {len(sections)} modular files")
    print(f" Location: topology/")
    print(f"\nNext steps:")
    print(f"  1. Review extracted files in topology/")
    print(f"  2. Backup original: cp topology.yaml topology.yaml.backup")
    print(f"  3. Create new topology.yaml with !include directives")

if __name__ == '__main__':
    split_topology()
