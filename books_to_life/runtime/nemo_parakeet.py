"""CUDA buffered Parakeet Unified with NeMo's per-stream phrase boosting.

Uses APIs from NVIDIA NeMo c2368ab (see requirements/requirements-nemo.txt), following its
speech_to_text_streaming_infer_rnnt.py chunk/context protocol. Incoming audio
alone advances the stream; no whole-file inference or transcript replacement.
"""
import numpy as np

from books_to_life.context.book_context import MAX_CONTEXT_CHARS


def hint_phrases(hotwords):
    if hotwords is None:
        return []
    if not isinstance(hotwords, str) or len(hotwords) > MAX_CONTEXT_CHARS:
        raise ValueError('Hotwords must be bounded text or null.')
    phrases = list(dict.fromkeys(p.strip() for p in hotwords.split(',') if p.strip()))
    if len(phrases) > 32 or any(len(p) > 200 for p in phrases):
        raise ValueError('Use at most 32 phrases, each at most 200 characters.')
    return phrases


def reset_phrase_state(computer, state):
    """Do not reset RNNT prediction history when a phrase vocabulary changes."""
    if state is not None:
        for i, fusion in enumerate(computer._all_fusion_models_with_params()):
            if fusion.is_multi_model:
                state.fusion_states_list[i] = fusion.model.get_init_states(1, bos=False)


def load_model(path, chunk_ms=560, right_ms=560):
    import torch
    from nemo.collections.asr.models import ASRModel
    from nemo.collections.asr.parts.submodules.rnnt_decoding import RNNTDecodingConfig
    from omegaconf import OmegaConf

    if not torch.cuda.is_available():
        raise RuntimeError('This server requires CUDA; CPU fallback is disabled.')
    model = ASRModel.restore_from(str(path), map_location=torch.device('cuda'))
    model.freeze()
    model.eval()
    model.to(device='cuda', dtype=torch.bfloat16)
    model.preprocessor.featurizer.dither = 0.0
    model.preprocessor.featurizer.pad_to = 0
    if model.cfg.encoder.att_context_style != 'chunked_limited_with_rc':
        raise ValueError('Expected the Parakeet Unified buffered streaming model.')
    model.encoder.set_default_att_context_size([70, chunk_ms // 80, right_ms // 80])
    cfg = OmegaConf.structured(RNNTDecodingConfig())
    cfg.strategy = 'greedy_batch'
    cfg.greedy.loop_labels = True
    cfg.greedy.use_cuda_graph_decoder = False
    cfg.greedy.enable_per_stream_biasing = True
    cfg.greedy.preserve_alignments = False
    cfg.fused_batch_size = -1
    model.change_decoding_strategy(cfg)
    return model


class NemoParakeetSession:
    def __init__(self, model, chunk_ms=560, right_ms=560, boost=1.0):
        import torch
        from nemo.collections.asr.parts.utils.streaming_utils import ContextSize, StreamingBatchedAudioBuffer
        self.torch = torch
        self.model = model
        self.computer = model.decoding.decoding.decoding_computer
        self.context = ContextSize(left=89600, chunk=chunk_ms * 16, right=right_ms * 16)
        self.buffer = StreamingBatchedAudioBuffer(1, self.context, torch.float32, model.device)
        self.pending = np.empty(0, dtype=np.float32)
        self.first = True
        self.state = None
        self.hyps = None
        self.text = ''
        self.request = None
        self.phrases = None
        self.boost = boost
        self.bias_ids = torch.tensor([-1], device=model.device, dtype=torch.long)
        self.finalized = False

    def set_hints(self, hotwords):
        from nemo.collections.asr.parts.context_biasing.biasing_multi_model import BiasingRequestItemConfig
        from nemo.collections.asr.parts.context_biasing.boosting_graph_batched import BoostingTreeModelConfig
        phrases = hint_phrases(hotwords)
        if phrases == self.phrases:
            return
        request = None
        if phrases:
            request = BiasingRequestItemConfig(
                boosting_model_cfg=BoostingTreeModelConfig(key_phrases_list=phrases,
                                                          context_score=1.0, depth_scaling=2.0),
                boosting_model_alpha=self.boost,
            )
            request.add_to_multi_model(self.model.tokenizer, self.computer.biasing_multi_model)
        # Retain acoustic/predictor state and emitted tokens. Only the phrase-tree
        # state is invalidated when replacing the vocabulary between chunks.
        try:
            reset_phrase_state(self.computer, self.state)
        except Exception:
            if request is not None:
                request.remove_from_multi_model(self.computer.biasing_multi_model)
            raise
        old_request = self.request
        self.request = request
        self.bias_ids.fill_(request.multi_model_id if request else -1)
        self.phrases = phrases
        if old_request is not None:
            old_request.remove_from_multi_model(self.computer.biasing_multi_model)

    def _decode(self, samples, final=False):
        torch = self.torch
        from nemo.collections.asr.parts.utils.rnnt_utils import batched_hyps_to_hypotheses
        with torch.inference_mode():
            data = torch.from_numpy(samples).to(self.model.device).unsqueeze(0)
            lengths = torch.tensor([len(samples)], device=self.model.device, dtype=torch.long)
            last = torch.tensor([final], device=self.model.device)
            self.buffer.add_audio_batch_(data, lengths, final, last)
            encoded, encoded_len = self.model(input_signal=self.buffer.samples,
                                             input_signal_length=self.buffer.context_size_batch.total())
            context = self.buffer.context_size.subsample(1280)
            context_batch = self.buffer.context_size_batch.subsample(1280)
            encoded = encoded.transpose(1, 2)[:, context.left:]
            decode_len = encoded_len - context_batch.left if final else context_batch.chunk
            if int(decode_len[0]) <= 0:
                return
            hyps, self.state = self.computer(x=encoded, out_len=decode_len,
                                            prev_batched_state=self.state, multi_biasing_ids=self.bias_ids)
            if self.hyps is None:
                self.hyps = hyps
            else:
                self.hyps.merge_(hyps)
            hyp = batched_hyps_to_hypotheses(self.hyps, batch_size=1)[0]
            self.text = self.model.tokenizer.ids_to_text(hyp.y_sequence.tolist())

    def feed(self, samples):
        if self.finalized:
            raise ValueError('Audio stream has already ended.')
        self.pending = np.concatenate((self.pending, samples))
        updates = []
        needed = self.context.chunk + self.context.right if self.first else self.context.chunk
        while len(self.pending) >= needed:
            part, self.pending = self.pending[:needed], self.pending[needed:]
            previous = self.text
            self._decode(part)
            if self.text != previous:
                updates.append(self.text)
            self.first = False
            needed = self.context.chunk
        return updates

    def finish(self):
        if not self.finalized:
            if len(self.pending) or not self.first:
                self._decode(self.pending, final=True)
            self.pending = np.empty(0, dtype=np.float32)
            self.finalized = True
        return self.text

    def close(self):
        if self.request is not None:
            self.request.remove_from_multi_model(self.computer.biasing_multi_model)
            self.request = None
