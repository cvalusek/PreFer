#!/usr/bin/env bash
set -euo pipefail

readonly SGLANG_GENERATED_MODEL_KEYS="qwen-3.8-27b-nvfp4"
GENERATED_MODEL_KEYS=$SGLANG_GENERATED_MODEL_KEYS
LEGACY_SMALL_MODELS=$SGLANG_GENERATED_MODEL_KEYS

model_key_fingerprint() {
  case "$1" in
  minimax-h3-fl2va-int8-convrot) printf '%s\n' 45bf26078343977c9cf1c732a2f2e5ff5940ae5c2968fa9f0638df5adc255cbe ;;
  minimax-h3-ref2va-int8-convrot) printf '%s\n' 9e2c8ed8e1b63ded5c76a2870395c3b3b765d2efe456bd35fd2c452558c0399e ;;
  qwen-3.8-27b-nvfp4) printf '%s\n' 510de70a8bdfa5363430bba4fe345730579aed08ab48c3c0656f54cfd097cb4f ;;
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

model_key_artifacts() {
  case "$1" in
  minimax-h3-fl2va-int8-convrot)
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/config.yaml"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_activations.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_alias_free_act.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_alias_free_filter.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_alias_free_resample.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_attn_proj.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_audio_vae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_bigvgan.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_utils.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/metadata.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/minimax_h3_audio_vae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/model_index.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/chat_template.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/merges.txt"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/tokenizer.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/tokenizer_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/video_preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/processor/vocab.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/chat_template.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/merges.txt"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/tokenizer.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/tokenizer_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/video_preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/vocab.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/merges.txt"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/tokenizer.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/tokenizer_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/vocab.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/transformer/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/attention.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/base_module.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/conv.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/flash.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/func.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/klvae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/minimax_h3_video_vae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/norm.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/normalize.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/parallel.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/source/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/utils.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_cnn.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_module.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_processor.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_vit.py"
      printf '%s\n' "Comfy-Org/MiniMax-H3/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
      printf '%s\n' "Comfy-Org/MiniMax-H3/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
      printf '%s\n' "Comfy-Org/MiniMax-H3/vae/minimax_h3_audio_vae_fp32.safetensors"
      printf '%s\n' "Comfy-Org/MiniMax-H3/vae/minimax_h3_video_vae_fp16.safetensors"
      ;;
  minimax-h3-ref2va-int8-convrot)
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/config.yaml"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_activations.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_alias_free_act.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_alias_free_filter.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_alias_free_resample.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_attn_proj.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_audio_vae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_bigvgan.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_utils.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/metadata.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/minimax_h3_audio_vae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/model_index.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/chat_template.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/merges.txt"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/tokenizer.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/tokenizer_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/video_preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/processor/vocab.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/chat_template.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/merges.txt"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/tokenizer.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/tokenizer_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/video_preprocessor_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/vocab.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/merges.txt"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/tokenizer.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/tokenizer_config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/vocab.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/transformer/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/attention.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/base_module.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/conv.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/flash.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/func.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/klvae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/minimax_h3_video_vae.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/norm.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/normalize.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/parallel.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/source/config.json"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/utils.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_cnn.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_module.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_processor.py"
      printf '%s\n' "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_vit.py"
      printf '%s\n' "Comfy-Org/MiniMax-H3/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
      printf '%s\n' "Comfy-Org/MiniMax-H3/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
      printf '%s\n' "Comfy-Org/MiniMax-H3/vae/minimax_h3_audio_vae_fp32.safetensors"
      printf '%s\n' "Comfy-Org/MiniMax-H3/vae/minimax_h3_video_vae_fp16.safetensors"
      ;;
  qwen-3.8-27b-nvfp4)
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/chat_template.jinja"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/generation_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/hf_quant_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/merges.txt"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model-00001-of-00003.safetensors"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model-00002-of-00003.safetensors"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model-00003-of-00003.safetensors"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model.safetensors.index.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/preprocessor_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/tokenizer.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/tokenizer_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/video_preprocessor_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/vocab.json"
      ;;
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

model_key_artifact_records() {
  case "$1" in
  minimax-h3-fl2va-int8-convrot)
      printf '%s\t%s\n' 1973 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/config.json"
      printf '%s\t%s\n' 91 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/config.yaml"
      printf '%s\t%s\n' 2189 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_activations.py"
      printf '%s\t%s\n' 835 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_alias_free_act.py"
      printf '%s\t%s\n' 3300 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_alias_free_filter.py"
      printf '%s\t%s\n' 1740 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_alias_free_resample.py"
      printf '%s\t%s\n' 3317 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_attn_proj.py"
      printf '%s\t%s\n' 7266 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_audio_vae.py"
      printf '%s\t%s\n' 7102 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_bigvgan.py"
      printf '%s\t%s\n' 362 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/dac_utils.py"
      printf '%s\t%s\n' 440 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/metadata.json"
      printf '%s\t%s\n' 3532 "MiniMaxAI/MiniMax-H3/FL2VA/audio_vae/minimax_h3_audio_vae.py"
      printf '%s\t%s\n' 719 "MiniMaxAI/MiniMax-H3/FL2VA/model_index.json"
      printf '%s\t%s\n' 5499 "MiniMaxAI/MiniMax-H3/FL2VA/processor/chat_template.json"
      printf '%s\t%s\n' 1671839 "MiniMaxAI/MiniMax-H3/FL2VA/processor/merges.txt"
      printf '%s\t%s\n' 390 "MiniMaxAI/MiniMax-H3/FL2VA/processor/preprocessor_config.json"
      printf '%s\t%s\n' 7032403 "MiniMaxAI/MiniMax-H3/FL2VA/processor/tokenizer.json"
      printf '%s\t%s\n' 11003 "MiniMaxAI/MiniMax-H3/FL2VA/processor/tokenizer_config.json"
      printf '%s\t%s\n' 385 "MiniMaxAI/MiniMax-H3/FL2VA/processor/video_preprocessor_config.json"
      printf '%s\t%s\n' 2776833 "MiniMaxAI/MiniMax-H3/FL2VA/processor/vocab.json"
      printf '%s\t%s\n' 5499 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/chat_template.json"
      printf '%s\t%s\n' 1474 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/config.json"
      printf '%s\t%s\n' 1671839 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/merges.txt"
      printf '%s\t%s\n' 390 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/preprocessor_config.json"
      printf '%s\t%s\n' 7032403 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/tokenizer.json"
      printf '%s\t%s\n' 11003 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/tokenizer_config.json"
      printf '%s\t%s\n' 385 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/video_preprocessor_config.json"
      printf '%s\t%s\n' 2776833 "MiniMaxAI/MiniMax-H3/FL2VA/text_encoder/vocab.json"
      printf '%s\t%s\n' 1671839 "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/merges.txt"
      printf '%s\t%s\n' 7032403 "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/tokenizer.json"
      printf '%s\t%s\n' 11003 "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/tokenizer_config.json"
      printf '%s\t%s\n' 2776833 "MiniMaxAI/MiniMax-H3/FL2VA/tokenizer/vocab.json"
      printf '%s\t%s\n' 604 "MiniMaxAI/MiniMax-H3/FL2VA/transformer/config.json"
      printf '%s\t%s\n' 5785 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/attention.py"
      printf '%s\t%s\n' 9520 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/base_module.py"
      printf '%s\t%s\n' 1807 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/config.json"
      printf '%s\t%s\n' 4487 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/conv.py"
      printf '%s\t%s\n' 5763 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/flash.py"
      printf '%s\t%s\n' 5840 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/func.py"
      printf '%s\t%s\n' 48594 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/klvae.py"
      printf '%s\t%s\n' 5123 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/minimax_h3_video_vae.py"
      printf '%s\t%s\n' 10686 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/norm.py"
      printf '%s\t%s\n' 1200 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/normalize.py"
      printf '%s\t%s\n' 12997 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/parallel.py"
      printf '%s\t%s\n' 1164 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/source/config.json"
      printf '%s\t%s\n' 764 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/utils.py"
      printf '%s\t%s\n' 8836 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_cnn.py"
      printf '%s\t%s\n' 1884 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_module.py"
      printf '%s\t%s\n' 8369 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_processor.py"
      printf '%s\t%s\n' 13490 "MiniMaxAI/MiniMax-H3/FL2VA/video_vae/vae_vit.py"
      printf '%s\t%s\n' 20970379616 "Comfy-Org/MiniMax-H3/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
      printf '%s\t%s\n' 15687142551 "Comfy-Org/MiniMax-H3/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
      printf '%s\t%s\n' 605254808 "Comfy-Org/MiniMax-H3/vae/minimax_h3_audio_vae_fp32.safetensors"
      printf '%s\t%s\n' 5207808496 "Comfy-Org/MiniMax-H3/vae/minimax_h3_video_vae_fp16.safetensors"
      ;;
  minimax-h3-ref2va-int8-convrot)
      printf '%s\t%s\n' 1973 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/config.json"
      printf '%s\t%s\n' 91 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/config.yaml"
      printf '%s\t%s\n' 2189 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_activations.py"
      printf '%s\t%s\n' 835 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_alias_free_act.py"
      printf '%s\t%s\n' 3300 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_alias_free_filter.py"
      printf '%s\t%s\n' 1740 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_alias_free_resample.py"
      printf '%s\t%s\n' 3317 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_attn_proj.py"
      printf '%s\t%s\n' 7266 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_audio_vae.py"
      printf '%s\t%s\n' 7102 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_bigvgan.py"
      printf '%s\t%s\n' 362 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/dac_utils.py"
      printf '%s\t%s\n' 440 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/metadata.json"
      printf '%s\t%s\n' 3532 "MiniMaxAI/MiniMax-H3/Ref2VA/audio_vae/minimax_h3_audio_vae.py"
      printf '%s\t%s\n' 707 "MiniMaxAI/MiniMax-H3/Ref2VA/model_index.json"
      printf '%s\t%s\n' 5499 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/chat_template.json"
      printf '%s\t%s\n' 1671839 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/merges.txt"
      printf '%s\t%s\n' 390 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/preprocessor_config.json"
      printf '%s\t%s\n' 7032403 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/tokenizer.json"
      printf '%s\t%s\n' 11003 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/tokenizer_config.json"
      printf '%s\t%s\n' 385 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/video_preprocessor_config.json"
      printf '%s\t%s\n' 2776833 "MiniMaxAI/MiniMax-H3/Ref2VA/processor/vocab.json"
      printf '%s\t%s\n' 5499 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/chat_template.json"
      printf '%s\t%s\n' 1474 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/config.json"
      printf '%s\t%s\n' 1671839 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/merges.txt"
      printf '%s\t%s\n' 390 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/preprocessor_config.json"
      printf '%s\t%s\n' 7032403 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/tokenizer.json"
      printf '%s\t%s\n' 11003 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/tokenizer_config.json"
      printf '%s\t%s\n' 385 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/video_preprocessor_config.json"
      printf '%s\t%s\n' 2776833 "MiniMaxAI/MiniMax-H3/Ref2VA/text_encoder/vocab.json"
      printf '%s\t%s\n' 1671839 "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/merges.txt"
      printf '%s\t%s\n' 7032403 "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/tokenizer.json"
      printf '%s\t%s\n' 11003 "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/tokenizer_config.json"
      printf '%s\t%s\n' 2776833 "MiniMaxAI/MiniMax-H3/Ref2VA/tokenizer/vocab.json"
      printf '%s\t%s\n' 604 "MiniMaxAI/MiniMax-H3/Ref2VA/transformer/config.json"
      printf '%s\t%s\n' 5785 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/attention.py"
      printf '%s\t%s\n' 9520 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/base_module.py"
      printf '%s\t%s\n' 1807 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/config.json"
      printf '%s\t%s\n' 4487 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/conv.py"
      printf '%s\t%s\n' 5763 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/flash.py"
      printf '%s\t%s\n' 5840 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/func.py"
      printf '%s\t%s\n' 48594 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/klvae.py"
      printf '%s\t%s\n' 5123 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/minimax_h3_video_vae.py"
      printf '%s\t%s\n' 10686 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/norm.py"
      printf '%s\t%s\n' 1200 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/normalize.py"
      printf '%s\t%s\n' 12997 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/parallel.py"
      printf '%s\t%s\n' 1164 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/source/config.json"
      printf '%s\t%s\n' 764 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/utils.py"
      printf '%s\t%s\n' 8836 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_cnn.py"
      printf '%s\t%s\n' 1884 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_module.py"
      printf '%s\t%s\n' 8369 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_processor.py"
      printf '%s\t%s\n' 13490 "MiniMaxAI/MiniMax-H3/Ref2VA/video_vae/vae_vit.py"
      printf '%s\t%s\n' 20970379616 "Comfy-Org/MiniMax-H3/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
      printf '%s\t%s\n' 15687142551 "Comfy-Org/MiniMax-H3/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
      printf '%s\t%s\n' 605254808 "Comfy-Org/MiniMax-H3/vae/minimax_h3_audio_vae_fp32.safetensors"
      printf '%s\t%s\n' 5207808496 "Comfy-Org/MiniMax-H3/vae/minimax_h3_video_vae_fp16.safetensors"
      ;;
  qwen-3.8-27b-nvfp4)
      printf '%s\t%s\n' 8952 "RadixArk/Qwen3.8-27B-NVFP4/chat_template.jinja"
      printf '%s\t%s\n' 73003 "RadixArk/Qwen3.8-27B-NVFP4/config.json"
      printf '%s\t%s\n' 214 "RadixArk/Qwen3.8-27B-NVFP4/generation_config.json"
      printf '%s\t%s\n' 53749 "RadixArk/Qwen3.8-27B-NVFP4/hf_quant_config.json"
      printf '%s\t%s\n' 3353259 "RadixArk/Qwen3.8-27B-NVFP4/merges.txt"
      printf '%s\t%s\n' 9965652544 "RadixArk/Qwen3.8-27B-NVFP4/model-00001-of-00003.safetensors"
      printf '%s\t%s\n' 9985757064 "RadixArk/Qwen3.8-27B-NVFP4/model-00002-of-00003.safetensors"
      printf '%s\t%s\n' 1970287672 "RadixArk/Qwen3.8-27B-NVFP4/model-00003-of-00003.safetensors"
      printf '%s\t%s\n' 214866 "RadixArk/Qwen3.8-27B-NVFP4/model.safetensors.index.json"
      printf '%s\t%s\n' 390 "RadixArk/Qwen3.8-27B-NVFP4/preprocessor_config.json"
      printf '%s\t%s\n' 12809320 "RadixArk/Qwen3.8-27B-NVFP4/tokenizer.json"
      printf '%s\t%s\n' 1121 "RadixArk/Qwen3.8-27B-NVFP4/tokenizer_config.json"
      printf '%s\t%s\n' 385 "RadixArk/Qwen3.8-27B-NVFP4/video_preprocessor_config.json"
      printf '%s\t%s\n' 6722759 "RadixArk/Qwen3.8-27B-NVFP4/vocab.json"
      ;;
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

