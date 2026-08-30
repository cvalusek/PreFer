#!/usr/bin/env bash
set -euo pipefail

readonly AUDIO_GENERATED_MODEL_KEYS="qwen3-tts-0.6b-bf16,qwen3-tts-1.7b-customvoice-bf16,ace-step-1.5-turbo-q8,minimax-music-3-q4,personaplex-7b-q4,qwen3-asr-0.6b-q8,qwen3-tts-1.7b-voicedesign-bf16"

audio_model_artifact_ids() {
  case "$1" in
  qwen3-tts-0.6b-bf16)
    printf '%s\n' "633f69b9c26d833afb4b1a9ecf6344564d9446e26e355db7ea4c12ca618b4fe7"
    ;;
  qwen3-tts-1.7b-customvoice-bf16)
    printf '%s\n' "f917a101f7297c7c870accde56e3830c2b1720b76d8f772cef66eac247d56a85"
    ;;
  ace-step-1.5-turbo-q8)
    printf '%s\n' "fe26e9958bf2ec7be33e14a7b4a276f0a36553f9176a8a30a22030f5f74b7014"
    ;;
  minimax-music-3-q4)
    printf '%s\n' "e2312b1635d863f99b0769aabbcf389c94758cbf3d1bac0c55106740224fd479" "fde2e48fb521169c76cab55951fcd62669fa8ccc12525dff468f6e9db5833385" "4e34839f947ff098e86f7646e84516ac92c30f11de4250a82530cd165702c951" "5033bb497295f6f098be8e48432a94bf4b93b11ed18ee4b3ff9f9648ad908853" "186f9ab9a69632519f16fa89b698861ff68024a2b721b73051e7315882517220" "a3daa11c7374b523eefaf75e5e2c48b64694337bc070a1f09eb86ef01cd71b22" "7d139537053358db8b7e4b3a49d7469d451df71d67ef35e1252068b10c344c86" "714e7807dcc4792108457f49812b96cc4de73472f97168bb920d75da2052281d" "59119e92976fe08e8f293e02ac1b82e6cbf8f3d68ebd6082e758b2aa86518450" "3da223ca93de4dcfe84df20d10923aaa8e6b4a1401628a6f2e9ce726adb3d37a" "be712634b571d30786c3e2a9799a37cafe4fb0a3cae4cd1fbac67d4fdb362acc" "ea4ca4d8ef5a3076b43ed94c62cea215a10b397264149af0a95f473ae9e1ebe0" "4e127b6b8b4e31c01b2bf9bbce2203e6e1c32a8f4af2e1bc30dd6585ee0a23ef"
    ;;
  personaplex-7b-q4)
    printf '%s\n' "90f5f3190d987f975522d17f8317a0ac9f4e84cd82c5ae0d20942d5c1e72e9a6"
    ;;
  qwen3-asr-0.6b-q8)
    printf '%s\n' "ceca49cf1a0d2d17bdb701ec4616fd1732f1a733efb5b4bb13129bfa630b1423"
    ;;
  qwen3-tts-1.7b-voicedesign-bf16)
    printf '%s\n' "837a015b90e09dd7b21b1a3f37db8a9b986a54fbc08a7a6212703d93b4c8aeeb"
    ;;
    *) echo "[audio-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

