#!/usr/bin/env bash
set -euo pipefail

IMAGE_GENERATED_MODEL_KEYS="flux-2-klein-4b-bf16-q8,qwen-image-q4,qwen-image-edit-2511-q4,sdxl-1.0-fp16,z-image-turbo-q8"

image_download_artifact() {
  local repo="$1" revision="$2" path="$3" expected_size="$4" expected_sha="$5"
  local destination="/models/${repo}/${path}"
  local partial="${destination}.partial.$$"
  mkdir -p "$(dirname "$destination")"
  if [ -f "$destination" ]; then
    local existing_size existing_sha
    existing_size="$(stat -c %s "$destination")"
    existing_sha="$(sha256sum "$destination" | awk '{print $1}')"
    if [ "$existing_size" = "$expected_size" ] && [ "$existing_sha" = "$expected_sha" ]; then
      echo "[image-download] verified $repo/$path"
      return
    fi
    echo "[image-download] replacing invalid $repo/$path" >&2
    rm -f "$destination"
  fi
  local auth=()
  if [ -n "${HF_TOKEN:-}" ]; then
    auth=(-H "Authorization: Bearer $HF_TOKEN")
  fi
  trap 'rm -f "$partial"' RETURN
  curl --fail --location --retry 5 --retry-all-errors "${auth[@]}"     "https://huggingface.co/${repo}/resolve/${revision}/${path}?download=true"     --output "$partial"
  local actual_size actual_sha
  actual_size="$(stat -c %s "$partial")"
  actual_sha="$(sha256sum "$partial" | awk '{print $1}')"
  if [ "$actual_size" != "$expected_size" ] || [ "$actual_sha" != "$expected_sha" ]; then
    echo "[image-download] integrity failure for $repo/$path" >&2
    return 1
  fi
  mv "$partial" "$destination"
  trap - RETURN
}

