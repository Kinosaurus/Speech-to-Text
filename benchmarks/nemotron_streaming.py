"""Cache-aware Nemotron session for the paired benchmark.

Follows installed NeMo CacheAwareStreamingAudioBuffer / conformer_stream_step.
Only received audio is preprocessed. Centered STFT frames whose right window
is not yet available are withheld until a later packet or EOF. Prefix feature
recomputation is deliberately simple; its cost IS included in measured latency.
No whole-file recognition or future-audio feature normalization is performed.
"""
import numpy as np


def load_model(path, chunk_ms=560, *, enable_hints=False):
    import torch
    from nemo.collections.asr.models import ASRModel
    from nemo.collections.asr.parts.submodules.rnnt_decoding import RNNTDecodingConfig
    from omegaconf import OmegaConf
    contexts = {80: 0, 160: 1, 560: 6, 1120: 13}
    if chunk_ms not in contexts:
        raise ValueError('Nemotron chunk_ms must be 80, 160, 560 or 1120')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    model = ASRModel.restore_from(str(path), map_location=torch.device('cuda'))
    model.freeze()
    model.eval()
    model.to(device='cuda', dtype=torch.bfloat16)
    if model.cfg.encoder.att_context_style != 'chunked_limited':
        raise ValueError('Expected cache-aware chunked Nemotron')
    if str(model.cfg.preprocessor.normalize).lower() not in ('na', 'none'):
        raise ValueError('Benchmark requires features without whole-utterance normalization')
    model.preprocessor.featurizer.dither = 0.0
    model.preprocessor.featurizer.pad_to = 0
    model.encoder.set_default_att_context_size([70, contexts[chunk_ms]])
    cfg = OmegaConf.structured(RNNTDecodingConfig())
    cfg.strategy = 'greedy_batch'
    cfg.greedy.loop_labels = True
    cfg.greedy.use_cuda_graph_decoder = False
    cfg.greedy.preserve_alignments = False
    cfg.greedy.enable_per_stream_biasing = enable_hints
    cfg.fused_batch_size = -1
    model.change_decoding_strategy(cfg)
    return model


class NemotronSession:
    def __init__(self, model, *, phrases=(), boost=1.0):
        from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer
        self.model = model
        self.buffer = CacheAwareStreamingAudioBuffer(model, online_normalization=False)
        self.raw = np.empty(0, dtype=np.float32)
        self.cache_channel, self.cache_time, self.cache_length = model.encoder.get_initial_cache_state(batch_size=1)
        self.previous_hypotheses = None
        self.previous_pred = None
        self.text = ''
        self.finalized = False
        self.processed_frames = 0
        self._biasing_request = None
        self._hint_phrases = ()
        self._hint_boost = boost
        self.set_hints(phrases)

    def set_hints(self, phrases):
        """Replace the phrase graph between calls, retaining the live hypothesis."""
        phrases = tuple(phrases)
        if phrases == self._hint_phrases:
            return False
        if self.finalized:
            raise ValueError('Cannot change hints after the stream ends.')
        from nemo.collections.asr.parts.context_biasing.biasing_multi_model import BiasingRequestItemConfig
        from nemo.collections.asr.parts.context_biasing.boosting_graph_batched import BoostingTreeModelConfig
        from nemo.collections.asr.parts.utils.rnnt_utils import Hypothesis

        computer = self.model.decoding.decoding.decoding_computer
        if not computer.per_stream_biasing_enabled:
            raise ValueError('Load the Nemotron model with enable_hints=True before supplying phrases.')
        graph = computer.biasing_multi_model
        request = None
        if phrases:
            request = BiasingRequestItemConfig(
                boosting_model_cfg=BoostingTreeModelConfig(key_phrases_list=list(phrases),
                                                           context_score=1.0, depth_scaling=2.0),
                boosting_model_alpha=self._hint_boost,
                auto_manage_multi_model=False,
            )
            request.add_to_multi_model(self.model.tokenizer, graph)
        try:
            if self.previous_hypotheses is None:
                self.previous_hypotheses = [Hypothesis.empty_with_biasing_cfg(request)]
            else:
                hypothesis = self.previous_hypotheses[0]
                state = hypothesis.dec_state
                if state is not None:
                    # The old graph node IDs are invalid in the new graph.
                    # Keep encoder caches, RNNT predictor state and past tokens.
                    for index, fusion in enumerate(computer._all_fusion_models_with_params()):
                        if fusion.is_multi_model:
                            state.fusion_state_list[index] = fusion.model.get_init_states(1, bos=False)[0]
                hypothesis.biasing_cfg = request
        except Exception:
            if request is not None:
                request.remove_from_multi_model(graph)
            raise
        old_request = self._biasing_request
        self._biasing_request = request
        self._hint_phrases = phrases
        if old_request is not None:
            old_request.remove_from_multi_model(graph)
        return True

    def _drain(self, final=False):
        import torch
        if len(self.raw) < 512:
            return []
        features, lengths = self.buffer.preprocess_audio(self.raw)
        # n_fft=512, hop=160. This excludes the reflected right boundary of
        # live prefix STFTs; the original EOF uses the normal NeMo reflection.
        # The reference buffer uses the complete feature tensor at EOF, which
        # can include one more centered STFT frame than preprocessor lengths.
        # Omitting it can shorten the final 160 ms chunk by one feature frame.
        stable = features.size(-1) if final else min(int(lengths[0]), max(0, (len(self.raw)-256)//160+1))
        self.buffer.buffer = features[:, :, :stable]
        self.buffer.streams_length = torch.tensor([stable], device=features.device)
        updates = []
        while self.buffer.buffer_idx < stable:
            sizes = self.buffer.streaming_cfg.chunk_size
            needed = sizes[0 if self.buffer.buffer_idx == 0 else 1] if isinstance(sizes, list) else sizes
            if not final and self.buffer.buffer_idx+needed > stable:
                break
            step = self.buffer.step
            chunk = next(iter(self.buffer), None)
            if chunk is None:
                break
            data, length = chunk
            result = self.model.conformer_stream_step(
                processed_signal=data, processed_signal_length=length,
                cache_last_channel=self.cache_channel, cache_last_time=self.cache_time,
                cache_last_channel_len=self.cache_length,
                keep_all_outputs=final and self.buffer.is_buffer_empty(),
                previous_hypotheses=self.previous_hypotheses,
                previous_pred_out=self.previous_pred,
                drop_extra_pre_encoded=0 if step == 0 else self.model.encoder.streaming_cfg.drop_extra_pre_encoded,
                return_transcription=True)
            (self.previous_pred, hypotheses, self.cache_channel, self.cache_time,
             self.cache_length, self.previous_hypotheses) = result
            text = hypotheses[0].text
            if text != self.text:
                self.text = text
                updates.append(text)
            self.processed_frames = min(self.buffer.buffer_idx, stable)
        return updates

    def feed(self, samples):
        if self.finalized:
            raise ValueError('Audio stream has ended')
        self.raw = np.concatenate((self.raw, samples))
        return self._drain()

    def finish(self):
        if not self.finalized:
            self._drain(final=True)
            self.finalized = True
        return self.text

    def close(self):
        if self._biasing_request is not None:
            computer = self.model.decoding.decoding.decoding_computer
            self._biasing_request.remove_from_multi_model(computer.biasing_multi_model)
            self._biasing_request = None
