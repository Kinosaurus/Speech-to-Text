"""Configure inference before importing Torch or WhisperLive."""

import os


def configure_device(device):
    if device == 'cpu':
        # The upstream backend chooses its device via torch.cuda.is_available().
        # Mask CUDA before Torch is imported so laptop tests use the Pi CPU path.
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    elif device not in ('auto', 'cuda'):
        raise ValueError(f'Unsupported inference device: {device}')


def describe_device(device, torch_module, ct2_module):
    cuda = torch_module.cuda.is_available()
    if device == 'cuda' and not cuda:
        raise ValueError('CUDA was requested but is unavailable. Check the NVIDIA driver and CUDA-enabled PyTorch installation.')
    selected = 'cuda' if cuda and device != 'cpu' else 'cpu'
    precision = 'int8'
    if selected == 'cuda':
        precision = 'float16' if torch_module.cuda.get_device_capability()[0] >= 7 else 'float32'
    try:
        if selected == 'cuda' and ct2_module.get_cuda_device_count() < 1:
            raise ValueError('PyTorch sees CUDA but CTranslate2 does not. Check its CUDA-enabled build and GPU libraries.')
        supported = ct2_module.get_supported_compute_types(selected)
    except RuntimeError as error:
        raise ValueError(f'CTranslate2 cannot initialize {selected}: {error}') from error
    if precision not in supported:
        raise ValueError(f'This CTranslate2 build does not support {precision} on {selected}. '
                         'Check the backend build and CUDA/cuDNN versions for GPU inference.')
    return selected, precision
