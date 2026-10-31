# Project guide

All terminal commands in these guides assume the project root is your current folder.

## Guides

- [Setups and tradeoffs](SETUPS.md): recommended pilot, alternatives, and reasons for each choice.
- [Current status](PROJECT_STATUS.md): implemented behavior, verified results, and remaining work.
- [Install and run](RUNNING.md): Windows, WSL, model preparation, clients, and servers.
- [Jetson setup](JETSON_SETUP.md) and [Raspberry Pi setup](PI4_SETUP.md): board deployment.
- [Low-storage testing](LOW_STORAGE_TESTING.md): smaller local test configurations.
- [Project brief](PROJECT_BRIEF.md): purpose, scope, and technical direction.
- [Pod notes](BOOKS_TO_LIFE_POD_NOTES.md): supporting project notes.
- `diagrams/`: editable application flow diagrams (`.drawio`) and checkpoint flow (`.mmd`).

## Code map

| Package files | Responsibility |
| --- | --- |
| `books_to_life/cli/run_*.py` | Command-line launchers for the client and speech servers. |
| `books_to_life/runtime/audio_runtime.py`, `books_to_life/runtime/asr_runtime.py` | Audio input and speech-device configuration. |
| `books_to_life/runtime/native_stream_client.py`, `books_to_life/runtime/nemo_parakeet.py` | Native-model transport and NeMo integration. |
| `books_to_life/context/book_context*.py` | Book phrase hints and their client/server transport. |
| `books_to_life/matching/checkpoint_matcher.py`, `books_to_life/matching/alignment_matcher.py` | Checkpoint matching and story alignment. |
| `books_to_life/matching/boundary_matcher.py`, `books_to_life/matching/evidence_matcher.py`, `books_to_life/matching/split_matcher.py`, `books_to_life/matching/timely_matcher.py` | Alternative tracking strategies compared by the benchmarks. |
| `books_to_life/data/recording_library.py` | Access to the organized recording library. |
| `books_to_life/cli/prepare_*.py` | Model preparation. |
| `books_to_life/cli/checkpoint_demo.py` | Standalone checkpoint demo. |

## Cleanup notes

Setup guides and diagrams were gathered here from the project root. Platform
dependency files moved to `requirements/`; the default `requirements.txt` stays
at the root. The original audio ZIP moved to `archives/recordings.zip` without
changing its contents. Recordings, models, environments, and historical outputs
were preserved in place.

All application Python code lives under `books_to_life/`. Run launchers from the
project root using `python -m books_to_life.cli.<module>`; do not launch a nested
file directly. Imports, tests, benchmarks, and container commands use the package.
