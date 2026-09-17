from pathlib import Path
import sys
from whisper_live.client import TranscriptionClient
import argparse


def read_optional_text(parser, inline_value, file_value, label):
    """Return an inline value or UTF-8 file contents, but never both."""
    if inline_value and file_value:
        parser.error(f"Use either --{label} or --{label}_file, not both.")
    if file_value:
        path = Path(file_value)
        if not path.is_file():
            parser.error(f"{label.replace('_', ' ').title()} file not found: {path}")
        return path.read_text(encoding='utf-8').strip()
    return inline_value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', '-p',
                          type=int,
                          default=9090,
                          help="Websocket port to run the server on.")
    parser.add_argument('--server', '-s',
                          type=str,
                          default='localhost',
                          help='hostname or ip address of server')
    parser.add_argument('--files', '-f',
                          type=str,
                          nargs='+',
                          help='Files to transcribe, separated by spaces. '
                              'If not provided, will use microphone input.')
    parser.add_argument('--output_file', '-o',
                          type=str,
                          default='./output_recording.wav',
                          help='output recording filename, only used for microphone input.')
    parser.add_argument('--model', '-m',
                          type=str,
                          default='base.en',
                          help='Model to use. base.en is the default low-latency English profile; tiny.en is faster.')
    parser.add_argument('--lang', '-l',
                          type=str,
                          default='en',
                          help='Language code for transcription, e.g., "en" for English.')
    parser.add_argument('--translate', '-t',
                          action='store_true',
                          help='Use Whisper built-in translation to English (sets task=translate). '
                              'For any-to-any translation, use --enable_translation instead.')
    parser.add_argument('--mute_audio_playback', '-a',
                          action='store_true',
                          help='Mute audio playback during transcription.') 
    parser.add_argument('--save_output_recording', '-r',
                          action='store_true',
                          help='Save the output recording, only used for microphone input.')
    parser.add_argument('--enable_translation',
                          action='store_true',
                          help='Enable any-to-any translation via M2M100 model (separate from Whisper --translate).')
    parser.add_argument('--target_language', '-tl',
                          type=str,
                          default='fr',
                          help='Target language for translation, e.g., "fr" for French.')
    parser.add_argument('--enable_timestamps',
                          action='store_true',
                          help='Show transcription with timestamps')
    parser.add_argument('--n_display_segments',
                          type=int,
                          default=4,
                          help='Number of transcript segments to display in terminal (default: 4).')
    parser.add_argument('--no_vad',
                          action='store_true',
                          help='Disable voice activity detection. Usually keep VAD enabled for a reading pod.')
    parser.add_argument('--vad_threshold',
                          type=float,
                          default=0.5,
                          help='Silero VAD speech threshold from 0 to 1 (default: 0.5).')
    parser.add_argument('--min_silence_ms',
                          type=int,
                          default=160,
                          help='Silence that ends a speech chunk, in milliseconds (default: 160).')
    parser.add_argument('--speech_pad_ms',
                          type=int,
                          default=120,
                          help='Audio padding around detected speech, in milliseconds (default: 120).')
    parser.add_argument('--same_output_threshold',
                          type=int,
                          default=3,
                          help='Repeated hypotheses before committing a segment. Lower is faster but less stable (default: 3).')
    parser.add_argument('--initial_prompt',
                          type=str,
                          default=None,
                          help='Short passage or context that is expected next.')
    parser.add_argument('--initial_prompt_file',
                          type=str,
                          default=None,
                          help='UTF-8 file containing the short passage expected next.')
    parser.add_argument('--hotwords',
                          type=str,
                          default=None,
                          help='Comma-separated story names or unusual vocabulary to bias recognition.')
    parser.add_argument('--hotwords_file',
                          type=str,
                          default=None,
                          help='UTF-8 file containing comma-separated story vocabulary.')

    args = parser.parse_args()

    if not 0.0 <= args.vad_threshold <= 1.0:
        parser.error('--vad_threshold must be between 0 and 1.')
    if args.min_silence_ms < 0 or args.speech_pad_ms < 0:
        parser.error('VAD timing values cannot be negative.')
    if args.same_output_threshold < 1:
        parser.error('--same_output_threshold must be at least 1.')

    initial_prompt = read_optional_text(
        parser, args.initial_prompt, args.initial_prompt_file, 'initial_prompt'
    )
    hotwords = read_optional_text(
        parser, args.hotwords, args.hotwords_file, 'hotwords'
    )

    if args.translate and args.enable_translation:
        print("[WARN]: Both --translate and --enable_translation are set. "
              "--translate uses Whisper's built-in to-English translation, "
              "while --enable_translation uses M2M100 for any-to-any. "
              "Both will be active.")

    client = TranscriptionClient(
        args.server,
        args.port,
        lang=args.lang,
        translate=args.translate,
        model=args.model,                                  # also support hf_model => `Systran/faster-whisper-small`
        use_vad=not args.no_vad,
        vad_parameters={
            'threshold': args.vad_threshold,
            'min_silence_duration_ms': args.min_silence_ms,
            'speech_pad_ms': args.speech_pad_ms,
        },
        same_output_threshold=args.same_output_threshold,
        initial_prompt=initial_prompt,
        hotwords=hotwords,
        save_output_recording=args.save_output_recording,  # Only used for microphone input, False by Default
        output_recording_filename=args.output_file,        # Only used for microphone input
        mute_audio_playback=args.mute_audio_playback,      # Only used for file input, False by Default
        enable_translation=args.enable_translation,        # Enable translation of the transcription output
        target_language=args.target_language,              # Target language for translation, e.g., "fr
        enable_timestamps=args.enable_timestamps,
        display_segments=args.n_display_segments,
    )

    if args.files is None:
        client()
        sys.exit(0)

    # Validate audio files
    valid_files = []
    for file_path in args.files:
        path = Path(file_path)
        if path.exists() and path.is_file():
            valid_files.append(str(path))
        else:
            print(f"Warning: File not found: {file_path}")

    if not valid_files:
        print("Error: No valid audio files found!")
        sys.exit(1)

    print(f"Found {len(valid_files)} audio file(s) to stream:")
    for file_path in valid_files:
        print(f"  - {file_path}")

    for f in valid_files:
        client(f)