image_download_model_key() {
  case "$1" in
  flux-2-klein-4b-bf16-q8)
    image_download_artifact "black-forest-labs/FLUX.2-klein-4B" "e7b7dc27f91deacad38e78976d1f2b499d76a294" "flux-2-klein-4b.safetensors" "7751105712" "ec3d4e733a771f61c052fb4856c48b336c55eaf2c65487c2a1faeb9bbda7a343" || return $?
    image_download_artifact "black-forest-labs/FLUX.2-small-decoder" "a3efc24f613ef42d9428af62fdbd6f5fd8856c4a" "full_encoder_small_decoder.safetensors" "249519092" "ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62" || return $?
    image_download_artifact "unsloth/Qwen3-4B-GGUF" "22c9fc8a8c7700b76a1789366280a6a5a1ad1120" "Qwen3-4B-Q8_0.gguf" "4280405792" "eed555233267a33c7e8ee31682762cc7751b3f6d224039086e0e846f05fffa5d" || return $?
    ;;
  flux-2-klein-4b-q4)
    image_download_artifact "leejet/FLUX.2-klein-4B-GGUF" "3b1f5a9dc3abb32238b053aeb3d823c30afdacbd" "flux-2-klein-4b-Q4_0.gguf" "2460378560" "d1023499ef3f2f82ff7c50e6778495195c1b6cc34835741778868428111f9ff4" || return $?
    image_download_artifact "black-forest-labs/FLUX.2-small-decoder" "a3efc24f613ef42d9428af62fdbd6f5fd8856c4a" "full_encoder_small_decoder.safetensors" "249519092" "ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62" || return $?
    image_download_artifact "unsloth/Qwen3-4B-GGUF" "22c9fc8a8c7700b76a1789366280a6a5a1ad1120" "Qwen3-4B-Q4_K_M.gguf" "2497281312" "f6f851777709861056efcdad3af01da38b31223a3ba26e61a4f8bf3a2195813a" || return $?
    ;;
  flux-2-klein-4b-q8)
    image_download_artifact "leejet/FLUX.2-klein-4B-GGUF" "3b1f5a9dc3abb32238b053aeb3d823c30afdacbd" "flux-2-klein-4b-Q8_0.gguf" "4300629440" "0bba6951258ec8f92d51114a8fa13e66828297bfff58a738f52729b3ef66fa28" || return $?
    image_download_artifact "black-forest-labs/FLUX.2-small-decoder" "a3efc24f613ef42d9428af62fdbd6f5fd8856c4a" "full_encoder_small_decoder.safetensors" "249519092" "ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62" || return $?
    image_download_artifact "unsloth/Qwen3-4B-GGUF" "22c9fc8a8c7700b76a1789366280a6a5a1ad1120" "Qwen3-4B-Q8_0.gguf" "4280405792" "eed555233267a33c7e8ee31682762cc7751b3f6d224039086e0e846f05fffa5d" || return $?
    ;;
  flux-2-klein-4b-q8-q4)
    image_download_artifact "leejet/FLUX.2-klein-4B-GGUF" "3b1f5a9dc3abb32238b053aeb3d823c30afdacbd" "flux-2-klein-4b-Q8_0.gguf" "4300629440" "0bba6951258ec8f92d51114a8fa13e66828297bfff58a738f52729b3ef66fa28" || return $?
    image_download_artifact "black-forest-labs/FLUX.2-small-decoder" "a3efc24f613ef42d9428af62fdbd6f5fd8856c4a" "full_encoder_small_decoder.safetensors" "249519092" "ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62" || return $?
    image_download_artifact "unsloth/Qwen3-4B-GGUF" "22c9fc8a8c7700b76a1789366280a6a5a1ad1120" "Qwen3-4B-Q4_K_M.gguf" "2497281312" "f6f851777709861056efcdad3af01da38b31223a3ba26e61a4f8bf3a2195813a" || return $?
    ;;
  qwen-image-q4)
    image_download_artifact "unsloth/Qwen-Image-GGUF" "8aa13c32cf6dda8ad5cb5e3a1beb93150faa246b" "qwen-image-Q4_K_M.gguf" "13127088672" "eb2d4719dda7c73c52c1685673d173f4c1407e78688c2869352cef3ef7ba3819" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" "253806246" "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f" || return $?
    image_download_artifact "mradermacher/Qwen2.5-VL-7B-Instruct-GGUF" "cfa2baa09946b211c107e6e104948987a64dd2c1" "Qwen2.5-VL-7B-Instruct.Q4_K_M.gguf" "4683072512" "0f00a930ba3108b6861ddadf74d8ebbd82e257c63eba728e62c3e8970f5eed94" || return $?
    ;;
  qwen-image-q6)
    image_download_artifact "QuantStack/Qwen-Image-GGUF" "257f261fa92593bed760aa6fa3f7921a49fea00f" "Qwen_Image-Q6_K.gguf" "16824990240" "0c60643ee869161ee7acd530f7faf1cb2361f131e1ebae27b95fdc481b6df2b2" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" "253806246" "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "b8f0a47470ec2a0724d6267ca696235e441baa5d" "split_files/text_encoders/qwen_2.5_vl_7b.safetensors" "16584415576" "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a" || return $?
    ;;
  qwen-image-q8)
    image_download_artifact "unsloth/Qwen-Image-GGUF" "8aa13c32cf6dda8ad5cb5e3a1beb93150faa246b" "qwen-image-Q8_0.gguf" "21761817120" "43142b32778dc0568c27395abc6f8291ac53f1de0b98eed919712cf161f248de" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" "253806246" "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "b8f0a47470ec2a0724d6267ca696235e441baa5d" "split_files/text_encoders/qwen_2.5_vl_7b.safetensors" "16584415576" "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a" || return $?
    ;;
  qwen-image-edit-2511-q4)
    image_download_artifact "unsloth/Qwen-Image-Edit-2511-GGUF" "0d33d9692b4b26212297240d87b0d4719aa4fd06" "qwen-image-edit-2511-Q4_K_M.gguf" "13244758624" "8677bac90627adbbc11efab87b1870e701c4eb3689ee865a3de8ab81b705a723" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" "253806246" "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "b8f0a47470ec2a0724d6267ca696235e441baa5d" "split_files/text_encoders/qwen_2.5_vl_7b.safetensors" "16584415576" "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a" || return $?
    ;;
  qwen-image-edit-2511-q6)
    image_download_artifact "unsloth/Qwen-Image-Edit-2511-GGUF" "0d33d9692b4b26212297240d87b0d4719aa4fd06" "qwen-image-edit-2511-Q6_K.gguf" "16852417120" "fdc28e5b8f7d9cfe0399fd1700c375f25f000fc4159bbdb0d4a809ae898eb759" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" "253806246" "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "b8f0a47470ec2a0724d6267ca696235e441baa5d" "split_files/text_encoders/qwen_2.5_vl_7b.safetensors" "16584415576" "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a" || return $?
    ;;
  qwen-image-edit-2511-q8)
    image_download_artifact "unsloth/Qwen-Image-Edit-2511-GGUF" "0d33d9692b4b26212297240d87b0d4719aa4fd06" "qwen-image-edit-2511-Q8_0.gguf" "21761817184" "ab4f0622fb002fccaaa679a2ecce6fd1b3190d8ea28a5b7b2b17b8669bc24afa" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" "253806246" "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f" || return $?
    image_download_artifact "Comfy-Org/Qwen-Image_ComfyUI" "b8f0a47470ec2a0724d6267ca696235e441baa5d" "split_files/text_encoders/qwen_2.5_vl_7b.safetensors" "16584415576" "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a" || return $?
    ;;
  sdxl-1.0-fp16)
    image_download_artifact "stabilityai/stable-diffusion-xl-base-1.0" "462165984030d82259a11f4367a4eed129e94a7b" "sd_xl_base_1.0.safetensors" "6938078334" "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b" || return $?
    ;;
  z-image-turbo-q4)
    image_download_artifact "leejet/Z-Image-Turbo-GGUF" "c61c0e422dc8b541b7548cf33a4ef8302b0f8085" "z_image_turbo-Q4_K.gguf" "3864250304" "14b375ab4f226bc5378f68f37e899ef3c2242b8541e61e2bc1aff40976086fbd" || return $?
    image_download_artifact "black-forest-labs/FLUX.1-schnell" "741f7c3ce8b383c54771c7003378a50191e9efe9" "ae.safetensors" "335304388" "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38" || return $?
    image_download_artifact "unsloth/Qwen3-4B-Instruct-2507-GGUF" "a06e946bb6b655725eafa393f4a9745d460374c9" "Qwen3-4B-Instruct-2507-Q4_K_M.gguf" "2497281120" "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597" || return $?
    ;;
  z-image-turbo-q6)
    image_download_artifact "leejet/Z-Image-Turbo-GGUF" "c61c0e422dc8b541b7548cf33a4ef8302b0f8085" "z_image_turbo-Q6_K.gguf" "5263239104" "319f627beac8059b7546f36a7b4d5097b7f4ee6a1fc37585d0f75ca1d12d01af" || return $?
    image_download_artifact "black-forest-labs/FLUX.1-schnell" "741f7c3ce8b383c54771c7003378a50191e9efe9" "ae.safetensors" "335304388" "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38" || return $?
    image_download_artifact "unsloth/Qwen3-4B-Instruct-2507-GGUF" "a06e946bb6b655725eafa393f4a9745d460374c9" "Qwen3-4B-Instruct-2507-Q4_K_M.gguf" "2497281120" "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597" || return $?
    ;;
  z-image-turbo-q8)
    image_download_artifact "leejet/Z-Image-Turbo-GGUF" "c61c0e422dc8b541b7548cf33a4ef8302b0f8085" "z_image_turbo-Q8_0.gguf" "6577440704" "df1c5baa86d1398c979495a6072dbcee79444fdb884a2445582ba0769c44e9a1" || return $?
    image_download_artifact "black-forest-labs/FLUX.1-schnell" "741f7c3ce8b383c54771c7003378a50191e9efe9" "ae.safetensors" "335304388" "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38" || return $?
    image_download_artifact "unsloth/Qwen3-4B-Instruct-2507-GGUF" "a06e946bb6b655725eafa393f4a9745d460374c9" "Qwen3-4B-Instruct-2507-Q8_0.gguf" "4280405600" "391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068" || return $?
    ;;
  *)
    echo "[image-download] unknown catalog key: $1" >&2
    return 2
    ;;
  esac
}
