# Books to Life Pod

This app listens to a child reading aloud, follows their place in a story, and
triggers checkpoints for visuals and sound.

Start with [current progress and tested commands](docs/PROJECT_STATUS.md).
For model choices, deployment options, and why the pilot setup was selected,
see [setups and tradeoffs](docs/SETUPS.md).
For installation and running the app, use the [running guide](docs/RUNNING.md).
Run commands from this project folder, even when reading a guide inside `docs/`.

## Where things belong

| Location | What it is for |
| --- | --- |
| `books_to_life/cli/run_client.py` | Send microphone or recorded audio to a speech server. |
| `books_to_life/cli/run_server.py` | Start the Whisper speech server. |
| `books_to_life/cli/run_native_server.py` | Start Parakeet or Moonshine. |
| `books_to_life/cli/run_nemo_server.py` | Start the NeMo Parakeet server in Linux/WSL. |
| `books_to_life/cli/prepare_models.py`, `books_to_life/cli/prepare_nemo_model.py` | Download and check speech models. |
| `books_to_life/cli/checkpoint_demo.py` | Try story checkpoints without running speech recognition. |
| `books_to_life/matching/` | Story alignment and checkpoint tracking. |
| `books_to_life/runtime/` | Audio input, speech devices, and model adapters. |
| `books_to_life/context/` | Book phrase hints and client/server transport. |
| `books_to_life/data/` | Recording library access. |
| [docs/](docs/README.md) | Setup guides, project notes, status, and diagrams. |
| `requirements/` | Dependency lists for specific clients, servers, and platforms. |
| `Dockerfile*`, `compose*.yaml`, `.env.*.example` | Container builds and platform settings. |
| [recordings/](recordings/README.md) | Audio library, passages, transcripts, and checkpoints. |
| [benchmarks/](benchmarks/README.md) | Evaluation scripts and published result summaries. |
| `tests/` | Automated checks. Run `.\.venv\Scripts\python.exe -m unittest discover -s tests`. |
| `output/` | Generated transcripts, logs, experiment runs, and presentation exports. |
| `archives/` | Preserved source bundles, including the original `recordings.zip`. |
| `model-cache/` | Downloaded speech models; keep to avoid downloading them again. |
| `.venv/` | Installed local Python environment. |
| `__pycache__/` | Automatically generated Python bytecode. |

Keep new guides in `docs/`, experiment tools in `benchmarks/`, and generated
files in `output/`. Container configuration stays at the root.

## Running after the cleanup

Python files now live in a package. From the project root, use `python -m`:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --help
.\.venv\Scripts\python.exe -m books_to_life.cli.run_server --help
.\.venv\Scripts\python.exe -m books_to_life.cli.checkpoint_demo
```

For an old command such as `python run_client.py --model ...`, replace
`run_client.py` with `-m books_to_life.cli.run_client` and keep the same options.
The same pattern applies to the other launchers in `books_to_life/cli/`.