sglang_model_artifact_ids() {
  case "$1" in
  minimax-h3-fl2va-int8-convrot)
    printf '%s\n' "1777f61a0e519cd1c6f25d3a3c198aab1c7156e51d05b6cd4704f4342a28dcaf" "65c5af92f79a33ebf74e1653335dfb014b0432b6824c32696b9b36aa33c06cd2" "74e4a96615f4019b41426af74d2f8461c9c6b8b2ee3f9efd8cdb26e093f0fdb3" "12d2e33e8a37667aa8562dd9e6333816e6b256d5a0c4850d938d126308b504a8" "585b982b6033a7b7802d19e00f2fefae992533db31ccd7539c07ff7dc3970e1b" "cb27447da00badd19e845cc0bd652bf117e7639f12fe1e818b94462c23150363" "132411c14b5a68f8e7aa54833084e99472933739a97bad3915512a10407b3cb1" "5edacf4c1452d04f63fe2dae44c31ca11e90f1c10ab98a86bc9b3dc275cf9984" "e5514befd3d59285ba8230c83434798535b662230ea9bc7158b9145e9406894d" "86553a5dc3a221a942a8353419f515edf6ea96d995d071d78d8f21644a8b88c1" "682596622db1a031acc40d8650f9055ebf9a667f2ea1e043171a127034c4b95f" "d554befae3f4f0b0d2f5d49922adc7f4cc9c14b9b23cc4d3220a33a360b5355a" "33c1e445f8f76aafd3007982ea2de185ff922fd699f393c4ce7d05a5579b572e" "c06931442bda3ae6b4eb023186ab8f0ccfe7182849da5d21c388554497da184f" "e50b640002d55043e92beca0067730a2e1c90c3e1c38078683148b4e6175c385" "acad371f8de76cd6f99447ce10dfaeeb16d50ad21c380462e5b1ea001f8d6327" "182bb3fd5685772a10d30760a53dc644239c6ef55a50361433cedcc167388ddf" "2a3fc60f23341e6b5080187e3b80530bd30267b736a989a2aa375b3bda77e0f3" "180aa5aba7833eeaefd267deb0d74cd83e47baa2c13541ab39082d3a9f38d97a" "12be3afbeaac13c2207e057b83d6819bceb6a9b25ab5279938c38c14de5cc4c2" "e5242ec7550f96cd1b7e54ce150ce9b1a04fc420a45b71203f3ecdb55648e893" "a146fdf921da7d3564520a83f8ac1b5c6c6fe7d5b270dec423ec3ba6b17df88b" "cd081462abb6cc09286fc578a5cfa48ad54109e9db46de00c791ce69fcabd2a2" "9527f2b09c2128e85c7970b5703bb5abcf14658b160dbbe1a0329655bb8a687f" "6b59e5daaff326aa639ab68c0fd2c509f28b898d926aefe27a38e080699c6e6f" "ca49770f9a004793fbf62e9e871b1c9b24b11d2c7eaa1d34654fcf37e5f5d38f" "5cd730f0dd9d73a9465a71400a2f3866e476a9a6420bf7a77b5d3c6fc648b10d" "43537d6a12f7199cca3363abdc998ceb1b59a992b52cfb65c116a0406fef819a" "b12fa1eecd40a2eacf19da2471b87ec3f95f09599526e295828dd71deb44121c" "9f8a56ad5a1728eaa3d2f5ba5395ef7787030164e2753890729ddfc6d57697b6" "56bb7fa0a62106df8fae689d4e4424429d8975da870afc5036fc62acc9877b78" "66294d81c98fdeb69163690c5ea8377b4c237c6d569df32b615ec49235e5e733" "44a3d3fb48f1594543a55f73582188437be0d6508f6ef57aeec1fa7950057a96" "6b6a29a776697ef4d1515c26d7c05d506e71d057ab95236768531062e78bc3c4" "c942421964a2f4bacc2de46737ace7407c99213b734991ac9d80d6d8e27a9679" "4550db48964f3030752e83e1c72125015166e98f29c3c2cb09fa2c738ed5bc55" "b49379bdc2b29a7e55d66e7684b58ba278a8a7e7bba91931f53cd46b782c91fe" "14f02da9597c047b68e3a66256f4aa91c8982820e6f481aa1bbe02bd733f1c56" "f629f3c3b383a64e3baa5e4b2236c7aee47fa64a7d07caaa3b675d64ad2a7e83" "d496ab322578978b6448682a731f0c6dada347afcc2fd597a18907d85fb0e6ae" "cd34bad0d66a513eed561bdfd3bb0b7a4fecc67c8d744261ac8ffafc18b82dad" "5e3db574cfa0f50420376feaf9a39ee747867cb5731acfbe9d8f7c135a6a5ee1" "32b9b5ea89a55cfbc3d09cbbc1aeb145117422608e69c75e7b6909c1bf9e5223" "c53c9621700c63148a3c81b0d6ee069a3183d4965acecba9ca27284e859e6aa4" "f71a833ef3fefe6757a402e4250da053eeffcfc51fdb3092be7df9532baa5fec" "18fd4ffc22dd48fc381d994d5e7b919e1c57f611ff57ab4aff972032ed191df0" "8740435bf7a3c37e2a213cd908fc49f7cfc37b2e4fe2339ae01ee355b3ba6d11" "e0d6b591aa86a90465d7197f112d48c2c78f97364fa19b03233290483444ae4e" "6b296624b2333131afd1d43b10a4874cfc52f882e954f4f95ba513710fec43d4" "197b3e0ff48d15f2552613724a6b2a64d85b40b04735db740c4f381a5fa1ddac" "e5b6dcd60518d8d785f847cd73bc386e49d47bbd576b5d8700eb34570a4813de" "eb27812965db98bab9180298f41629add421020e807111c667f2ec6b801b2024" "f8a4b810d64ac7aae80edf1a86dcac463d9e2d49a7443584a7bcc3bc87a1f1bf" "8b05098bd8da92c5e326c4152fe9f29834aef2489b5a098192c088e0abdb64a6"
    ;;
  minimax-h3-ref2va-int8-convrot)
    printf '%s\n' "cefbdb47c26a2d9cfd7530197c97751b2fb838be3f7c4c6df474e8e7e472ab45" "03164c445d7327ea4a0fbc01638920edf4056bfdeae1ea9203a60096169f5fdd" "90b3b7e679a6b856a3413d16c4636245a61fcf71463d968b4ecd63abc209f953" "247e72bfc485f160845f5522051c41d301884f3f35d0dcc1019b18b70d99a1c0" "53a5efc78f1739519cfacdb528b7b2d5fc82024b85c34f5d4907c452a9788ac0" "cb3c6a6aae91178f1d7d02aa097005898cabaa95cdd14b8d5b944c4a4e40582c" "d33a505cba5eeb915a10f86fd60b87294c4e7ffdecb13c5e3d19a2420dacec36" "ed0fb2e418b2902b7ed1ab2b442355f7b1be46712b7912f4da2b60f6c14a4a9e" "97ebd718db0f02eda12ec5d669a0abed1cb3991966fab9564c7114622fcc6313" "127a5f54a82d01b4886f6e615c613bc424fd7af527be65932038052cf3391561" "6d107783bd63177c9ee197c5477688c5e99113417578b7878651273d90ee3854" "b9b1c527d89ec7ca1c89ecf6d1984d0f120e4cd23f11ac789c559b030ba317fd" "47b1d01b67fe2df13f9e39e79b101baec94ccfd8b4ece7c641322edb5a87728e" "def039a803ddc8227dcdbe8c702469483c29f2451b7ce38643579109d72689e2" "35158b65febc07515ae249a6220e75c7f2c0d20c2dd413438fe05b61153e3bca" "45744f4a728a958821b6e251f7111ddea3b655dd4b857184826433f796b165dc" "bf2fec0c64575ab5bd8957ca68cd8ba8dad7c8ca75cd22265ad7f0460ead746a" "1cd77b434193822c3a7526db00d2a126ef7d39fcf022654ca0f4e4b0b84270e4" "3ee7af87d088762a967a08df8ad5da0866ee6d1163469cd286d7ed3c84392ba8" "c55222b12846cf5c8c8cebd81c42a537ab306888ada596806a30fd4a7d2618ab" "932d40a3d4b1fda3fe087cea99024be5dba4543d3a3089ec4caa0f9d530c7de0" "a9c4f6a66c12e12134bc9168208b3dc49f334673e566a69b346a4f59e366147f" "221d67d6e046f742e7e28172089cc96e81999eead245bad8fee5b85e14c239b0" "4ea96b08125671598ae3abd1d087e8058ffe9b69b1fd2a7ccaff206f3247c2a3" "e5d72605eb8b0067faa22b4dcbe8a589158782123f5ddd66fd4d6b2fb81709a5" "18cba62292ed3e4d1972e92649c1378ac11050edd6875112c27883b90ddc1977" "94df1cfefc7cc274fd9d348449d026c75e59d61fcf09e6deaa78639bd80a8039" "434a13d7eb7658186962af30c6ae511f718166834ad1073237298d1600fc71a5" "58a285ae8c68cf5b24ceb6f7601df1f695f79cd86cc877833f03486827af1634" "5e0b58636c189d3bc78aa642e7e1cb7483a3eef0c681f8cc01d54a5732fe265d" "ec574c3a9688759e09c150892060816f05b810433d824db5f4b2dd5f93ac86d9" "b5cce8521d0922e7231cf395b12e4806cfdeafa1b647c395c65d6b77ed03cb5d" "32987bba8301dab54f2125367cec44a10b81225b2f24e12f5ffe3b22ea1e2373" "7c1f1541994d8adbb9acfc38cd23229b9c2145b18ec8684cd71b7f972ed40d0f" "a840bd7de4b572d9448bd4f828abf3202b2ec133a4398fb1b0e87526fb0729a9" "b3af6d16005c0e1ce72958eeeb04925e42ed2c10e1479a12c69b4a4083fc4666" "002655bb8c773c8226c896fee0936d54553b9fc704581764acc73ad2e26d224b" "ff9caea90791bcad5e43dbbfd55f051a13a5a798301bb7da866abf6c5cbcc775" "00edbf980322c706fe3e7438c1ad6654bf1e5635d4cba79590adbdaff6afc69d" "d8f14bf4d50a3dec20d44e8975f0d981dd97066ea5b11b68082bb642ca481d07" "7ac94323cffd7ac2488a7fc167a6863a13f7b607d67e5c9dc6f9308d356af6d4" "470810526fdaf745776eb0828072384bec39f89a65dc283d491ddbbe9b4f266d" "5de0d62499dda586ca5b3880ee64383d7b9f68648f16a22df5aac706d132283c" "da4ea9d0e87ab5d25d628f049ce35c1e649219ec2a53435c7e94302e52cdeb0b" "643f218ae163bb85c7fd0084d30408090f16efbde14c7883ce260d6b5b5046a4" "021324fb3d450a9a8e717049f7107543bb62c7133da03fb8db5a85a023bbb348" "d29b0f89a1322f74b95bc1f6638eb9864eca0fd6b407c8ca35a27f77f97e7da3" "a32d7605df547188c02a488b3e7fec45ef6ed7ce03ff335f3300e43474de22a6" "01825b8b9e3577a377cb782bb8420455920dc1efada09ba1bd99e123729ceed2" "473ebef86532b8d5a42f3bef95d5ba27d3fb63fe294922815dd20a9de28a1c6d" "3588902454f67912fd9d4dbbdd50aa71d22a89a3356854aa1c8904c696b51c95" "eb27812965db98bab9180298f41629add421020e807111c667f2ec6b801b2024" "f8a4b810d64ac7aae80edf1a86dcac463d9e2d49a7443584a7bcc3bc87a1f1bf" "8b05098bd8da92c5e326c4152fe9f29834aef2489b5a098192c088e0abdb64a6"
    ;;
  qwen-3.8-27b-nvfp4)
    printf '%s\n' "1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4" "bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c" "919d7ee15a0fadbddfc063ea3ab00cd3e40eff57da0e06367feb477d0dfd7c05" "3e6b53eec281228ca50a1417d3d768d33ee1d8578aeafb516fe50aa81401db7d" "e7e3e7f9a82fa7f51aabb6ade09bb28fa48f5d0c182c27058d4429e42c93435a" "93758408a062a258fd549c4e4ba9e28bfa2b045e2ab55cd6b27487fb01afc3db" "1b005625d88e08b27423395b98ec92f1bc2fcc747355bba89a8581f61e25757b" "68ad6bf748e17568538d93aa614efd5cd86ae3b458364276787fc87ae98aa167" "8a0d6be7fd2bcbb0483918329bc56b1ab010eb4e59d92332a4ebdd81ebfb226b" "ba5d8f1df983d9283c17076c60f2426e27f4917cfdd25e4e436826bdc563245c" "3001036477fa91b75a2b38182de57581aa886607f24a1a4fddea200e1b4c291b" "f3c3ca7e0bd239424a4fea839b50a052e6727c3c89c8fefaa7d1811a94bcfa63" "d46158d901e1e5079969870d919555b038173ce4ef182146087ac682bc638785" "1d6ee74940f64d6aae63bf1f31e9f5c07fb279da96d73c9744736b58e4b96163"
    ;;
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

