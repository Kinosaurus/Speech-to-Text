"""Cache the stock Whisper and VAD models before an offline reading session."""

import argparse
import time

from books_to_life.runtime.asr_runtime import configure_device, describe_device


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=('tiny.en', 'base.en', 'small.en', 'medium.en'), default='base.en')
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='cpu')
    parser.add_argument('--verify_inference', action='store_true',
                        help='Run a synthetic silent input to verify model loading and ASR kernels; not an accuracy test.')
    args = parser.parse_args()
    configure_device(args.device)
    import torch
    import ctranslate2
    try:
        device, precision = describe_device(args.device, torch, ctranslate2)
    except ValueError as error:
        parser.error(str(error))
    # Same loaders/cache paths as the packaged WhisperLive faster-whisper backend.
    from whisper_live.transcriber.transcriber_faster_whisper import WhisperModel
    from whisper_live.vad import VoiceActivityDetector
    print(f'[PREPARE] Downloading/loading {args.model} on {device} ({precision}).', flush=True)
    model = WhisperModel(args.model, device=device, compute_type=precision, cpu_threads=2)
    VoiceActivityDetector()
    if args.verify_inference:
        import numpy as np
        started = time.perf_counter()
        segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language='en',
                                      beam_size=1, condition_on_previous_text=False)
        list(segments)
        print(f'[VERIFY] Synthetic ASR inference passed on {device} in '
              f'{time.perf_counter() - started:.2f}s. This is not reading latency or accuracy.', flush=True)
    print('[PREPARE] Whisper and VAD are cached. Keep the model-cache volume.', flush=True)


if __name__ == '__main__':
    main()
