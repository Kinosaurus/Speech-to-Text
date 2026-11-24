from pathlib import Path
import json
import sys
import argparse
from datetime import datetime

from books_to_life.matching.checkpoint_matcher import CheckpointMatcher, MATCHING_ENGINE
from books_to_life.matching.alignment_matcher import AlignmentMatcher
from books_to_life.matching.evidence_matcher import EvidenceAlignmentMatcher
from books_to_life.matching.split_matcher import SplitEvidenceMatcher
from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.transcript_display import TranscriptEvidence
from books_to_life.runtime.audio_runtime import configure_microphone, input_devices, save_microphone_audio, wait_for_server
from books_to_life.runtime.audio_runtime import microphone_label
from books_to_life.data.recording_library import resolve_recording_path, session_outputs
from books_to_life.context.book_context import BookContext
from books_to_life.runtime.sound_player import SoundPlayer
from books_to_life.runtime.nemo_defaults import NEMO_MODELS


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
    parser.add_argument('--stop-on-stdin-close', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--live-transcript', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--list_input_devices', action='store_true',
                        help='List microphone names and indexes without connecting to the server.')
    parser.add_argument('--input_device', default=None,
                        help='Microphone index or unique part of its name; default uses the OS microphone.')
    parser.add_argument('--audio_chunk', type=int, default=4096,
                        help='Microphone samples per packet at 16 kHz; try 1024 on the Pi (64 ms).')
    parser.add_argument('--connection_timeout', type=float, default=180,
                        help='Maximum seconds to wait for the server and model to become ready.')
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
                          default=None,
                          help='output recording filename, only used for microphone input.')
    parser.add_argument('--transcript_file', default=None,
                        help='Destination for the recognized transcript (SRT).')
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
    recording = parser.add_mutually_exclusive_group()
    recording.add_argument('--save_output_recording', '-r', action='store_true', default=True,
                           help='Save microphone audio (enabled by default).')
    recording.add_argument('--no-save-output-recording', dest='save_output_recording', action='store_false',
                           help='Do not save microphone audio.')
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
    parser.add_argument('--no_book_context', action='store_true',
                        help='Disable automatic book prompts/hotwords; explicit hints still apply.')
    parser.add_argument('--book_context_lookahead', type=int, default=2,
                        help='Future checkpoints included in ASR hints, after the next expected one (default: 2).')
    parser.add_argument('--book_context_words', type=int, default=64,
                        help='Maximum words in the nearby ASR passage prompt (default: 64, range: 8–128).')
    parser.add_argument('--checkpoints',
                          type=str,
                          default=None,
                          help='JSON book manifest with full pages text, checkpoint positions and effect objects.')
    parser.add_argument('--checkpoint_threshold',
                          type=float,
                          default=None,
                          help='Override the manifest similarity threshold from 0 to 100.')
    parser.add_argument('--checkpoint_stability',
                          type=int,
                          default=None,
                          help='Override the number of consecutive matches required to trigger.')
    parser.add_argument('--matching_mode', choices=('alignment', 'evidence', 'split', 'fuzzy'), default='alignment',
                        help='Full-text alignment (default); experimental evidence/split alignment; or fuzzy checkpoint phrases.')
    parser.add_argument('--sound_dir', type=Path,
                        help='Folder containing effect WAVs; defaults to the checkpoint manifest folder.')
    parser.add_argument('--mute_effects', action='store_true', help='Disable story effect sounds.')
    parser.add_argument('--mute-checkpoint-sound', action='append', default=[], metavar='ID',
                        help='Skip a checkpoint sound when another output plays it.')
    parser.add_argument('--sound_volume', type=float, default=0.5, help='Effect volume from 0 to 1 (default: 0.5).')
    parser.add_argument('--sound_output_device', type=int, default=None, help='PortAudio output device index; defaults to OS speakers.')

    args = parser.parse_args()
    if not 0 <= args.sound_volume <= 1:
        parser.error('--sound_volume must be between 0 and 1.')

    session = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    if args.files:
        args.files = [str(resolve_recording_path(path)) for path in args.files]
    default_audio, default_transcript = session_outputs(args.files, session)
    if args.output_file is None:
        args.output_file = str(default_audio)
    if args.transcript_file is None:
        args.transcript_file = str(default_transcript)
    if args.checkpoints:
        args.checkpoints = str(resolve_recording_path(args.checkpoints))
    Path(args.transcript_file).parent.mkdir(parents=True, exist_ok=True)

    native_model = args.model in ('parakeet', 'moonshine', *NEMO_MODELS)
    if native_model:
        if args.model not in NEMO_MODELS and (args.initial_prompt or args.initial_prompt_file or args.hotwords or args.hotwords_file):
            parser.error('Parakeet/Moonshine native runtime does not support prompts or hotwords.')
        if args.translate or args.enable_translation or args.lang != 'en':
            parser.error('Parakeet/Moonshine native runtime supports English transcription only.')
        if args.model in NEMO_MODELS:
            if args.initial_prompt or args.initial_prompt_file:
                parser.error('NeMo models accept --hotwords phrases, not a Whisper passage prompt.')
            print(f'[ASR] {args.model}: phrase boosting supported; Whisper VAD/segment settings do not apply.')
        else:
            args.no_book_context = True
            print('[ASR] Native streaming: book hints disabled; Whisper VAD/segment settings do not apply.')
        if args.files and len(args.files) != 1:
            parser.error('Run one native recording per client invocation.')

    if args.audio_chunk < 256 or args.audio_chunk > 16384:
        parser.error('--audio_chunk must be between 256 and 16384 samples.')
    if not 0 < args.connection_timeout < float('inf'):
        parser.error('--connection_timeout must be positive and finite.')
    if args.list_input_devices:
        import pyaudio
        audio = pyaudio.PyAudio()
        try:
            devices = input_devices(audio)
            for device in devices:
                print(f"{device['index']}: {device['name']} (input channels={device['maxInputChannels']})")
            if not devices:
                print('No microphone inputs found. Connect a USB microphone and check audio permissions.')
        finally:
            audio.terminate()
        sys.exit(0 if devices else 1)

    if not 0.0 <= args.vad_threshold <= 1.0:
        parser.error('--vad_threshold must be between 0 and 1.')
    if args.min_silence_ms < 0 or args.speech_pad_ms < 0:
        parser.error('VAD timing values cannot be negative.')
    if args.same_output_threshold < 1:
        parser.error('--same_output_threshold must be at least 1.')
    if (args.checkpoint_threshold is not None
            and not 0.0 <= args.checkpoint_threshold <= 100.0):
        parser.error('--checkpoint_threshold must be between 0 and 100.')
    if args.checkpoint_stability is not None and args.checkpoint_stability < 1:
        parser.error('--checkpoint_stability must be at least 1.')
    if not 0 <= args.book_context_lookahead <= 10 or not 8 <= args.book_context_words <= 128:
        parser.error('Book context requires --book_context_lookahead 0–10 and --book_context_words 8–128.')

    initial_prompt = read_optional_text(
        parser, args.initial_prompt, args.initial_prompt_file, 'initial_prompt'
    )
    hotwords = read_optional_text(
        parser, args.hotwords, args.hotwords_file, 'hotwords'
    )

    transcription_callback = None
    sound_player = None
    book_context = None
    print(f"[ASR] Requested model={args.model}, language={args.lang}, VAD={not args.no_vad}")
    if args.checkpoints:
        try:
            matcher_type = {'alignment': AlignmentMatcher, 'evidence': EvidenceAlignmentMatcher, 'split': TimelyEvidenceMatcher, 'fuzzy': CheckpointMatcher}[args.matching_mode]
            checkpoint_matcher = matcher_type.from_file(
                args.checkpoints,
                threshold=args.checkpoint_threshold,
                stability=args.checkpoint_stability,
            )
        except ValueError as error:
            parser.error(str(error))

        print(
            f"[CHECKPOINTS] Loaded {len(checkpoint_matcher.checkpoints)} checkpoints "
            f"for '{checkpoint_matcher.title}' using {checkpoint_matcher.mode} ({MATCHING_ENGINE})."
        )
        if not args.mute_effects:
            sound_player = SoundPlayer(checkpoint_matcher.checkpoints, args.checkpoints,
                sound_dir=args.sound_dir, volume=args.sound_volume, output_device=args.sound_output_device)
            print(f'[SOUND] Loaded sounds for {len(sound_player.sounds)} checkpoints.')

        if not args.no_book_context:
            book_context = BookContext(
                checkpoint_matcher, lookahead=args.book_context_lookahead,
                prompt_words=args.book_context_words, initial_prompt=initial_prompt, hotwords=hotwords,
                phrase_only=args.model in NEMO_MODELS,
            )
            initial_prompt, hotwords = book_context.hints.initial_prompt, book_context.hints.hotwords
            print(f"[BOOK_CONTEXT] Automatic hints enabled; lookahead={args.book_context_lookahead}.")
            print(f"[BOOK_CONTEXT] Hotwords: {hotwords or '(none)'}")
            print(f"[BOOK_CONTEXT] Passage prompt: {initial_prompt or '(none)'}")

        transcript_evidence = TranscriptEvidence() if args.live_transcript else None
        if isinstance(checkpoint_matcher, AlignmentMatcher):
            checkpoint_matcher.explain_matches = args.live_transcript

        def handle_transcription(text, segments):
            if args.live_transcript:
                if args.model in NEMO_MODELS and segments and len(segments) == 1:
                    live_text = segments[0]['text']
                elif native_model:
                    # Native backends revise the full transcript on every update.
                    live_text = text
                else:
                    # Whisper sends a rolling window. Keep its committed history
                    # and use the current packet for the unfinished segment.
                    committed = client.client.transcript
                    parts = [segment['text'] for segment in committed]
                    if not segments[-1].get('completed', False):
                        parts.append(segments[-1]['text'])
                    live_text = ' '.join(parts) if parts else text
            else:
                print(f"[TRANSCRIPT] {text}")
            if args.matching_mode in ('alignment', 'evidence', 'split'):
                update = checkpoint_matcher.process(text, segments=segments)
            else:
                update = checkpoint_matcher.process(text)
            if transcript_evidence is not None:
                panel_update = transcript_evidence.update(live_text, getattr(checkpoint_matcher, '_buffer', ()), update)
                checkpoint = checkpoint_matcher.current_checkpoint
                panel_update['reading_checkpoint'] = str(checkpoint['id']) if checkpoint is not None else None
                print('[PANEL_TRANSCRIPT] ' + json.dumps(panel_update), flush=True)
            if book_context:
                hints = book_context.refresh()
                if hints is not None:
                    print(f"[BOOK_CONTEXT] Updated hotwords: {hints.hotwords or '(none)'}")
                    client.client.queue_book_context(hints)
            if update.checkpoint_id is None:
                return
            print(
                f"[MATCH] {update.checkpoint_id} at position {update.checkpoint_position}: "
                f"{update.score:.1f} "
                f"({update.confirmations}/{update.confirmations_required})"
            )
            if args.matching_mode in ('alignment', 'evidence', 'split'):
                print(f"[ALIGN] page={update.page}, words={update.alignment_start}:{update.alignment_end}, "
                      f"confirmed_position={update.tracked_word_position}, recovery={update.recovering}, "
                      f"ambiguous={update.ambiguous}, duplicate={update.duplicate}")
                if update.skipped_checkpoint_ids:
                    print(f"[SKIPPED] {', '.join(update.skipped_checkpoint_ids)}")
            for ident in getattr(update, 'additional_suppressed_checkpoint_ids', ()):
                print(f"[SUPPRESSED] {ident}: pending permission closed before a later checkpoint")
            if getattr(update, 'effect_pending_checkpoint_id', None):
                print(f"[PENDING] {update.effect_pending_checkpoint_id}: waiting for a complete endpoint")
            if getattr(update, 'effect_suppressed', False):
                print(f"[SUPPRESSED] {update.checkpoint_id}: {update.effect_suppression_reason}")
            if update.triggered:
                effect = json.dumps(update.effect, ensure_ascii=False)
                print(f"[TRIGGER] {update.checkpoint_id}: {effect}")
                if sound_player and update.checkpoint_id not in args.mute_checkpoint_sound:
                    sound_player.handle_update(update)
            if update.completed:
                print("[CHECKPOINTS] All story checkpoints completed.")

        transcription_callback = handle_transcription

    if args.translate and args.enable_translation:
        print("[WARN]: Both --translate and --enable_translation are set. "
              "--translate uses Whisper's built-in to-English translation, "
              "while --enable_translation uses M2M100 for any-to-any. "
              "Both will be active.")

    if native_model:
        from books_to_life.runtime.native_stream_client import NativeTranscriptionClient as TranscriptionClient
    elif book_context:
        from books_to_life.context.book_context_client import BookTranscriptionClient as TranscriptionClient
    else:
        from whisper_live.client import TranscriptionClient
    print(f'[SERVER] ws://{args.server}:{args.port}')
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
        transcription_callback=transcription_callback,
        output_transcription_path=args.transcript_file,
        mute_audio_playback=args.mute_audio_playback,      # Only used for file input, False by Default
        enable_translation=args.enable_translation,        # Enable translation of the transcription output
        target_language=args.target_language,              # Target language for translation, e.g., "fr
        enable_timestamps=args.enable_timestamps,
        display_segments=args.n_display_segments,
    )

    if args.files is None:
        if args.stop_on_stdin_close:
            import _thread
            from threading import Event, Thread

            stopping = Event()
            capturing = Event()
            def stop_when_parent_closes():
                sys.stdin.buffer.read(1)
                stopping.set()
                if capturing.is_set():
                    _thread.interrupt_main()

            Thread(target=stop_when_parent_closes, daemon=True).start()
        else:
            stopping = None

        try:
            microphone = configure_microphone(client, args.input_device, args.audio_chunk)
            print(f'[MICROPHONE] {microphone_label(client.p, microphone)}', flush=True)
            print(f"[AUDIO] Capture rate={client.rate} Hz, channels={client.channels}")
            print(f'[AUDIO] Packet duration={1000 * client.chunk / client.rate:g} ms')
            wait_for_server(client, args.connection_timeout, stopping)
            if stopping is not None and stopping.is_set():
                if sound_player:
                    sound_player.close()
                client.close_all_clients()
                if client.stream is not None:
                    client.stream.close()
                client.p.terminate()
                sys.exit(0)
        except (OSError, ValueError, ConnectionError, TimeoutError) as error:
            if sound_player:
                sound_player.close()
            client.close_all_clients()
            if client.stream is not None:
                client.stream.close()
            client.p.terminate()
            parser.exit(1, f'[STARTUP] {error}\n')
        try:
            with save_microphone_audio(client, args.output_file if args.save_output_recording else None):
                if args.stop_on_stdin_close:
                    capturing.set()
                    if stopping.is_set():
                        raise KeyboardInterrupt
                    print('[SESSION] Listening', flush=True)
                client()
        except KeyboardInterrupt:
            if not args.stop_on_stdin_close or not stopping.is_set():
                raise
        except BaseException:
            if sound_player:
                sound_player.close()
            raise
        if sound_player:
            # WhisperLive consumes Ctrl+C internally when microphone capture ends.
            sound_player.close()
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
        if sound_player:
            sound_player.close()
        sys.exit(1)

    print(f"Found {len(valid_files)} audio file(s) to stream:")
    for file_path in valid_files:
        print(f"  - {file_path}")

    try:
        wait_for_server(client, args.connection_timeout)
    except (ConnectionError, TimeoutError) as error:
        if sound_player:
            sound_player.close()
        client.close_all_clients()
        if client.stream is not None:
            client.stream.close()
        client.p.terminate()
        parser.exit(1, f'[STARTUP] {error}\n')
    try:
        for f in valid_files:
            client(f)
    except BaseException:
        if sound_player:
            sound_player.close()
        raise
    if sound_player:
        sound_player.close(drain=True)
