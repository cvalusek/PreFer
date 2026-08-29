#!/usr/bin/env bash
set -euo pipefail

readonly AUDIO_GENERATED_MODEL_KEYS="qwen3-tts-0.6b-bf16,qwen3-tts-1.7b-customvoice-bf16,ace-step-1.5-turbo-q8,minimax-music-3-q4,personaplex-7b-q4,qwen3-asr-0.6b-q8,qwen3-tts-1.7b-voicedesign-bf16"

audio_verify_artifact() {
  local path="$1"
  local expected_size="$2"
  local expected_sha256="$3"
  [ -f "$path" ] || return 1
  [ "$(stat -c '%s' "$path")" = "$expected_size" ] || return 1
  [ "$(sha256sum "$path" | cut -d ' ' -f 1)" = "$expected_sha256" ]
}

audio_download_artifact() {
  local key="$1"
  local repo="$2"
  local revision="$3"
  local artifact="$4"
  local expected_size="$5"
  local expected_sha256="$6"
  local destination="/models/$repo/$artifact"
  local partial="${destination}.partial"
  local url="https://huggingface.co/$repo/resolve/$revision/$artifact?download=true"

  mkdir -p "$(dirname "$destination")"
  if audio_verify_artifact "$destination" "$expected_size" "$expected_sha256"; then
    echo "[audio-download] $key: exact artifact already present"
    return
  fi

  rm -f "$destination"
  echo "[audio-download] $key: downloading pinned artifact"
  curl --fail --location --retry 5 --retry-all-errors --continue-at - --output "$partial" "$url"
  if ! audio_verify_artifact "$partial" "$expected_size" "$expected_sha256"; then
    echo "[audio-download] $key: size or SHA-256 validation failed" >&2
    rm -f "$partial"
    return 1
  fi
  mv -f "$partial" "$destination"
}

audio_download_model_key() {
  case "$1" in
  qwen3-tts-0.6b-bf16)
    audio_download_artifact "qwen3-tts-0.6b-bf16" "audio-cpp/audio.cpp-gguf" "89c1e5437d5df724c5d36fca23f1e98e3d5185d7" "Qwen3-TTS-12Hz-0.6B-Base-GGUF/qwen3-tts-12hz-0.6b-base-bf16.gguf" 2516154496 "97d418048b07b5b267628da955b27db4c57b353ded8089de01a469b474255b8d"
    ;;
  qwen3-tts-1.7b-customvoice-bf16)
    audio_download_artifact "qwen3-tts-1.7b-customvoice-bf16" "audio-cpp/audio.cpp-gguf" "09fe073ba154561f4474162e8bd4ab233a848eca" "Qwen3-TTS-12Hz-1.7B-CustomVoice-GGUF/qwen3-tts-12hz-1.7b-customvoice-bf16.gguf" 4179144352 "ef55652c7aa919dc5eeb7967c782a17a6f5d9a8b775337376a4678d37e71a11c"
    ;;
  ace-step-1.5-turbo-q8)
    audio_download_artifact "ace-step-1.5-turbo-q8" "audio-cpp/audio.cpp-gguf" "315d31fe91fdfd30d36a1deb08e89ff25a8bece5" "ACE-Step1.5-GGUF/turbo/ace-step-1.5-turbo-q8_0.gguf" 6185460032 "cd7bf272588f548d4a253f57483132ef0f8f54a549f26471b09caa72c654270b"
    ;;
  minimax-music-3-q4)
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config.json" 107 "1ffcff67d916d5519d1ef9a36853232ee6bcb7e14a936623c4e85559f5dce106"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/language_model.json" 1596 "34ded58fcd5e8181557f1417e76af9f3e95109a5ce113a4771fd16f8625b53c0"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/rvq_depth_decoder.json" 274 "b38c7f72d4b2fa8667442071f9e4a63ca5a7b5d0859e5e64ee7f79c4bc64520c"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/condition_encoder.json" 292 "1cdea3f36506719128ae4a29cdfff74b1134e607eb4a504ce6d810568fac8263"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/transformer.json" 294 "f60856be934127a8b8223510aff2e38a9efd8bbdbc230c3d3339b96e2cb12f00"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/vocoder.json" 251 "4161afd07ba7d5b949e29c8a7a005592259fba73e9110b6ece9dfd38d3489eac"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "tokenizer/tokenizer.json" 11423801 "b1537fa9e59a537276ecbc2e12d0438edff635a1f4a4948e679774b5feb3e610"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "tokenizer/tokenizer_config.json" 377 "1689852cc9c45010de040c8302a8acdc0d2c4c6c740dd7e9dd0a8c704e16eada"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "language_model_q4_0.gguf" 6006866496 "6f621dd636320403c03e9f755b3e2047f5754d055e0fcc6c0c444ae52ffbfa90"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "rvq_depth_decoder_q8_0.gguf" 714028960 "d5b7495fb1a7845abfeab13df829510de442fd4ea0fd55467fe9895fe8ec5db6"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "condition_encoder.gguf" 100677184 "7f9414097b1f6ad154dae08ed69ce88fd0db6d7fd422f4d1a847216ca28ba1bf"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "transformer_q4_0.gguf" 1396392768 "18d3b2461a2988f59e197ccf05dc3931663099290b42443baa2a30e4fd15e506"
    audio_download_artifact "minimax-music-3-q4" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "vocoder.gguf" 216704192 "0a768b596516678fc850da1aff36556b8bc6bafcb7b42bc7ba7cb46cb9927a42"
    ;;
  personaplex-7b-q4)
    audio_download_artifact "personaplex-7b-q4" "audio-cpp/audio.cpp-gguf" "315d31fe91fdfd30d36a1deb08e89ff25a8bece5" "PersonaPlex-GGUF/personaplex-7b-v1-q4_k.gguf" 7860681248 "257347f65ed2cf563d44499144636f7999a78fe9547c27b5eb057b4ce9cc3665"
    ;;
  qwen3-asr-0.6b-q8)
    audio_download_artifact "qwen3-asr-0.6b-q8" "audio-cpp/audio.cpp-gguf" "09fe073ba154561f4474162e8bd4ab233a848eca" "Qwen3-ASR-0.6B-GGUF/qwen3-asr-0.6b-q8_0.gguf" 1151272416 "6c44ec2fb4cee513892d7863c1fcc3ea6b699ffa4d899b0ef4ab19956d9544f7"
    ;;
  qwen3-tts-1.7b-voicedesign-bf16)
    audio_download_artifact "qwen3-tts-1.7b-voicedesign-bf16" "audio-cpp/audio.cpp-gguf" "09fe073ba154561f4474162e8bd4ab233a848eca" "Qwen3-TTS-12Hz-1.7B-VoiceDesign-GGUF/qwen3-tts-12hz-1.7b-voicedesign-bf16.gguf" 4179089248 "f4cebcd68023a2db7c3fc8d52d1d28eafb22d4e3b7a64e12c4f946a300536f86"
    ;;
    *) echo "[audio-download] unknown model key: $1" >&2; return 2 ;;
  esac
}