sglang_download_artifact_id() {
  case "$1" in
  1777f61a0e519cd1c6f25d3a3c198aab1c7156e51d05b6cd4704f4342a28dcaf)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/config.json" 1973 "d8f3bcc62e23c7e9806970fa63cca6139c06faa3797cf9c94034f60db8512771"
    ;;
  65c5af92f79a33ebf74e1653335dfb014b0432b6824c32696b9b36aa33c06cd2)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/config.yaml" 91 "259f675c9f71eedc24ca4f23965cd32a1b3878fc894f56664c40328d99831a5e"
    ;;
  74e4a96615f4019b41426af74d2f8461c9c6b8b2ee3f9efd8cdb26e093f0fdb3)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_activations.py" 2189 "74ca8bb9e8039f1ff362ca4219eee5240a7df9502f3dbdc3161d4e86fbd6dc04"
    ;;
  12d2e33e8a37667aa8562dd9e6333816e6b256d5a0c4850d938d126308b504a8)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_alias_free_act.py" 835 "db8761e66c0eaf9fce2dcccb59162d52b22ca0de9f699cf7d21ec7cd507e86fd"
    ;;
  585b982b6033a7b7802d19e00f2fefae992533db31ccd7539c07ff7dc3970e1b)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_alias_free_filter.py" 3300 "a369523cd7f14f4f299d8e2e47f3c473da76ed1910e6e9134fd7a9fce02537e8"
    ;;
  cb27447da00badd19e845cc0bd652bf117e7639f12fe1e818b94462c23150363)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_alias_free_resample.py" 1740 "fe35055893833c563e42adc5e5882cbe7628c82d48d33c300fcf0a9576997910"
    ;;
  132411c14b5a68f8e7aa54833084e99472933739a97bad3915512a10407b3cb1)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_attn_proj.py" 3317 "0e04556fa5fd38d4a71e62fcf4d3242fd9a2464fd72ed62baef2ec0980d910c6"
    ;;
  5edacf4c1452d04f63fe2dae44c31ca11e90f1c10ab98a86bc9b3dc275cf9984)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_audio_vae.py" 7266 "ec04939602d4710d039e83f558a7572547669652f7fa967e3de0a3b6c48cfd48"
    ;;
  e5514befd3d59285ba8230c83434798535b662230ea9bc7158b9145e9406894d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_bigvgan.py" 7102 "f5df4e6f633e74da479549ef7a6d2684964e4b65ac42c6765be42f9c7fcb7bd2"
    ;;
  86553a5dc3a221a942a8353419f515edf6ea96d995d071d78d8f21644a8b88c1)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_utils.py" 362 "74ef0ba2c2a11ca35a7c0cc166fe88e564de01230000a0bcc8429103312ad9f0"
    ;;
  682596622db1a031acc40d8650f9055ebf9a667f2ea1e043171a127034c4b95f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/metadata.json" 440 "755d0529d43b2b5c83590f6f44ca659bc68e6a21b01d5669c93e8b2965749bff"
    ;;
  d554befae3f4f0b0d2f5d49922adc7f4cc9c14b9b23cc4d3220a33a360b5355a)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/minimax_h3_audio_vae.py" 3532 "63bc0dab6def69480cfd77ea820f9a9a84fc4bd6e56868e4f45ec1e1e200578f"
    ;;
  33c1e445f8f76aafd3007982ea2de185ff922fd699f393c4ce7d05a5579b572e)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/model_index.json" 719 "d1113e0f123c69f79cd0de35ca1771606ebc3ec924270d257b771f96f584aa6b"
    ;;
  c06931442bda3ae6b4eb023186ab8f0ccfe7182849da5d21c388554497da184f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  e50b640002d55043e92beca0067730a2e1c90c3e1c38078683148b4e6175c385)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  acad371f8de76cd6f99447ce10dfaeeb16d50ad21c380462e5b1ea001f8d6327)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  182bb3fd5685772a10d30760a53dc644239c6ef55a50361433cedcc167388ddf)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  2a3fc60f23341e6b5080187e3b80530bd30267b736a989a2aa375b3bda77e0f3)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  180aa5aba7833eeaefd267deb0d74cd83e47baa2c13541ab39082d3a9f38d97a)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  12be3afbeaac13c2207e057b83d6819bceb6a9b25ab5279938c38c14de5cc4c2)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  e5242ec7550f96cd1b7e54ce150ce9b1a04fc420a45b71203f3ecdb55648e893)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  a146fdf921da7d3564520a83f8ac1b5c6c6fe7d5b270dec423ec3ba6b17df88b)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/config.json" 1474 "d2dd0c60d01b9e195d9447c52da61c7302d28828524914c044d9c6e1b81d0427"
    ;;
  cd081462abb6cc09286fc578a5cfa48ad54109e9db46de00c791ce69fcabd2a2)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  9527f2b09c2128e85c7970b5703bb5abcf14658b160dbbe1a0329655bb8a687f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  6b59e5daaff326aa639ab68c0fd2c509f28b898d926aefe27a38e080699c6e6f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  ca49770f9a004793fbf62e9e871b1c9b24b11d2c7eaa1d34654fcf37e5f5d38f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  5cd730f0dd9d73a9465a71400a2f3866e476a9a6420bf7a77b5d3c6fc648b10d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  43537d6a12f7199cca3363abdc998ceb1b59a992b52cfb65c116a0406fef819a)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  b12fa1eecd40a2eacf19da2471b87ec3f95f09599526e295828dd71deb44121c)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  9f8a56ad5a1728eaa3d2f5ba5395ef7787030164e2753890729ddfc6d57697b6)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  56bb7fa0a62106df8fae689d4e4424429d8975da870afc5036fc62acc9877b78)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  66294d81c98fdeb69163690c5ea8377b4c237c6d569df32b615ec49235e5e733)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  44a3d3fb48f1594543a55f73582188437be0d6508f6ef57aeec1fa7950057a96)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/transformer/config.json" 604 "f619093a231fcfbcc3d035bec26c50ad864e7331a500d5c519f5045dc1e50458"
    ;;
  6b6a29a776697ef4d1515c26d7c05d506e71d057ab95236768531062e78bc3c4)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/attention.py" 5785 "c9db8465c57f0bfb40c0194227be6e34b2c1ff7c5b5d63abca9964eed6283767"
    ;;
  c942421964a2f4bacc2de46737ace7407c99213b734991ac9d80d6d8e27a9679)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/base_module.py" 9520 "0e7ddf5086179a306298693ac461ffcbc27ccb28dbc786b1a05060de7a3357c0"
    ;;
  4550db48964f3030752e83e1c72125015166e98f29c3c2cb09fa2c738ed5bc55)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/config.json" 1807 "3edd2cdd1ebc823c868be55ef917e1b3b8a398fde4d3150dae44a3bf05d9f627"
    ;;
  b49379bdc2b29a7e55d66e7684b58ba278a8a7e7bba91931f53cd46b782c91fe)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/conv.py" 4487 "b3adee35f27e5d372543242aa86ce5e0138f13b794b6c81f919001e3e2346723"
    ;;
  14f02da9597c047b68e3a66256f4aa91c8982820e6f481aa1bbe02bd733f1c56)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/flash.py" 5763 "c1918463d303a16f278a670bb4f33d3f8d6f7653b0d473313ff5835699b86d04"
    ;;
  f629f3c3b383a64e3baa5e4b2236c7aee47fa64a7d07caaa3b675d64ad2a7e83)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/func.py" 5840 "0612c26a65f095699cc7acd51937cd153584fa5a0476956e46a4679aa575c22d"
    ;;
  d496ab322578978b6448682a731f0c6dada347afcc2fd597a18907d85fb0e6ae)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/klvae.py" 48594 "d05a22b4918ad303f147d6b0d0ae9038bd1af1f810a5553b04f3542ab9bcff96"
    ;;
  cd34bad0d66a513eed561bdfd3bb0b7a4fecc67c8d744261ac8ffafc18b82dad)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/minimax_h3_video_vae.py" 5123 "77fdea69a48485b5434f65d08096657b5d78b78b7cdf24e1241038f237720138"
    ;;
  5e3db574cfa0f50420376feaf9a39ee747867cb5731acfbe9d8f7c135a6a5ee1)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/norm.py" 10686 "258b120ca8d9a16366d7b811fe93eebf98fe1564db0995e8b7747229c651919a"
    ;;
  32b9b5ea89a55cfbc3d09cbbc1aeb145117422608e69c75e7b6909c1bf9e5223)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/normalize.py" 1200 "8db651acb9eb551c906a2850bbca8e9d851f00d07b30ccf66ceb6057da687a13"
    ;;
  c53c9621700c63148a3c81b0d6ee069a3183d4965acecba9ca27284e859e6aa4)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/parallel.py" 12997 "7193522beafd65bc3dbe40b9843e360ab8da3a0bb211e9bfb67bb0d5d0e66919"
    ;;
  f71a833ef3fefe6757a402e4250da053eeffcfc51fdb3092be7df9532baa5fec)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/source/config.json" 1164 "66c68f541e6578ce613ce7a0fc985eb59097038829e49f7535e6d08e6d95ab12"
    ;;
  18fd4ffc22dd48fc381d994d5e7b919e1c57f611ff57ab4aff972032ed191df0)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/utils.py" 764 "309e45e9d9e33cd5516a10eac2d207eb9f940079a6d9bbe0ee80aaaf7eb42dcd"
    ;;
  8740435bf7a3c37e2a213cd908fc49f7cfc37b2e4fe2339ae01ee355b3ba6d11)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_cnn.py" 8836 "3949b701e6893bd2ea070cd5b18ed8135a7c21d884290df449b1997212d65b11"
    ;;
  e0d6b591aa86a90465d7197f112d48c2c78f97364fa19b03233290483444ae4e)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_module.py" 1884 "9558fb302e10a619f198e12e04701c68988e897d0b627f958f33d27fd2a30d94"
    ;;
  6b296624b2333131afd1d43b10a4874cfc52f882e954f4f95ba513710fec43d4)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_processor.py" 8369 "32870580a1802d9163104a4d68170e35a4772106867181e1bd343dff11f87d2e"
    ;;
  197b3e0ff48d15f2552613724a6b2a64d85b40b04735db740c4f381a5fa1ddac)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_vit.py" 13490 "a372c28441b56ec2dbc6041dbd6ce2766c64c0e61b2c69a16594a97a11da3f58"
    ;;
  e5b6dcd60518d8d785f847cd73bc386e49d47bbd576b5d8700eb34570a4813de)
    prefer_download_hf_artifact "sglang-download" "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" 20970379616 "e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a"
    ;;
  eb27812965db98bab9180298f41629add421020e807111c667f2ec6b801b2024)
    prefer_download_hf_artifact "sglang-download" "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" 15687142551 "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6"
    ;;
  f8a4b810d64ac7aae80edf1a86dcac463d9e2d49a7443584a7bcc3bc87a1f1bf)
    prefer_download_hf_artifact "sglang-download" "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "vae/minimax_h3_audio_vae_fp32.safetensors" 605254808 "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48"
    ;;
  8b05098bd8da92c5e326c4152fe9f29834aef2489b5a098192c088e0abdb64a6)
    prefer_download_hf_artifact "sglang-download" "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "vae/minimax_h3_video_vae_fp16.safetensors" 5207808496 "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522"
    ;;
  cefbdb47c26a2d9cfd7530197c97751b2fb838be3f7c4c6df474e8e7e472ab45)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/config.json" 1973 "d8f3bcc62e23c7e9806970fa63cca6139c06faa3797cf9c94034f60db8512771"
    ;;
  03164c445d7327ea4a0fbc01638920edf4056bfdeae1ea9203a60096169f5fdd)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/config.yaml" 91 "259f675c9f71eedc24ca4f23965cd32a1b3878fc894f56664c40328d99831a5e"
    ;;
  90b3b7e679a6b856a3413d16c4636245a61fcf71463d968b4ecd63abc209f953)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_activations.py" 2189 "74ca8bb9e8039f1ff362ca4219eee5240a7df9502f3dbdc3161d4e86fbd6dc04"
    ;;
  247e72bfc485f160845f5522051c41d301884f3f35d0dcc1019b18b70d99a1c0)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_alias_free_act.py" 835 "db8761e66c0eaf9fce2dcccb59162d52b22ca0de9f699cf7d21ec7cd507e86fd"
    ;;
  53a5efc78f1739519cfacdb528b7b2d5fc82024b85c34f5d4907c452a9788ac0)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_alias_free_filter.py" 3300 "a369523cd7f14f4f299d8e2e47f3c473da76ed1910e6e9134fd7a9fce02537e8"
    ;;
  cb3c6a6aae91178f1d7d02aa097005898cabaa95cdd14b8d5b944c4a4e40582c)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_alias_free_resample.py" 1740 "fe35055893833c563e42adc5e5882cbe7628c82d48d33c300fcf0a9576997910"
    ;;
  d33a505cba5eeb915a10f86fd60b87294c4e7ffdecb13c5e3d19a2420dacec36)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_attn_proj.py" 3317 "0e04556fa5fd38d4a71e62fcf4d3242fd9a2464fd72ed62baef2ec0980d910c6"
    ;;
  ed0fb2e418b2902b7ed1ab2b442355f7b1be46712b7912f4da2b60f6c14a4a9e)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_audio_vae.py" 7266 "ec04939602d4710d039e83f558a7572547669652f7fa967e3de0a3b6c48cfd48"
    ;;
  97ebd718db0f02eda12ec5d669a0abed1cb3991966fab9564c7114622fcc6313)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_bigvgan.py" 7102 "f5df4e6f633e74da479549ef7a6d2684964e4b65ac42c6765be42f9c7fcb7bd2"
    ;;
  127a5f54a82d01b4886f6e615c613bc424fd7af527be65932038052cf3391561)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_utils.py" 362 "74ef0ba2c2a11ca35a7c0cc166fe88e564de01230000a0bcc8429103312ad9f0"
    ;;
  6d107783bd63177c9ee197c5477688c5e99113417578b7878651273d90ee3854)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/metadata.json" 440 "755d0529d43b2b5c83590f6f44ca659bc68e6a21b01d5669c93e8b2965749bff"
    ;;
  b9b1c527d89ec7ca1c89ecf6d1984d0f120e4cd23f11ac789c559b030ba317fd)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/minimax_h3_audio_vae.py" 3532 "63bc0dab6def69480cfd77ea820f9a9a84fc4bd6e56868e4f45ec1e1e200578f"
    ;;
  47b1d01b67fe2df13f9e39e79b101baec94ccfd8b4ece7c641322edb5a87728e)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/model_index.json" 707 "b160b13700bf08aea7fce1bc3dd0d3a49ea15036298c50082ec107f87843b90c"
    ;;
  def039a803ddc8227dcdbe8c702469483c29f2451b7ce38643579109d72689e2)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  35158b65febc07515ae249a6220e75c7f2c0d20c2dd413438fe05b61153e3bca)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  45744f4a728a958821b6e251f7111ddea3b655dd4b857184826433f796b165dc)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  bf2fec0c64575ab5bd8957ca68cd8ba8dad7c8ca75cd22265ad7f0460ead746a)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  1cd77b434193822c3a7526db00d2a126ef7d39fcf022654ca0f4e4b0b84270e4)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  3ee7af87d088762a967a08df8ad5da0866ee6d1163469cd286d7ed3c84392ba8)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  c55222b12846cf5c8c8cebd81c42a537ab306888ada596806a30fd4a7d2618ab)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  932d40a3d4b1fda3fe087cea99024be5dba4543d3a3089ec4caa0f9d530c7de0)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  a9c4f6a66c12e12134bc9168208b3dc49f334673e566a69b346a4f59e366147f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/config.json" 1474 "d2dd0c60d01b9e195d9447c52da61c7302d28828524914c044d9c6e1b81d0427"
    ;;
  221d67d6e046f742e7e28172089cc96e81999eead245bad8fee5b85e14c239b0)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  4ea96b08125671598ae3abd1d087e8058ffe9b69b1fd2a7ccaff206f3247c2a3)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  e5d72605eb8b0067faa22b4dcbe8a589158782123f5ddd66fd4d6b2fb81709a5)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  18cba62292ed3e4d1972e92649c1378ac11050edd6875112c27883b90ddc1977)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  94df1cfefc7cc274fd9d348449d026c75e59d61fcf09e6deaa78639bd80a8039)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  434a13d7eb7658186962af30c6ae511f718166834ad1073237298d1600fc71a5)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  58a285ae8c68cf5b24ceb6f7601df1f695f79cd86cc877833f03486827af1634)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  5e0b58636c189d3bc78aa642e7e1cb7483a3eef0c681f8cc01d54a5732fe265d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  ec574c3a9688759e09c150892060816f05b810433d824db5f4b2dd5f93ac86d9)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  b5cce8521d0922e7231cf395b12e4806cfdeafa1b647c395c65d6b77ed03cb5d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  32987bba8301dab54f2125367cec44a10b81225b2f24e12f5ffe3b22ea1e2373)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/transformer/config.json" 604 "f619093a231fcfbcc3d035bec26c50ad864e7331a500d5c519f5045dc1e50458"
    ;;
  7c1f1541994d8adbb9acfc38cd23229b9c2145b18ec8684cd71b7f972ed40d0f)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/attention.py" 5785 "c9db8465c57f0bfb40c0194227be6e34b2c1ff7c5b5d63abca9964eed6283767"
    ;;
  a840bd7de4b572d9448bd4f828abf3202b2ec133a4398fb1b0e87526fb0729a9)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/base_module.py" 9520 "0e7ddf5086179a306298693ac461ffcbc27ccb28dbc786b1a05060de7a3357c0"
    ;;
  b3af6d16005c0e1ce72958eeeb04925e42ed2c10e1479a12c69b4a4083fc4666)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/config.json" 1807 "3edd2cdd1ebc823c868be55ef917e1b3b8a398fde4d3150dae44a3bf05d9f627"
    ;;
  002655bb8c773c8226c896fee0936d54553b9fc704581764acc73ad2e26d224b)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/conv.py" 4487 "b3adee35f27e5d372543242aa86ce5e0138f13b794b6c81f919001e3e2346723"
    ;;
  ff9caea90791bcad5e43dbbfd55f051a13a5a798301bb7da866abf6c5cbcc775)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/flash.py" 5763 "c1918463d303a16f278a670bb4f33d3f8d6f7653b0d473313ff5835699b86d04"
    ;;
  00edbf980322c706fe3e7438c1ad6654bf1e5635d4cba79590adbdaff6afc69d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/func.py" 5840 "0612c26a65f095699cc7acd51937cd153584fa5a0476956e46a4679aa575c22d"
    ;;
  d8f14bf4d50a3dec20d44e8975f0d981dd97066ea5b11b68082bb642ca481d07)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/klvae.py" 48594 "d05a22b4918ad303f147d6b0d0ae9038bd1af1f810a5553b04f3542ab9bcff96"
    ;;
  7ac94323cffd7ac2488a7fc167a6863a13f7b607d67e5c9dc6f9308d356af6d4)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/minimax_h3_video_vae.py" 5123 "77fdea69a48485b5434f65d08096657b5d78b78b7cdf24e1241038f237720138"
    ;;
  470810526fdaf745776eb0828072384bec39f89a65dc283d491ddbbe9b4f266d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/norm.py" 10686 "258b120ca8d9a16366d7b811fe93eebf98fe1564db0995e8b7747229c651919a"
    ;;
  5de0d62499dda586ca5b3880ee64383d7b9f68648f16a22df5aac706d132283c)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/normalize.py" 1200 "8db651acb9eb551c906a2850bbca8e9d851f00d07b30ccf66ceb6057da687a13"
    ;;
  da4ea9d0e87ab5d25d628f049ce35c1e649219ec2a53435c7e94302e52cdeb0b)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/parallel.py" 12997 "7193522beafd65bc3dbe40b9843e360ab8da3a0bb211e9bfb67bb0d5d0e66919"
    ;;
  643f218ae163bb85c7fd0084d30408090f16efbde14c7883ce260d6b5b5046a4)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/source/config.json" 1164 "66c68f541e6578ce613ce7a0fc985eb59097038829e49f7535e6d08e6d95ab12"
    ;;
  021324fb3d450a9a8e717049f7107543bb62c7133da03fb8db5a85a023bbb348)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/utils.py" 764 "309e45e9d9e33cd5516a10eac2d207eb9f940079a6d9bbe0ee80aaaf7eb42dcd"
    ;;
  d29b0f89a1322f74b95bc1f6638eb9864eca0fd6b407c8ca35a27f77f97e7da3)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_cnn.py" 8836 "3949b701e6893bd2ea070cd5b18ed8135a7c21d884290df449b1997212d65b11"
    ;;
  a32d7605df547188c02a488b3e7fec45ef6ed7ce03ff335f3300e43474de22a6)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_module.py" 1884 "9558fb302e10a619f198e12e04701c68988e897d0b627f958f33d27fd2a30d94"
    ;;
  01825b8b9e3577a377cb782bb8420455920dc1efada09ba1bd99e123729ceed2)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_processor.py" 8369 "32870580a1802d9163104a4d68170e35a4772106867181e1bd343dff11f87d2e"
    ;;
  473ebef86532b8d5a42f3bef95d5ba27d3fb63fe294922815dd20a9de28a1c6d)
    prefer_download_hf_artifact "sglang-download" "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_vit.py" 13490 "a372c28441b56ec2dbc6041dbd6ce2766c64c0e61b2c69a16594a97a11da3f58"
    ;;
  3588902454f67912fd9d4dbbdd50aa71d22a89a3356854aa1c8904c696b51c95)
    prefer_download_hf_artifact "sglang-download" "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" 20970379616 "9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779"
    ;;
  1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "chat_template.jinja" 8952 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041"
    ;;
  bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "config.json" 73003 "7ff41ec6f96ad50efea3c92751cd261b63839d39936eb6e6ffc9066db8672740"
    ;;
  919d7ee15a0fadbddfc063ea3ab00cd3e40eff57da0e06367feb477d0dfd7c05)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "generation_config.json" 214 "a4cef85934ea1fdcb207944dbc6eee70dbbf16806874428556ae33023336c0a4"
    ;;
  3e6b53eec281228ca50a1417d3d768d33ee1d8578aeafb516fe50aa81401db7d)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "hf_quant_config.json" 53749 "0f39e8cd23abdfb79adc89ac1b19acad990aa6ac32973f9ab0a67d1e3449535c"
    ;;
  e7e3e7f9a82fa7f51aabb6ade09bb28fa48f5d0c182c27058d4429e42c93435a)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "merges.txt" 3353259 "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d"
    ;;
  93758408a062a258fd549c4e4ba9e28bfa2b045e2ab55cd6b27487fb01afc3db)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model-00001-of-00003.safetensors" 9965652544 "fbcdb5ba1cdda462b5f38592d071e772c4d398afea61a0aa9188b32d1a239a79"
    ;;
  1b005625d88e08b27423395b98ec92f1bc2fcc747355bba89a8581f61e25757b)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model-00002-of-00003.safetensors" 9985757064 "db6146a5464fb0a891181b93c81593f0ca65c602eb14120a1c2b1b09bca11f85"
    ;;
  68ad6bf748e17568538d93aa614efd5cd86ae3b458364276787fc87ae98aa167)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model-00003-of-00003.safetensors" 1970287672 "d3cfb92742e30c8b46564665791dbe0a86ed64cfc02b1275081530793c0c9581"
    ;;
  8a0d6be7fd2bcbb0483918329bc56b1ab010eb4e59d92332a4ebdd81ebfb226b)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model.safetensors.index.json" 214866 "7aa103a2582b7d26631988de33dea19e8a308ee9c239e8e14feb374af30905e2"
    ;;
  ba5d8f1df983d9283c17076c60f2426e27f4917cfdd25e4e436826bdc563245c)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  3001036477fa91b75a2b38182de57581aa886607f24a1a4fddea200e1b4c291b)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "tokenizer.json" 12809320 "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
    ;;
  f3c3ca7e0bd239424a4fea839b50a052e6727c3c89c8fefaa7d1811a94bcfa63)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "tokenizer_config.json" 1121 "e5d078b00e6c1223b32444db8c1001dc71d86ceef8ee706b5bf084c3a43a1f9c"
    ;;
  d46158d901e1e5079969870d919555b038173ce4ef182146087ac682bc638785)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  1d6ee74940f64d6aae63bf1f31e9f5c07fb279da96d73c9744736b58e4b96163)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "vocab.json" 6722759 "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003"
    ;;
    *) echo "[sglang-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

