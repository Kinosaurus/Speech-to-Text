from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from books_to_life.runtime.nemotron import reset_hint_state


class NemotronHintTests(unittest.TestCase):
    def test_graph_change_resets_individual_fusion_state_and_keeps_predictor(self):
        predictor, other, fresh = object(), object(), object()
        tree = Mock()
        tree.get_init_states.return_value = [fresh]
        computer = Mock()
        computer._all_fusion_models_with_params.return_value = [
            SimpleNamespace(is_multi_model=False), SimpleNamespace(is_multi_model=True,model=tree)]
        state = SimpleNamespace(predictor_state=predictor,fusion_state_list=[other,object()])
        reset_hint_state(computer,state)
        self.assertIs(state.predictor_state,predictor)
        self.assertIs(state.fusion_state_list[0],other)
        self.assertIs(state.fusion_state_list[1],fresh)
        tree.get_init_states.assert_called_once_with(1,bos=False)

    def test_graph_change_before_any_audio_has_no_decoder_state_to_reset(self):
        computer = Mock()
        reset_hint_state(computer,None)
        computer._all_fusion_models_with_params.assert_not_called()


if __name__ == '__main__':
    unittest.main()