audio_download_artifact_id() {
  case "$1" in
  633f69b9c26d833afb4b1a9ecf6344564d9446e26e355db7ea4c12ca618b4fe7)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/audio.cpp-gguf" "89c1e5437d5df724c5d36fca23f1e98e3d5185d7" "Qwen3-TTS-12Hz-0.6B-Base-GGUF/qwen3-tts-12hz-0.6b-base-bf16.gguf" 2516154496 "97d418048b07b5b267628da955b27db4c57b353ded8089de01a469b474255b8d"
    ;;
  f917a101f7297c7c870accde56e3830c2b1720b76d8f772cef66eac247d56a85)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/audio.cpp-gguf" "09fe073ba154561f4474162e8bd4ab233a848eca" "Qwen3-TTS-12Hz-1.7B-CustomVoice-GGUF/qwen3-tts-12hz-1.7b-customvoice-bf16.gguf" 4179144352 "ef55652c7aa919dc5eeb7967c782a17a6f5d9a8b775337376a4678d37e71a11c"
    ;;
  fe26e9958bf2ec7be33e14a7b4a276f0a36553f9176a8a30a22030f5f74b7014)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/audio.cpp-gguf" "315d31fe91fdfd30d36a1deb08e89ff25a8bece5" "ACE-Step1.5-GGUF/turbo/ace-step-1.5-turbo-q8_0.gguf" 6185460032 "cd7bf272588f548d4a253f57483132ef0f8f54a549f26471b09caa72c654270b"
    ;;
  e2312b1635d863f99b0769aabbcf389c94758cbf3d1bac0c55106740224fd479)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config.json" 107 "1ffcff67d916d5519d1ef9a36853232ee6bcb7e14a936623c4e85559f5dce106"
    ;;
  fde2e48fb521169c76cab55951fcd62669fa8ccc12525dff468f6e9db5833385)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/language_model.json" 1596 "34ded58fcd5e8181557f1417e76af9f3e95109a5ce113a4771fd16f8625b53c0"
    ;;
  4e34839f947ff098e86f7646e84516ac92c30f11de4250a82530cd165702c951)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/rvq_depth_decoder.json" 274 "b38c7f72d4b2fa8667442071f9e4a63ca5a7b5d0859e5e64ee7f79c4bc64520c"
    ;;
  5033bb497295f6f098be8e48432a94bf4b93b11ed18ee4b3ff9f9648ad908853)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/condition_encoder.json" 292 "1cdea3f36506719128ae4a29cdfff74b1134e607eb4a504ce6d810568fac8263"
    ;;
  186f9ab9a69632519f16fa89b698861ff68024a2b721b73051e7315882517220)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/transformer.json" 294 "f60856be934127a8b8223510aff2e38a9efd8bbdbc230c3d3339b96e2cb12f00"
    ;;
  a3daa11c7374b523eefaf75e5e2c48b64694337bc070a1f09eb86ef01cd71b22)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "config/vocoder.json" 251 "4161afd07ba7d5b949e29c8a7a005592259fba73e9110b6ece9dfd38d3489eac"
    ;;
  7d139537053358db8b7e4b3a49d7469d451df71d67ef35e1252068b10c344c86)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "tokenizer/tokenizer.json" 11423801 "b1537fa9e59a537276ecbc2e12d0438edff635a1f4a4948e679774b5feb3e610"
    ;;
  714e7807dcc4792108457f49812b96cc4de73472f97168bb920d75da2052281d)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "tokenizer/tokenizer_config.json" 377 "1689852cc9c45010de040c8302a8acdc0d2c4c6c740dd7e9dd0a8c704e16eada"
    ;;
  59119e92976fe08e8f293e02ac1b82e6cbf8f3d68ebd6082e758b2aa86518450)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "language_model_q4_0.gguf" 6006866496 "6f621dd636320403c03e9f755b3e2047f5754d055e0fcc6c0c444ae52ffbfa90"
    ;;
  3da223ca93de4dcfe84df20d10923aaa8e6b4a1401628a6f2e9ce726adb3d37a)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "rvq_depth_decoder_q8_0.gguf" 714028960 "d5b7495fb1a7845abfeab13df829510de442fd4ea0fd55467fe9895fe8ec5db6"
    ;;
  be712634b571d30786c3e2a9799a37cafe4fb0a3cae4cd1fbac67d4fdb362acc)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "condition_encoder.gguf" 100677184 "7f9414097b1f6ad154dae08ed69ce88fd0db6d7fd422f4d1a847216ca28ba1bf"
    ;;
  ea4ca4d8ef5a3076b43ed94c62cea215a10b397264149af0a95f473ae9e1ebe0)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "transformer_q4_0.gguf" 1396392768 "18d3b2461a2988f59e197ccf05dc3931663099290b42443baa2a30e4fd15e506"
    ;;
  4e127b6b8b4e31c01b2bf9bbce2203e6e1c32a8f4af2e1bc30dd6585ee0a23ef)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/MiniMax-Music3-GGUF" "2a19a42dd84d9ab9411316977ff3c9fd143ab214" "vocoder.gguf" 216704192 "0a768b596516678fc850da1aff36556b8bc6bafcb7b42bc7ba7cb46cb9927a42"
    ;;
  90f5f3190d987f975522d17f8317a0ac9f4e84cd82c5ae0d20942d5c1e72e9a6)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/audio.cpp-gguf" "315d31fe91fdfd30d36a1deb08e89ff25a8bece5" "PersonaPlex-GGUF/personaplex-7b-v1-q4_k.gguf" 7860681248 "257347f65ed2cf563d44499144636f7999a78fe9547c27b5eb057b4ce9cc3665"
    ;;
  ceca49cf1a0d2d17bdb701ec4616fd1732f1a733efb5b4bb13129bfa630b1423)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/audio.cpp-gguf" "09fe073ba154561f4474162e8bd4ab233a848eca" "Qwen3-ASR-0.6B-GGUF/qwen3-asr-0.6b-q8_0.gguf" 1151272416 "6c44ec2fb4cee513892d7863c1fcc3ea6b699ffa4d899b0ef4ab19956d9544f7"
    ;;
  837a015b90e09dd7b21b1a3f37db8a9b986a54fbc08a7a6212703d93b4c8aeeb)
    prefer_download_hf_artifact "audio-download" "$1" "audio-cpp/audio.cpp-gguf" "09fe073ba154561f4474162e8bd4ab233a848eca" "Qwen3-TTS-12Hz-1.7B-VoiceDesign-GGUF/qwen3-tts-12hz-1.7b-voicedesign-bf16.gguf" 4179089248 "f4cebcd68023a2db7c3fc8d52d1d28eafb22d4e3b7a64e12c4f946a300536f86"
    ;;
    *) echo "[audio-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

audio_download_model_keys() {
  prefer_download_model_keys     "audio-download" "${AUDIO_DOWNLOAD_JOBS:-4}" 8     audio_model_artifact_ids audio_download_artifact_id "$@"
}

audio_download_model_key() {
  audio_download_model_keys "$1"
}