sglang_artifact_record() {
  case "$1" in
  1777f61a0e519cd1c6f25d3a3c198aab1c7156e51d05b6cd4704f4342a28dcaf)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/config.json" 1973 sha256 "d8f3bcc62e23c7e9806970fa63cca6139c06faa3797cf9c94034f60db8512771"
    ;;
  65c5af92f79a33ebf74e1653335dfb014b0432b6824c32696b9b36aa33c06cd2)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/config.yaml" 91 sha256 "259f675c9f71eedc24ca4f23965cd32a1b3878fc894f56664c40328d99831a5e"
    ;;
  74e4a96615f4019b41426af74d2f8461c9c6b8b2ee3f9efd8cdb26e093f0fdb3)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_activations.py" 2189 sha256 "74ca8bb9e8039f1ff362ca4219eee5240a7df9502f3dbdc3161d4e86fbd6dc04"
    ;;
  12d2e33e8a37667aa8562dd9e6333816e6b256d5a0c4850d938d126308b504a8)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_alias_free_act.py" 835 sha256 "db8761e66c0eaf9fce2dcccb59162d52b22ca0de9f699cf7d21ec7cd507e86fd"
    ;;
  585b982b6033a7b7802d19e00f2fefae992533db31ccd7539c07ff7dc3970e1b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_alias_free_filter.py" 3300 sha256 "a369523cd7f14f4f299d8e2e47f3c473da76ed1910e6e9134fd7a9fce02537e8"
    ;;
  cb27447da00badd19e845cc0bd652bf117e7639f12fe1e818b94462c23150363)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_alias_free_resample.py" 1740 sha256 "fe35055893833c563e42adc5e5882cbe7628c82d48d33c300fcf0a9576997910"
    ;;
  132411c14b5a68f8e7aa54833084e99472933739a97bad3915512a10407b3cb1)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_attn_proj.py" 3317 sha256 "0e04556fa5fd38d4a71e62fcf4d3242fd9a2464fd72ed62baef2ec0980d910c6"
    ;;
  5edacf4c1452d04f63fe2dae44c31ca11e90f1c10ab98a86bc9b3dc275cf9984)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_audio_vae.py" 7266 sha256 "ec04939602d4710d039e83f558a7572547669652f7fa967e3de0a3b6c48cfd48"
    ;;
  e5514befd3d59285ba8230c83434798535b662230ea9bc7158b9145e9406894d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_bigvgan.py" 7102 sha256 "f5df4e6f633e74da479549ef7a6d2684964e4b65ac42c6765be42f9c7fcb7bd2"
    ;;
  86553a5dc3a221a942a8353419f515edf6ea96d995d071d78d8f21644a8b88c1)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/dac_utils.py" 362 sha256 "74ef0ba2c2a11ca35a7c0cc166fe88e564de01230000a0bcc8429103312ad9f0"
    ;;
  682596622db1a031acc40d8650f9055ebf9a667f2ea1e043171a127034c4b95f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/metadata.json" 440 sha256 "755d0529d43b2b5c83590f6f44ca659bc68e6a21b01d5669c93e8b2965749bff"
    ;;
  d554befae3f4f0b0d2f5d49922adc7f4cc9c14b9b23cc4d3220a33a360b5355a)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/audio_vae/minimax_h3_audio_vae.py" 3532 sha256 "63bc0dab6def69480cfd77ea820f9a9a84fc4bd6e56868e4f45ec1e1e200578f"
    ;;
  33c1e445f8f76aafd3007982ea2de185ff922fd699f393c4ce7d05a5579b572e)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/model_index.json" 719 sha256 "d1113e0f123c69f79cd0de35ca1771606ebc3ec924270d257b771f96f584aa6b"
    ;;
  c06931442bda3ae6b4eb023186ab8f0ccfe7182849da5d21c388554497da184f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/chat_template.json" 5499 sha256 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  e50b640002d55043e92beca0067730a2e1c90c3e1c38078683148b4e6175c385)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/merges.txt" 1671839 sha256 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  acad371f8de76cd6f99447ce10dfaeeb16d50ad21c380462e5b1ea001f8d6327)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/preprocessor_config.json" 390 sha256 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  182bb3fd5685772a10d30760a53dc644239c6ef55a50361433cedcc167388ddf)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/tokenizer.json" 7032403 sha256 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  2a3fc60f23341e6b5080187e3b80530bd30267b736a989a2aa375b3bda77e0f3)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/tokenizer_config.json" 11003 sha256 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  180aa5aba7833eeaefd267deb0d74cd83e47baa2c13541ab39082d3a9f38d97a)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/video_preprocessor_config.json" 385 sha256 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  12be3afbeaac13c2207e057b83d6819bceb6a9b25ab5279938c38c14de5cc4c2)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/processor/vocab.json" 2776833 sha256 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  e5242ec7550f96cd1b7e54ce150ce9b1a04fc420a45b71203f3ecdb55648e893)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/chat_template.json" 5499 sha256 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  a146fdf921da7d3564520a83f8ac1b5c6c6fe7d5b270dec423ec3ba6b17df88b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/config.json" 1474 sha256 "d2dd0c60d01b9e195d9447c52da61c7302d28828524914c044d9c6e1b81d0427"
    ;;
  cd081462abb6cc09286fc578a5cfa48ad54109e9db46de00c791ce69fcabd2a2)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/merges.txt" 1671839 sha256 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  9527f2b09c2128e85c7970b5703bb5abcf14658b160dbbe1a0329655bb8a687f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/preprocessor_config.json" 390 sha256 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  6b59e5daaff326aa639ab68c0fd2c509f28b898d926aefe27a38e080699c6e6f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/tokenizer.json" 7032403 sha256 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  ca49770f9a004793fbf62e9e871b1c9b24b11d2c7eaa1d34654fcf37e5f5d38f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/tokenizer_config.json" 11003 sha256 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  5cd730f0dd9d73a9465a71400a2f3866e476a9a6420bf7a77b5d3c6fc648b10d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/video_preprocessor_config.json" 385 sha256 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  43537d6a12f7199cca3363abdc998ceb1b59a992b52cfb65c116a0406fef819a)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/text_encoder/vocab.json" 2776833 sha256 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  b12fa1eecd40a2eacf19da2471b87ec3f95f09599526e295828dd71deb44121c)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/merges.txt" 1671839 sha256 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  9f8a56ad5a1728eaa3d2f5ba5395ef7787030164e2753890729ddfc6d57697b6)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/tokenizer.json" 7032403 sha256 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  56bb7fa0a62106df8fae689d4e4424429d8975da870afc5036fc62acc9877b78)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/tokenizer_config.json" 11003 sha256 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  66294d81c98fdeb69163690c5ea8377b4c237c6d569df32b615ec49235e5e733)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/tokenizer/vocab.json" 2776833 sha256 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  44a3d3fb48f1594543a55f73582188437be0d6508f6ef57aeec1fa7950057a96)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/transformer/config.json" 604 sha256 "f619093a231fcfbcc3d035bec26c50ad864e7331a500d5c519f5045dc1e50458"
    ;;
  6b6a29a776697ef4d1515c26d7c05d506e71d057ab95236768531062e78bc3c4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/attention.py" 5785 sha256 "c9db8465c57f0bfb40c0194227be6e34b2c1ff7c5b5d63abca9964eed6283767"
    ;;
  c942421964a2f4bacc2de46737ace7407c99213b734991ac9d80d6d8e27a9679)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/base_module.py" 9520 sha256 "0e7ddf5086179a306298693ac461ffcbc27ccb28dbc786b1a05060de7a3357c0"
    ;;
  4550db48964f3030752e83e1c72125015166e98f29c3c2cb09fa2c738ed5bc55)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/config.json" 1807 sha256 "3edd2cdd1ebc823c868be55ef917e1b3b8a398fde4d3150dae44a3bf05d9f627"
    ;;
  b49379bdc2b29a7e55d66e7684b58ba278a8a7e7bba91931f53cd46b782c91fe)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/conv.py" 4487 sha256 "b3adee35f27e5d372543242aa86ce5e0138f13b794b6c81f919001e3e2346723"
    ;;
  14f02da9597c047b68e3a66256f4aa91c8982820e6f481aa1bbe02bd733f1c56)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/flash.py" 5763 sha256 "c1918463d303a16f278a670bb4f33d3f8d6f7653b0d473313ff5835699b86d04"
    ;;
  f629f3c3b383a64e3baa5e4b2236c7aee47fa64a7d07caaa3b675d64ad2a7e83)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/func.py" 5840 sha256 "0612c26a65f095699cc7acd51937cd153584fa5a0476956e46a4679aa575c22d"
    ;;
  d496ab322578978b6448682a731f0c6dada347afcc2fd597a18907d85fb0e6ae)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/klvae.py" 48594 sha256 "d05a22b4918ad303f147d6b0d0ae9038bd1af1f810a5553b04f3542ab9bcff96"
    ;;
  cd34bad0d66a513eed561bdfd3bb0b7a4fecc67c8d744261ac8ffafc18b82dad)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/minimax_h3_video_vae.py" 5123 sha256 "77fdea69a48485b5434f65d08096657b5d78b78b7cdf24e1241038f237720138"
    ;;
  5e3db574cfa0f50420376feaf9a39ee747867cb5731acfbe9d8f7c135a6a5ee1)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/norm.py" 10686 sha256 "258b120ca8d9a16366d7b811fe93eebf98fe1564db0995e8b7747229c651919a"
    ;;
  32b9b5ea89a55cfbc3d09cbbc1aeb145117422608e69c75e7b6909c1bf9e5223)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/normalize.py" 1200 sha256 "8db651acb9eb551c906a2850bbca8e9d851f00d07b30ccf66ceb6057da687a13"
    ;;
  c53c9621700c63148a3c81b0d6ee069a3183d4965acecba9ca27284e859e6aa4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/parallel.py" 12997 sha256 "7193522beafd65bc3dbe40b9843e360ab8da3a0bb211e9bfb67bb0d5d0e66919"
    ;;
  f71a833ef3fefe6757a402e4250da053eeffcfc51fdb3092be7df9532baa5fec)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/source/config.json" 1164 sha256 "66c68f541e6578ce613ce7a0fc985eb59097038829e49f7535e6d08e6d95ab12"
    ;;
  18fd4ffc22dd48fc381d994d5e7b919e1c57f611ff57ab4aff972032ed191df0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/utils.py" 764 sha256 "309e45e9d9e33cd5516a10eac2d207eb9f940079a6d9bbe0ee80aaaf7eb42dcd"
    ;;
  8740435bf7a3c37e2a213cd908fc49f7cfc37b2e4fe2339ae01ee355b3ba6d11)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_cnn.py" 8836 sha256 "3949b701e6893bd2ea070cd5b18ed8135a7c21d884290df449b1997212d65b11"
    ;;
  e0d6b591aa86a90465d7197f112d48c2c78f97364fa19b03233290483444ae4e)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_module.py" 1884 sha256 "9558fb302e10a619f198e12e04701c68988e897d0b627f958f33d27fd2a30d94"
    ;;
  6b296624b2333131afd1d43b10a4874cfc52f882e954f4f95ba513710fec43d4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_processor.py" 8369 sha256 "32870580a1802d9163104a4d68170e35a4772106867181e1bd343dff11f87d2e"
    ;;
  197b3e0ff48d15f2552613724a6b2a64d85b40b04735db740c4f381a5fa1ddac)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "FL2VA/video_vae/vae_vit.py" 13490 sha256 "a372c28441b56ec2dbc6041dbd6ce2766c64c0e61b2c69a16594a97a11da3f58"
    ;;
  e5b6dcd60518d8d785f847cd73bc386e49d47bbd576b5d8700eb34570a4813de)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" 20970379616 sha256 "e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a"
    ;;
  eb27812965db98bab9180298f41629add421020e807111c667f2ec6b801b2024)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" 15687142551 sha256 "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6"
    ;;
  f8a4b810d64ac7aae80edf1a86dcac463d9e2d49a7443584a7bcc3bc87a1f1bf)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "vae/minimax_h3_audio_vae_fp32.safetensors" 605254808 sha256 "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48"
    ;;
  8b05098bd8da92c5e326c4152fe9f29834aef2489b5a098192c088e0abdb64a6)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "vae/minimax_h3_video_vae_fp16.safetensors" 5207808496 sha256 "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522"
    ;;
  cefbdb47c26a2d9cfd7530197c97751b2fb838be3f7c4c6df474e8e7e472ab45)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/config.json" 1973 sha256 "d8f3bcc62e23c7e9806970fa63cca6139c06faa3797cf9c94034f60db8512771"
    ;;
  03164c445d7327ea4a0fbc01638920edf4056bfdeae1ea9203a60096169f5fdd)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/config.yaml" 91 sha256 "259f675c9f71eedc24ca4f23965cd32a1b3878fc894f56664c40328d99831a5e"
    ;;
  90b3b7e679a6b856a3413d16c4636245a61fcf71463d968b4ecd63abc209f953)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_activations.py" 2189 sha256 "74ca8bb9e8039f1ff362ca4219eee5240a7df9502f3dbdc3161d4e86fbd6dc04"
    ;;
  247e72bfc485f160845f5522051c41d301884f3f35d0dcc1019b18b70d99a1c0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_alias_free_act.py" 835 sha256 "db8761e66c0eaf9fce2dcccb59162d52b22ca0de9f699cf7d21ec7cd507e86fd"
    ;;
  53a5efc78f1739519cfacdb528b7b2d5fc82024b85c34f5d4907c452a9788ac0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_alias_free_filter.py" 3300 sha256 "a369523cd7f14f4f299d8e2e47f3c473da76ed1910e6e9134fd7a9fce02537e8"
    ;;
  cb3c6a6aae91178f1d7d02aa097005898cabaa95cdd14b8d5b944c4a4e40582c)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_alias_free_resample.py" 1740 sha256 "fe35055893833c563e42adc5e5882cbe7628c82d48d33c300fcf0a9576997910"
    ;;
  d33a505cba5eeb915a10f86fd60b87294c4e7ffdecb13c5e3d19a2420dacec36)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_attn_proj.py" 3317 sha256 "0e04556fa5fd38d4a71e62fcf4d3242fd9a2464fd72ed62baef2ec0980d910c6"
    ;;
  ed0fb2e418b2902b7ed1ab2b442355f7b1be46712b7912f4da2b60f6c14a4a9e)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_audio_vae.py" 7266 sha256 "ec04939602d4710d039e83f558a7572547669652f7fa967e3de0a3b6c48cfd48"
    ;;
  97ebd718db0f02eda12ec5d669a0abed1cb3991966fab9564c7114622fcc6313)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_bigvgan.py" 7102 sha256 "f5df4e6f633e74da479549ef7a6d2684964e4b65ac42c6765be42f9c7fcb7bd2"
    ;;
  127a5f54a82d01b4886f6e615c613bc424fd7af527be65932038052cf3391561)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/dac_utils.py" 362 sha256 "74ef0ba2c2a11ca35a7c0cc166fe88e564de01230000a0bcc8429103312ad9f0"
    ;;
  6d107783bd63177c9ee197c5477688c5e99113417578b7878651273d90ee3854)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/metadata.json" 440 sha256 "755d0529d43b2b5c83590f6f44ca659bc68e6a21b01d5669c93e8b2965749bff"
    ;;
  b9b1c527d89ec7ca1c89ecf6d1984d0f120e4cd23f11ac789c559b030ba317fd)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/audio_vae/minimax_h3_audio_vae.py" 3532 sha256 "63bc0dab6def69480cfd77ea820f9a9a84fc4bd6e56868e4f45ec1e1e200578f"
    ;;
  47b1d01b67fe2df13f9e39e79b101baec94ccfd8b4ece7c641322edb5a87728e)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/model_index.json" 707 sha256 "b160b13700bf08aea7fce1bc3dd0d3a49ea15036298c50082ec107f87843b90c"
    ;;
  def039a803ddc8227dcdbe8c702469483c29f2451b7ce38643579109d72689e2)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/chat_template.json" 5499 sha256 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  35158b65febc07515ae249a6220e75c7f2c0d20c2dd413438fe05b61153e3bca)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/merges.txt" 1671839 sha256 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  45744f4a728a958821b6e251f7111ddea3b655dd4b857184826433f796b165dc)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/preprocessor_config.json" 390 sha256 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  bf2fec0c64575ab5bd8957ca68cd8ba8dad7c8ca75cd22265ad7f0460ead746a)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/tokenizer.json" 7032403 sha256 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  1cd77b434193822c3a7526db00d2a126ef7d39fcf022654ca0f4e4b0b84270e4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/tokenizer_config.json" 11003 sha256 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  3ee7af87d088762a967a08df8ad5da0866ee6d1163469cd286d7ed3c84392ba8)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/video_preprocessor_config.json" 385 sha256 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  c55222b12846cf5c8c8cebd81c42a537ab306888ada596806a30fd4a7d2618ab)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/processor/vocab.json" 2776833 sha256 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  932d40a3d4b1fda3fe087cea99024be5dba4543d3a3089ec4caa0f9d530c7de0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/chat_template.json" 5499 sha256 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce"
    ;;
  a9c4f6a66c12e12134bc9168208b3dc49f334673e566a69b346a4f59e366147f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/config.json" 1474 sha256 "d2dd0c60d01b9e195d9447c52da61c7302d28828524914c044d9c6e1b81d0427"
    ;;
  221d67d6e046f742e7e28172089cc96e81999eead245bad8fee5b85e14c239b0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/merges.txt" 1671839 sha256 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  4ea96b08125671598ae3abd1d087e8058ffe9b69b1fd2a7ccaff206f3247c2a3)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/preprocessor_config.json" 390 sha256 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  e5d72605eb8b0067faa22b4dcbe8a589158782123f5ddd66fd4d6b2fb81709a5)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/tokenizer.json" 7032403 sha256 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  18cba62292ed3e4d1972e92649c1378ac11050edd6875112c27883b90ddc1977)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/tokenizer_config.json" 11003 sha256 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  94df1cfefc7cc274fd9d348449d026c75e59d61fcf09e6deaa78639bd80a8039)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/video_preprocessor_config.json" 385 sha256 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  434a13d7eb7658186962af30c6ae511f718166834ad1073237298d1600fc71a5)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/text_encoder/vocab.json" 2776833 sha256 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  58a285ae8c68cf5b24ceb6f7601df1f695f79cd86cc877833f03486827af1634)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/merges.txt" 1671839 sha256 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ;;
  5e0b58636c189d3bc78aa642e7e1cb7483a3eef0c681f8cc01d54a5732fe265d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/tokenizer.json" 7032403 sha256 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7"
    ;;
  ec574c3a9688759e09c150892060816f05b810433d824db5f4b2dd5f93ac86d9)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/tokenizer_config.json" 11003 sha256 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68"
    ;;
  b5cce8521d0922e7231cf395b12e4806cfdeafa1b647c395c65d6b77ed03cb5d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/tokenizer/vocab.json" 2776833 sha256 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ;;
  32987bba8301dab54f2125367cec44a10b81225b2f24e12f5ffe3b22ea1e2373)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/transformer/config.json" 604 sha256 "f619093a231fcfbcc3d035bec26c50ad864e7331a500d5c519f5045dc1e50458"
    ;;
  7c1f1541994d8adbb9acfc38cd23229b9c2145b18ec8684cd71b7f972ed40d0f)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/attention.py" 5785 sha256 "c9db8465c57f0bfb40c0194227be6e34b2c1ff7c5b5d63abca9964eed6283767"
    ;;
  a840bd7de4b572d9448bd4f828abf3202b2ec133a4398fb1b0e87526fb0729a9)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/base_module.py" 9520 sha256 "0e7ddf5086179a306298693ac461ffcbc27ccb28dbc786b1a05060de7a3357c0"
    ;;
  b3af6d16005c0e1ce72958eeeb04925e42ed2c10e1479a12c69b4a4083fc4666)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/config.json" 1807 sha256 "3edd2cdd1ebc823c868be55ef917e1b3b8a398fde4d3150dae44a3bf05d9f627"
    ;;
  002655bb8c773c8226c896fee0936d54553b9fc704581764acc73ad2e26d224b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/conv.py" 4487 sha256 "b3adee35f27e5d372543242aa86ce5e0138f13b794b6c81f919001e3e2346723"
    ;;
  ff9caea90791bcad5e43dbbfd55f051a13a5a798301bb7da866abf6c5cbcc775)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/flash.py" 5763 sha256 "c1918463d303a16f278a670bb4f33d3f8d6f7653b0d473313ff5835699b86d04"
    ;;
  00edbf980322c706fe3e7438c1ad6654bf1e5635d4cba79590adbdaff6afc69d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/func.py" 5840 sha256 "0612c26a65f095699cc7acd51937cd153584fa5a0476956e46a4679aa575c22d"
    ;;
  d8f14bf4d50a3dec20d44e8975f0d981dd97066ea5b11b68082bb642ca481d07)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/klvae.py" 48594 sha256 "d05a22b4918ad303f147d6b0d0ae9038bd1af1f810a5553b04f3542ab9bcff96"
    ;;
  7ac94323cffd7ac2488a7fc167a6863a13f7b607d67e5c9dc6f9308d356af6d4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/minimax_h3_video_vae.py" 5123 sha256 "77fdea69a48485b5434f65d08096657b5d78b78b7cdf24e1241038f237720138"
    ;;
  470810526fdaf745776eb0828072384bec39f89a65dc283d491ddbbe9b4f266d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/norm.py" 10686 sha256 "258b120ca8d9a16366d7b811fe93eebf98fe1564db0995e8b7747229c651919a"
    ;;
  5de0d62499dda586ca5b3880ee64383d7b9f68648f16a22df5aac706d132283c)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/normalize.py" 1200 sha256 "8db651acb9eb551c906a2850bbca8e9d851f00d07b30ccf66ceb6057da687a13"
    ;;
  da4ea9d0e87ab5d25d628f049ce35c1e649219ec2a53435c7e94302e52cdeb0b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/parallel.py" 12997 sha256 "7193522beafd65bc3dbe40b9843e360ab8da3a0bb211e9bfb67bb0d5d0e66919"
    ;;
  643f218ae163bb85c7fd0084d30408090f16efbde14c7883ce260d6b5b5046a4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/source/config.json" 1164 sha256 "66c68f541e6578ce613ce7a0fc985eb59097038829e49f7535e6d08e6d95ab12"
    ;;
  021324fb3d450a9a8e717049f7107543bb62c7133da03fb8db5a85a023bbb348)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/utils.py" 764 sha256 "309e45e9d9e33cd5516a10eac2d207eb9f940079a6d9bbe0ee80aaaf7eb42dcd"
    ;;
  d29b0f89a1322f74b95bc1f6638eb9864eca0fd6b407c8ca35a27f77f97e7da3)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_cnn.py" 8836 sha256 "3949b701e6893bd2ea070cd5b18ed8135a7c21d884290df449b1997212d65b11"
    ;;
  a32d7605df547188c02a488b3e7fec45ef6ed7ce03ff335f3300e43474de22a6)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_module.py" 1884 sha256 "9558fb302e10a619f198e12e04701c68988e897d0b627f958f33d27fd2a30d94"
    ;;
  01825b8b9e3577a377cb782bb8420455920dc1efada09ba1bd99e123729ceed2)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_processor.py" 8369 sha256 "32870580a1802d9163104a4d68170e35a4772106867181e1bd343dff11f87d2e"
    ;;
  473ebef86532b8d5a42f3bef95d5ba27d3fb63fe294922815dd20a9de28a1c6d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "MiniMaxAI/MiniMax-H3" "5d9b308a59ab12e67147f191e184baf704185bd1" "Ref2VA/video_vae/vae_vit.py" 13490 sha256 "a372c28441b56ec2dbc6041dbd6ce2766c64c0e61b2c69a16594a97a11da3f58"
    ;;
  3588902454f67912fd9d4dbbdd50aa71d22a89a3356854aa1c8904c696b51c95)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "Comfy-Org/MiniMax-H3" "3f57e8291d2ef846f9a074b1b76d2767db434abe" "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" 20970379616 sha256 "9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779"
    ;;
  1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "chat_template.jinja" 8952 sha256 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041"
    ;;
  bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "config.json" 73003 sha256 "7ff41ec6f96ad50efea3c92751cd261b63839d39936eb6e6ffc9066db8672740"
    ;;
  919d7ee15a0fadbddfc063ea3ab00cd3e40eff57da0e06367feb477d0dfd7c05)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "generation_config.json" 214 sha256 "a4cef85934ea1fdcb207944dbc6eee70dbbf16806874428556ae33023336c0a4"
    ;;
  3e6b53eec281228ca50a1417d3d768d33ee1d8578aeafb516fe50aa81401db7d)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "hf_quant_config.json" 53749 sha256 "0f39e8cd23abdfb79adc89ac1b19acad990aa6ac32973f9ab0a67d1e3449535c"
    ;;
  e7e3e7f9a82fa7f51aabb6ade09bb28fa48f5d0c182c27058d4429e42c93435a)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "merges.txt" 3353259 sha256 "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d"
    ;;
  93758408a062a258fd549c4e4ba9e28bfa2b045e2ab55cd6b27487fb01afc3db)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model-00001-of-00003.safetensors" 9965652544 sha256 "fbcdb5ba1cdda462b5f38592d071e772c4d398afea61a0aa9188b32d1a239a79"
    ;;
  1b005625d88e08b27423395b98ec92f1bc2fcc747355bba89a8581f61e25757b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model-00002-of-00003.safetensors" 9985757064 sha256 "db6146a5464fb0a891181b93c81593f0ca65c602eb14120a1c2b1b09bca11f85"
    ;;
  68ad6bf748e17568538d93aa614efd5cd86ae3b458364276787fc87ae98aa167)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model-00003-of-00003.safetensors" 1970287672 sha256 "d3cfb92742e30c8b46564665791dbe0a86ed64cfc02b1275081530793c0c9581"
    ;;
  8a0d6be7fd2bcbb0483918329bc56b1ab010eb4e59d92332a4ebdd81ebfb226b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "model.safetensors.index.json" 214866 sha256 "7aa103a2582b7d26631988de33dea19e8a308ee9c239e8e14feb374af30905e2"
    ;;
  ba5d8f1df983d9283c17076c60f2426e27f4917cfdd25e4e436826bdc563245c)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "preprocessor_config.json" 390 sha256 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  3001036477fa91b75a2b38182de57581aa886607f24a1a4fddea200e1b4c291b)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "tokenizer.json" 12809320 sha256 "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
    ;;
  f3c3ca7e0bd239424a4fea839b50a052e6727c3c89c8fefaa7d1811a94bcfa63)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "tokenizer_config.json" 1121 sha256 "e5d078b00e6c1223b32444db8c1001dc71d86ceef8ee706b5bf084c3a43a1f9c"
    ;;
  d46158d901e1e5079969870d919555b038173ce4ef182146087ac682bc638785)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "video_preprocessor_config.json" 385 sha256 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  1d6ee74940f64d6aae63bf1f31e9f5c07fb279da96d73c9744736b58e4b96163)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "vocab.json" 6722759 sha256 "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003"
    ;;
    *) echo "[sglang-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

