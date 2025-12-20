#!/usr/bin/env python3
import os
import shutil
import sys

def main():
    """Initialize the configuration file from the template."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, 'config.py')
    template_path = os.path.join(project_root, 'config.template.py')

    if not os.path.exists(template_path):
        print(f"Error: Template file not found at {template_path}")
        sys.exit(1)

    if os.path.exists(config_path):
        print(f"Configuration file already exists at {config_path}")
        print("Skipping initialization to avoid overwriting existing config.")
    else:
        try:
            shutil.copy2(template_path, config_path)
            print(f"Successfully created config.py from template.")
            print(f"Please edit {config_path} with your specific configuration.")
        except IOError as e:
            print(f"Error creating config.py: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
