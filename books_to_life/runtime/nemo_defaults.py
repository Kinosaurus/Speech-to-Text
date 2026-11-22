"""Shared NeMo launch defaults; explicit server CLI flags can override buffers."""

CHUNK_MS = 160
RIGHT_MS = 560
MIC_PACKET_SAMPLES = 1280
NEMO_MODELS = ('parakeet-nemo', 'nemotron')


def microphone_arguments(model):
    return ['--audio_chunk',str(MIC_PACKET_SAMPLES)] if model in NEMO_MODELS else []