sglang_s3_download_artifact_id() {
  if [ -z "${SGLANG_S3_BUCKET_NAME:-}" ]; then
    echo "[sglang-download] SGLANG_S3_BUCKET_NAME is required for S3 staging" >&2
    return 2
  fi
  case "$1" in
  1777f61a0e519cd1c6f25d3a3c198aab1c7156e51d05b6cd4704f4342a28dcaf)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/config.json" 1973 "d8f3bcc62e23c7e9806970fa63cca6139c06faa3797cf9c94034f60db8512771" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  65c5af92f79a33ebf74e1653335dfb014b0432b6824c32696b9b36aa33c06cd2)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/config.yaml" 91 "259f675c9f71eedc24ca4f23965cd32a1b3878fc894f56664c40328d99831a5e" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  74e4a96615f4019b41426af74d2f8461c9c6b8b2ee3f9efd8cdb26e093f0fdb3)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_activations.py" 2189 "74ca8bb9e8039f1ff362ca4219eee5240a7df9502f3dbdc3161d4e86fbd6dc04" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  12d2e33e8a37667aa8562dd9e6333816e6b256d5a0c4850d938d126308b504a8)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_alias_free_act.py" 835 "db8761e66c0eaf9fce2dcccb59162d52b22ca0de9f699cf7d21ec7cd507e86fd" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  585b982b6033a7b7802d19e00f2fefae992533db31ccd7539c07ff7dc3970e1b)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_alias_free_filter.py" 3300 "a369523cd7f14f4f299d8e2e47f3c473da76ed1910e6e9134fd7a9fce02537e8" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  cb27447da00badd19e845cc0bd652bf117e7639f12fe1e818b94462c23150363)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_alias_free_resample.py" 1740 "fe35055893833c563e42adc5e5882cbe7628c82d48d33c300fcf0a9576997910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  132411c14b5a68f8e7aa54833084e99472933739a97bad3915512a10407b3cb1)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_attn_proj.py" 3317 "0e04556fa5fd38d4a71e62fcf4d3242fd9a2464fd72ed62baef2ec0980d910c6" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  5edacf4c1452d04f63fe2dae44c31ca11e90f1c10ab98a86bc9b3dc275cf9984)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_audio_vae.py" 7266 "ec04939602d4710d039e83f558a7572547669652f7fa967e3de0a3b6c48cfd48" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e5514befd3d59285ba8230c83434798535b662230ea9bc7158b9145e9406894d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_bigvgan.py" 7102 "f5df4e6f633e74da479549ef7a6d2684964e4b65ac42c6765be42f9c7fcb7bd2" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  86553a5dc3a221a942a8353419f515edf6ea96d995d071d78d8f21644a8b88c1)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/dac_utils.py" 362 "74ef0ba2c2a11ca35a7c0cc166fe88e564de01230000a0bcc8429103312ad9f0" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  682596622db1a031acc40d8650f9055ebf9a667f2ea1e043171a127034c4b95f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/metadata.json" 440 "755d0529d43b2b5c83590f6f44ca659bc68e6a21b01d5669c93e8b2965749bff" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  d554befae3f4f0b0d2f5d49922adc7f4cc9c14b9b23cc4d3220a33a360b5355a)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/audio_vae/minimax_h3_audio_vae.py" 3532 "63bc0dab6def69480cfd77ea820f9a9a84fc4bd6e56868e4f45ec1e1e200578f" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  33c1e445f8f76aafd3007982ea2de185ff922fd699f393c4ce7d05a5579b572e)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/model_index.json" 719 "d1113e0f123c69f79cd0de35ca1771606ebc3ec924270d257b771f96f584aa6b" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  c06931442bda3ae6b4eb023186ab8f0ccfe7182849da5d21c388554497da184f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e50b640002d55043e92beca0067730a2e1c90c3e1c38078683148b4e6175c385)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  acad371f8de76cd6f99447ce10dfaeeb16d50ad21c380462e5b1ea001f8d6327)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  182bb3fd5685772a10d30760a53dc644239c6ef55a50361433cedcc167388ddf)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  2a3fc60f23341e6b5080187e3b80530bd30267b736a989a2aa375b3bda77e0f3)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  180aa5aba7833eeaefd267deb0d74cd83e47baa2c13541ab39082d3a9f38d97a)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  12be3afbeaac13c2207e057b83d6819bceb6a9b25ab5279938c38c14de5cc4c2)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/processor/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e5242ec7550f96cd1b7e54ce150ce9b1a04fc420a45b71203f3ecdb55648e893)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  a146fdf921da7d3564520a83f8ac1b5c6c6fe7d5b270dec423ec3ba6b17df88b)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/config.json" 1474 "d2dd0c60d01b9e195d9447c52da61c7302d28828524914c044d9c6e1b81d0427" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  cd081462abb6cc09286fc578a5cfa48ad54109e9db46de00c791ce69fcabd2a2)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  9527f2b09c2128e85c7970b5703bb5abcf14658b160dbbe1a0329655bb8a687f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  6b59e5daaff326aa639ab68c0fd2c509f28b898d926aefe27a38e080699c6e6f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  ca49770f9a004793fbf62e9e871b1c9b24b11d2c7eaa1d34654fcf37e5f5d38f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  5cd730f0dd9d73a9465a71400a2f3866e476a9a6420bf7a77b5d3c6fc648b10d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  43537d6a12f7199cca3363abdc998ceb1b59a992b52cfb65c116a0406fef819a)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/text_encoder/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  b12fa1eecd40a2eacf19da2471b87ec3f95f09599526e295828dd71deb44121c)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/tokenizer/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  9f8a56ad5a1728eaa3d2f5ba5395ef7787030164e2753890729ddfc6d57697b6)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/tokenizer/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  56bb7fa0a62106df8fae689d4e4424429d8975da870afc5036fc62acc9877b78)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/tokenizer/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  66294d81c98fdeb69163690c5ea8377b4c237c6d569df32b615ec49235e5e733)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/tokenizer/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  44a3d3fb48f1594543a55f73582188437be0d6508f6ef57aeec1fa7950057a96)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/transformer/config.json" 604 "f619093a231fcfbcc3d035bec26c50ad864e7331a500d5c519f5045dc1e50458" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  6b6a29a776697ef4d1515c26d7c05d506e71d057ab95236768531062e78bc3c4)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/attention.py" 5785 "c9db8465c57f0bfb40c0194227be6e34b2c1ff7c5b5d63abca9964eed6283767" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  c942421964a2f4bacc2de46737ace7407c99213b734991ac9d80d6d8e27a9679)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/base_module.py" 9520 "0e7ddf5086179a306298693ac461ffcbc27ccb28dbc786b1a05060de7a3357c0" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  4550db48964f3030752e83e1c72125015166e98f29c3c2cb09fa2c738ed5bc55)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/config.json" 1807 "3edd2cdd1ebc823c868be55ef917e1b3b8a398fde4d3150dae44a3bf05d9f627" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  b49379bdc2b29a7e55d66e7684b58ba278a8a7e7bba91931f53cd46b782c91fe)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/conv.py" 4487 "b3adee35f27e5d372543242aa86ce5e0138f13b794b6c81f919001e3e2346723" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  14f02da9597c047b68e3a66256f4aa91c8982820e6f481aa1bbe02bd733f1c56)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/flash.py" 5763 "c1918463d303a16f278a670bb4f33d3f8d6f7653b0d473313ff5835699b86d04" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  f629f3c3b383a64e3baa5e4b2236c7aee47fa64a7d07caaa3b675d64ad2a7e83)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/func.py" 5840 "0612c26a65f095699cc7acd51937cd153584fa5a0476956e46a4679aa575c22d" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  d496ab322578978b6448682a731f0c6dada347afcc2fd597a18907d85fb0e6ae)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/klvae.py" 48594 "d05a22b4918ad303f147d6b0d0ae9038bd1af1f810a5553b04f3542ab9bcff96" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  cd34bad0d66a513eed561bdfd3bb0b7a4fecc67c8d744261ac8ffafc18b82dad)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/minimax_h3_video_vae.py" 5123 "77fdea69a48485b5434f65d08096657b5d78b78b7cdf24e1241038f237720138" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  5e3db574cfa0f50420376feaf9a39ee747867cb5731acfbe9d8f7c135a6a5ee1)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/norm.py" 10686 "258b120ca8d9a16366d7b811fe93eebf98fe1564db0995e8b7747229c651919a" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  32b9b5ea89a55cfbc3d09cbbc1aeb145117422608e69c75e7b6909c1bf9e5223)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/normalize.py" 1200 "8db651acb9eb551c906a2850bbca8e9d851f00d07b30ccf66ceb6057da687a13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  c53c9621700c63148a3c81b0d6ee069a3183d4965acecba9ca27284e859e6aa4)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/parallel.py" 12997 "7193522beafd65bc3dbe40b9843e360ab8da3a0bb211e9bfb67bb0d5d0e66919" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  f71a833ef3fefe6757a402e4250da053eeffcfc51fdb3092be7df9532baa5fec)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/source/config.json" 1164 "66c68f541e6578ce613ce7a0fc985eb59097038829e49f7535e6d08e6d95ab12" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  18fd4ffc22dd48fc381d994d5e7b919e1c57f611ff57ab4aff972032ed191df0)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/utils.py" 764 "309e45e9d9e33cd5516a10eac2d207eb9f940079a6d9bbe0ee80aaaf7eb42dcd" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  8740435bf7a3c37e2a213cd908fc49f7cfc37b2e4fe2339ae01ee355b3ba6d11)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/vae_cnn.py" 8836 "3949b701e6893bd2ea070cd5b18ed8135a7c21d884290df449b1997212d65b11" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e0d6b591aa86a90465d7197f112d48c2c78f97364fa19b03233290483444ae4e)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/vae_module.py" 1884 "9558fb302e10a619f198e12e04701c68988e897d0b627f958f33d27fd2a30d94" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  6b296624b2333131afd1d43b10a4874cfc52f882e954f4f95ba513710fec43d4)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/vae_processor.py" 8369 "32870580a1802d9163104a4d68170e35a4772106867181e1bd343dff11f87d2e" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  197b3e0ff48d15f2552613724a6b2a64d85b40b04735db740c4f381a5fa1ddac)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "FL2VA/video_vae/vae_vit.py" 13490 "a372c28441b56ec2dbc6041dbd6ce2766c64c0e61b2c69a16594a97a11da3f58" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e5b6dcd60518d8d785f847cd73bc386e49d47bbd576b5d8700eb34570a4813de)
    prefer_download_s3_artifact "sglang-s3" "$1" "Comfy-Org/MiniMax-H3" "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" 20970379616 "e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  eb27812965db98bab9180298f41629add421020e807111c667f2ec6b801b2024)
    prefer_download_s3_artifact "sglang-s3" "$1" "Comfy-Org/MiniMax-H3" "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" 15687142551 "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  f8a4b810d64ac7aae80edf1a86dcac463d9e2d49a7443584a7bcc3bc87a1f1bf)
    prefer_download_s3_artifact "sglang-s3" "$1" "Comfy-Org/MiniMax-H3" "vae/minimax_h3_audio_vae_fp32.safetensors" 605254808 "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  8b05098bd8da92c5e326c4152fe9f29834aef2489b5a098192c088e0abdb64a6)
    prefer_download_s3_artifact "sglang-s3" "$1" "Comfy-Org/MiniMax-H3" "vae/minimax_h3_video_vae_fp16.safetensors" 5207808496 "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  cefbdb47c26a2d9cfd7530197c97751b2fb838be3f7c4c6df474e8e7e472ab45)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/config.json" 1973 "d8f3bcc62e23c7e9806970fa63cca6139c06faa3797cf9c94034f60db8512771" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  03164c445d7327ea4a0fbc01638920edf4056bfdeae1ea9203a60096169f5fdd)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/config.yaml" 91 "259f675c9f71eedc24ca4f23965cd32a1b3878fc894f56664c40328d99831a5e" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  90b3b7e679a6b856a3413d16c4636245a61fcf71463d968b4ecd63abc209f953)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_activations.py" 2189 "74ca8bb9e8039f1ff362ca4219eee5240a7df9502f3dbdc3161d4e86fbd6dc04" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  247e72bfc485f160845f5522051c41d301884f3f35d0dcc1019b18b70d99a1c0)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_alias_free_act.py" 835 "db8761e66c0eaf9fce2dcccb59162d52b22ca0de9f699cf7d21ec7cd507e86fd" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  53a5efc78f1739519cfacdb528b7b2d5fc82024b85c34f5d4907c452a9788ac0)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_alias_free_filter.py" 3300 "a369523cd7f14f4f299d8e2e47f3c473da76ed1910e6e9134fd7a9fce02537e8" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  cb3c6a6aae91178f1d7d02aa097005898cabaa95cdd14b8d5b944c4a4e40582c)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_alias_free_resample.py" 1740 "fe35055893833c563e42adc5e5882cbe7628c82d48d33c300fcf0a9576997910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  d33a505cba5eeb915a10f86fd60b87294c4e7ffdecb13c5e3d19a2420dacec36)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_attn_proj.py" 3317 "0e04556fa5fd38d4a71e62fcf4d3242fd9a2464fd72ed62baef2ec0980d910c6" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  ed0fb2e418b2902b7ed1ab2b442355f7b1be46712b7912f4da2b60f6c14a4a9e)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_audio_vae.py" 7266 "ec04939602d4710d039e83f558a7572547669652f7fa967e3de0a3b6c48cfd48" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  97ebd718db0f02eda12ec5d669a0abed1cb3991966fab9564c7114622fcc6313)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_bigvgan.py" 7102 "f5df4e6f633e74da479549ef7a6d2684964e4b65ac42c6765be42f9c7fcb7bd2" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  127a5f54a82d01b4886f6e615c613bc424fd7af527be65932038052cf3391561)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/dac_utils.py" 362 "74ef0ba2c2a11ca35a7c0cc166fe88e564de01230000a0bcc8429103312ad9f0" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  6d107783bd63177c9ee197c5477688c5e99113417578b7878651273d90ee3854)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/metadata.json" 440 "755d0529d43b2b5c83590f6f44ca659bc68e6a21b01d5669c93e8b2965749bff" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  b9b1c527d89ec7ca1c89ecf6d1984d0f120e4cd23f11ac789c559b030ba317fd)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/audio_vae/minimax_h3_audio_vae.py" 3532 "63bc0dab6def69480cfd77ea820f9a9a84fc4bd6e56868e4f45ec1e1e200578f" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  47b1d01b67fe2df13f9e39e79b101baec94ccfd8b4ece7c641322edb5a87728e)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/model_index.json" 707 "b160b13700bf08aea7fce1bc3dd0d3a49ea15036298c50082ec107f87843b90c" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  def039a803ddc8227dcdbe8c702469483c29f2451b7ce38643579109d72689e2)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  35158b65febc07515ae249a6220e75c7f2c0d20c2dd413438fe05b61153e3bca)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  45744f4a728a958821b6e251f7111ddea3b655dd4b857184826433f796b165dc)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  bf2fec0c64575ab5bd8957ca68cd8ba8dad7c8ca75cd22265ad7f0460ead746a)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  1cd77b434193822c3a7526db00d2a126ef7d39fcf022654ca0f4e4b0b84270e4)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  3ee7af87d088762a967a08df8ad5da0866ee6d1163469cd286d7ed3c84392ba8)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  c55222b12846cf5c8c8cebd81c42a537ab306888ada596806a30fd4a7d2618ab)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/processor/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  932d40a3d4b1fda3fe087cea99024be5dba4543d3a3089ec4caa0f9d530c7de0)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/chat_template.json" 5499 "5c72a170d2a4a1a3bc5adad2e689ae28138a9700e5b8c96c0266331e86c0acce" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  a9c4f6a66c12e12134bc9168208b3dc49f334673e566a69b346a4f59e366147f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/config.json" 1474 "d2dd0c60d01b9e195d9447c52da61c7302d28828524914c044d9c6e1b81d0427" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  221d67d6e046f742e7e28172089cc96e81999eead245bad8fee5b85e14c239b0)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  4ea96b08125671598ae3abd1d087e8058ffe9b69b1fd2a7ccaff206f3247c2a3)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e5d72605eb8b0067faa22b4dcbe8a589158782123f5ddd66fd4d6b2fb81709a5)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  18cba62292ed3e4d1972e92649c1378ac11050edd6875112c27883b90ddc1977)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  94df1cfefc7cc274fd9d348449d026c75e59d61fcf09e6deaa78639bd80a8039)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  434a13d7eb7658186962af30c6ae511f718166834ad1073237298d1600fc71a5)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/text_encoder/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  58a285ae8c68cf5b24ceb6f7601df1f695f79cd86cc877833f03486827af1634)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/tokenizer/merges.txt" 1671839 "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  5e0b58636c189d3bc78aa642e7e1cb7483a3eef0c681f8cc01d54a5732fe265d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/tokenizer/tokenizer.json" 7032403 "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  ec574c3a9688759e09c150892060816f05b810433d824db5f4b2dd5f93ac86d9)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/tokenizer/tokenizer_config.json" 11003 "a07e942ac874baa13758de8d1fbdb186683cc03416b5589e1b6671c6b3057c68" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  b5cce8521d0922e7231cf395b12e4806cfdeafa1b647c395c65d6b77ed03cb5d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/tokenizer/vocab.json" 2776833 "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  32987bba8301dab54f2125367cec44a10b81225b2f24e12f5ffe3b22ea1e2373)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/transformer/config.json" 604 "f619093a231fcfbcc3d035bec26c50ad864e7331a500d5c519f5045dc1e50458" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  7c1f1541994d8adbb9acfc38cd23229b9c2145b18ec8684cd71b7f972ed40d0f)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/attention.py" 5785 "c9db8465c57f0bfb40c0194227be6e34b2c1ff7c5b5d63abca9964eed6283767" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  a840bd7de4b572d9448bd4f828abf3202b2ec133a4398fb1b0e87526fb0729a9)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/base_module.py" 9520 "0e7ddf5086179a306298693ac461ffcbc27ccb28dbc786b1a05060de7a3357c0" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  b3af6d16005c0e1ce72958eeeb04925e42ed2c10e1479a12c69b4a4083fc4666)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/config.json" 1807 "3edd2cdd1ebc823c868be55ef917e1b3b8a398fde4d3150dae44a3bf05d9f627" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  002655bb8c773c8226c896fee0936d54553b9fc704581764acc73ad2e26d224b)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/conv.py" 4487 "b3adee35f27e5d372543242aa86ce5e0138f13b794b6c81f919001e3e2346723" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  ff9caea90791bcad5e43dbbfd55f051a13a5a798301bb7da866abf6c5cbcc775)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/flash.py" 5763 "c1918463d303a16f278a670bb4f33d3f8d6f7653b0d473313ff5835699b86d04" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  00edbf980322c706fe3e7438c1ad6654bf1e5635d4cba79590adbdaff6afc69d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/func.py" 5840 "0612c26a65f095699cc7acd51937cd153584fa5a0476956e46a4679aa575c22d" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  d8f14bf4d50a3dec20d44e8975f0d981dd97066ea5b11b68082bb642ca481d07)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/klvae.py" 48594 "d05a22b4918ad303f147d6b0d0ae9038bd1af1f810a5553b04f3542ab9bcff96" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  7ac94323cffd7ac2488a7fc167a6863a13f7b607d67e5c9dc6f9308d356af6d4)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/minimax_h3_video_vae.py" 5123 "77fdea69a48485b5434f65d08096657b5d78b78b7cdf24e1241038f237720138" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  470810526fdaf745776eb0828072384bec39f89a65dc283d491ddbbe9b4f266d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/norm.py" 10686 "258b120ca8d9a16366d7b811fe93eebf98fe1564db0995e8b7747229c651919a" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  5de0d62499dda586ca5b3880ee64383d7b9f68648f16a22df5aac706d132283c)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/normalize.py" 1200 "8db651acb9eb551c906a2850bbca8e9d851f00d07b30ccf66ceb6057da687a13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  da4ea9d0e87ab5d25d628f049ce35c1e649219ec2a53435c7e94302e52cdeb0b)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/parallel.py" 12997 "7193522beafd65bc3dbe40b9843e360ab8da3a0bb211e9bfb67bb0d5d0e66919" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  643f218ae163bb85c7fd0084d30408090f16efbde14c7883ce260d6b5b5046a4)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/source/config.json" 1164 "66c68f541e6578ce613ce7a0fc985eb59097038829e49f7535e6d08e6d95ab12" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  021324fb3d450a9a8e717049f7107543bb62c7133da03fb8db5a85a023bbb348)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/utils.py" 764 "309e45e9d9e33cd5516a10eac2d207eb9f940079a6d9bbe0ee80aaaf7eb42dcd" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  d29b0f89a1322f74b95bc1f6638eb9864eca0fd6b407c8ca35a27f77f97e7da3)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/vae_cnn.py" 8836 "3949b701e6893bd2ea070cd5b18ed8135a7c21d884290df449b1997212d65b11" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  a32d7605df547188c02a488b3e7fec45ef6ed7ce03ff335f3300e43474de22a6)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/vae_module.py" 1884 "9558fb302e10a619f198e12e04701c68988e897d0b627f958f33d27fd2a30d94" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  01825b8b9e3577a377cb782bb8420455920dc1efada09ba1bd99e123729ceed2)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/vae_processor.py" 8369 "32870580a1802d9163104a4d68170e35a4772106867181e1bd343dff11f87d2e" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  473ebef86532b8d5a42f3bef95d5ba27d3fb63fe294922815dd20a9de28a1c6d)
    prefer_download_s3_artifact "sglang-s3" "$1" "MiniMaxAI/MiniMax-H3" "Ref2VA/video_vae/vae_vit.py" 13490 "a372c28441b56ec2dbc6041dbd6ce2766c64c0e61b2c69a16594a97a11da3f58" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  3588902454f67912fd9d4dbbdd50aa71d22a89a3356854aa1c8904c696b51c95)
    prefer_download_s3_artifact "sglang-s3" "$1" "Comfy-Org/MiniMax-H3" "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" 20970379616 "9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "chat_template.jinja" 8952 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "config.json" 73003 "7ff41ec6f96ad50efea3c92751cd261b63839d39936eb6e6ffc9066db8672740" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  919d7ee15a0fadbddfc063ea3ab00cd3e40eff57da0e06367feb477d0dfd7c05)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "generation_config.json" 214 "a4cef85934ea1fdcb207944dbc6eee70dbbf16806874428556ae33023336c0a4" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  3e6b53eec281228ca50a1417d3d768d33ee1d8578aeafb516fe50aa81401db7d)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "hf_quant_config.json" 53749 "0f39e8cd23abdfb79adc89ac1b19acad990aa6ac32973f9ab0a67d1e3449535c" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  e7e3e7f9a82fa7f51aabb6ade09bb28fa48f5d0c182c27058d4429e42c93435a)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "merges.txt" 3353259 "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  93758408a062a258fd549c4e4ba9e28bfa2b045e2ab55cd6b27487fb01afc3db)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "model-00001-of-00003.safetensors" 9965652544 "fbcdb5ba1cdda462b5f38592d071e772c4d398afea61a0aa9188b32d1a239a79" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  1b005625d88e08b27423395b98ec92f1bc2fcc747355bba89a8581f61e25757b)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "model-00002-of-00003.safetensors" 9985757064 "db6146a5464fb0a891181b93c81593f0ca65c602eb14120a1c2b1b09bca11f85" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  68ad6bf748e17568538d93aa614efd5cd86ae3b458364276787fc87ae98aa167)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "model-00003-of-00003.safetensors" 1970287672 "d3cfb92742e30c8b46564665791dbe0a86ed64cfc02b1275081530793c0c9581" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  8a0d6be7fd2bcbb0483918329bc56b1ab010eb4e59d92332a4ebdd81ebfb226b)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "model.safetensors.index.json" 214866 "7aa103a2582b7d26631988de33dea19e8a308ee9c239e8e14feb374af30905e2" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  ba5d8f1df983d9283c17076c60f2426e27f4917cfdd25e4e436826bdc563245c)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  3001036477fa91b75a2b38182de57581aa886607f24a1a4fddea200e1b4c291b)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "tokenizer.json" 12809320 "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  f3c3ca7e0bd239424a4fea839b50a052e6727c3c89c8fefaa7d1811a94bcfa63)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "tokenizer_config.json" 1121 "e5d078b00e6c1223b32444db8c1001dc71d86ceef8ee706b5bf084c3a43a1f9c" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  d46158d901e1e5079969870d919555b038173ce4ef182146087ac682bc638785)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  1d6ee74940f64d6aae63bf1f31e9f5c07fb279da96d73c9744736b58e4b96163)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "vocab.json" 6722759 "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
    *) echo "[sglang-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

sglang_s3_stage_artifact() {
  local artifact_id="$1"
  local status=0
  if sglang_s3_download_artifact_id "$artifact_id"; then
    return 0
  else
    status=$?
  fi
  echo "[sglang-download] artifact $artifact_id: S3 staging unavailable or invalid (status $status); falling back to Hugging Face" >&2
  sglang_download_artifact_id "$artifact_id"
}

sglang_download_model_keys() {
  prefer_download_model_keys_hf \
    "sglang-download" "${SGLANG_DOWNLOAD_JOBS:-4}" 8 \
    sglang_model_artifact_ids sglang_artifact_record "$@"
}

sglang_download_model_keys_s3() {
  prefer_download_model_keys \
    "sglang-s3-download" "${SGLANG_DOWNLOAD_JOBS:-4}" 8 \
    sglang_model_artifact_ids sglang_s3_stage_artifact "$@"
}

sglang_download_model_key() {
  sglang_download_model_keys "$1"
}

download_model_key() {
  sglang_download_model_key "$1"
}
