#!/usr/bin/env bash
set -euo pipefail

python3 -m venv "$HOME/.venvs/books-to-life-nemo"
python="$HOME/.venvs/books-to-life-nemo/bin/python"
"$python" -m pip install --upgrade pip
"$python" -m pip install --no-cache-dir -r requirements/requirements-nemo.txt
"$python" -c 'import torch; assert torch.cuda.is_available(), "CUDA is unavailable in this WSL distro"; print(torch.cuda.get_device_name())'
"$python" -m books_to_life.cli.prepare_nemotron_model
