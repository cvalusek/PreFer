#!/usr/bin/env bash
set -euo pipefail

readonly IMAGE_GENERATED_MODEL_KEYS="flux-2-klein-4b-bf16-q8,qwen-image-q4,qwen-image-edit-2511-q4,sdxl-1.0-fp16,z-image-turbo-q8"

image_model_artifact_ids() {
  case "$1" in
  flux-2-klein-4b-bf16-q8)
    printf '%s\n' "210aa23a176e3648cd3633eaa112f3b8449e3173ad2047c08ff889cbf334bb92" "900d4ebd91cbff32d139f031889d2dd21e070db74bc868613f893d63aa1c84cc" "0150ca6c64b0e0863a564e1da8f1f278007601b7624336fadf72adcea4c8ce2f"
    ;;
  flux-2-klein-4b-q4)
    printf '%s\n' "01165789166308ea474de2213b29475c85c8a222aac7118651bd96b856ad6b68" "900d4ebd91cbff32d139f031889d2dd21e070db74bc868613f893d63aa1c84cc" "f7d004c0eaa2166a3c4e80368e8d21ac726893b45ab8b492db7f0cb508ef9ecb"
    ;;
  flux-2-klein-4b-q8)
    printf '%s\n' "7f399b83a0a0715d49e5d8c033d148abf5b32edbd2709b1bfc47745da6482b7d" "900d4ebd91cbff32d139f031889d2dd21e070db74bc868613f893d63aa1c84cc" "0150ca6c64b0e0863a564e1da8f1f278007601b7624336fadf72adcea4c8ce2f"
    ;;
  flux-2-klein-4b-q8-q4)
    printf '%s\n' "7f399b83a0a0715d49e5d8c033d148abf5b32edbd2709b1bfc47745da6482b7d" "900d4ebd91cbff32d139f031889d2dd21e070db74bc868613f893d63aa1c84cc" "f7d004c0eaa2166a3c4e80368e8d21ac726893b45ab8b492db7f0cb508ef9ecb"
    ;;
  qwen-image-q4)
    printf '%s\n' "bf60def0faa970060bebab180315453daae00dd554b12de53052b55b94893f5c" "684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d" "337b325fce8cb552dc0d51e0880ac386e5d680b23cb06422435312a9873d2f62"
    ;;
  qwen-image-q6)
    printf '%s\n' "a502d3ada226288d058b4cfec0aca45f456b20f61695fdb933712fe83633fb6c" "684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d" "9f951bc71a8f27960fb74b41752b2ed0fceeef18f08ec2c2a2bdade9bc0143d5"
    ;;
  qwen-image-q8)
    printf '%s\n' "1ebfe982684a301826b735b09cfcb7e7ae387bc8cf9d422fee426bf45a2f446c" "684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d" "9f951bc71a8f27960fb74b41752b2ed0fceeef18f08ec2c2a2bdade9bc0143d5"
    ;;
  qwen-image-edit-2511-q4)
    printf '%s\n' "ac2728487ff2918bac75ee1c62c0fd974cdece6bd502faefc3989c050c234678" "684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d" "9f951bc71a8f27960fb74b41752b2ed0fceeef18f08ec2c2a2bdade9bc0143d5"
    ;;
  qwen-image-edit-2511-q6)
    printf '%s\n' "947ebf8d6870ad91d0c511caefab3f90b492077a01f5f2d8e334e2f5f8248295" "684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d" "9f951bc71a8f27960fb74b41752b2ed0fceeef18f08ec2c2a2bdade9bc0143d5"
    ;;
  qwen-image-edit-2511-q8)
    printf '%s\n' "d6a2d371ee99322045f393ca3139ba9e5cc794efa3276db4c3918b01ebbd1ba5" "684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d" "9f951bc71a8f27960fb74b41752b2ed0fceeef18f08ec2c2a2bdade9bc0143d5"
    ;;
  sdxl-1.0-fp16)
    printf '%s\n' "a9c4f3a30836c7c2c884f2e3dde4baa508630a610060b601b92e0eb1489a20d2"
    ;;
  z-image-turbo-q4)
    printf '%s\n' "3724203525019941ed98882738819c5ec584b1afc8365cbbe8f035aa6e7cdc1c" "31a793bd611bfa467570c448d3ff7bc0375910cad989d831225c73acf3bd20e7" "b719a79fbdae383139a34765ea67544f968c151943e90d2cc81e0eb39c5ed4b9"
    ;;
  z-image-turbo-q6)
    printf '%s\n' "04616f33385eb60de990bd2e0e5895f1e32c1f8e7426b18abc1e7c1d54bb0c24" "31a793bd611bfa467570c448d3ff7bc0375910cad989d831225c73acf3bd20e7" "b719a79fbdae383139a34765ea67544f968c151943e90d2cc81e0eb39c5ed4b9"
    ;;
  z-image-turbo-q8)
    printf '%s\n' "8470d08965457ec86390102406e1dd3abf4958e562f60352a25f12b9c791687c" "31a793bd611bfa467570c448d3ff7bc0375910cad989d831225c73acf3bd20e7" "768de660218e86a55540d8463b08f716891a80052e804da1dac9ef5e066e5162"
    ;;
    *) echo "[image-download] unknown catalog key: $1" >&2; return 2 ;;
  esac
}

image_download_artifact_id() {
  case "$1" in
  210aa23a176e3648cd3633eaa112f3b8449e3173ad2047c08ff889cbf334bb92)
    prefer_download_hf_artifact "image-download" "$1" "black-forest-labs/FLUX.2-klein-4B" "e7b7dc27f91deacad38e78976d1f2b499d76a294" "flux-2-klein-4b.safetensors" 7751105712 "ec3d4e733a771f61c052fb4856c48b336c55eaf2c65487c2a1faeb9bbda7a343"
    ;;
  900d4ebd91cbff32d139f031889d2dd21e070db74bc868613f893d63aa1c84cc)
    prefer_download_hf_artifact "image-download" "$1" "black-forest-labs/FLUX.2-small-decoder" "a3efc24f613ef42d9428af62fdbd6f5fd8856c4a" "full_encoder_small_decoder.safetensors" 249519092 "ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62"
    ;;
  0150ca6c64b0e0863a564e1da8f1f278007601b7624336fadf72adcea4c8ce2f)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen3-4B-GGUF" "22c9fc8a8c7700b76a1789366280a6a5a1ad1120" "Qwen3-4B-Q8_0.gguf" 4280405792 "eed555233267a33c7e8ee31682762cc7751b3f6d224039086e0e846f05fffa5d"
    ;;
  01165789166308ea474de2213b29475c85c8a222aac7118651bd96b856ad6b68)
    prefer_download_hf_artifact "image-download" "$1" "leejet/FLUX.2-klein-4B-GGUF" "3b1f5a9dc3abb32238b053aeb3d823c30afdacbd" "flux-2-klein-4b-Q4_0.gguf" 2460378560 "d1023499ef3f2f82ff7c50e6778495195c1b6cc34835741778868428111f9ff4"
    ;;
  f7d004c0eaa2166a3c4e80368e8d21ac726893b45ab8b492db7f0cb508ef9ecb)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen3-4B-GGUF" "22c9fc8a8c7700b76a1789366280a6a5a1ad1120" "Qwen3-4B-Q4_K_M.gguf" 2497281312 "f6f851777709861056efcdad3af01da38b31223a3ba26e61a4f8bf3a2195813a"
    ;;
  7f399b83a0a0715d49e5d8c033d148abf5b32edbd2709b1bfc47745da6482b7d)
    prefer_download_hf_artifact "image-download" "$1" "leejet/FLUX.2-klein-4B-GGUF" "3b1f5a9dc3abb32238b053aeb3d823c30afdacbd" "flux-2-klein-4b-Q8_0.gguf" 4300629440 "0bba6951258ec8f92d51114a8fa13e66828297bfff58a738f52729b3ef66fa28"
    ;;
  bf60def0faa970060bebab180315453daae00dd554b12de53052b55b94893f5c)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen-Image-GGUF" "8aa13c32cf6dda8ad5cb5e3a1beb93150faa246b" "qwen-image-Q4_K_M.gguf" 13127088672 "eb2d4719dda7c73c52c1685673d173f4c1407e78688c2869352cef3ef7ba3819"
    ;;
  684cc3900ad89ca3d4fa5ba0ee76aa3105e36a83eb565fd39dc21d9a6df6977d)
    prefer_download_hf_artifact "image-download" "$1" "Comfy-Org/Qwen-Image_ComfyUI" "7beb7b647f04469fbe64ba8adc2bb0d7e5e9f73f" "split_files/vae/qwen_image_vae.safetensors" 253806246 "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f"
    ;;
  337b325fce8cb552dc0d51e0880ac386e5d680b23cb06422435312a9873d2f62)
    prefer_download_hf_artifact "image-download" "$1" "mradermacher/Qwen2.5-VL-7B-Instruct-GGUF" "cfa2baa09946b211c107e6e104948987a64dd2c1" "Qwen2.5-VL-7B-Instruct.Q4_K_M.gguf" 4683072512 "0f00a930ba3108b6861ddadf74d8ebbd82e257c63eba728e62c3e8970f5eed94"
    ;;
  a502d3ada226288d058b4cfec0aca45f456b20f61695fdb933712fe83633fb6c)
    prefer_download_hf_artifact "image-download" "$1" "QuantStack/Qwen-Image-GGUF" "257f261fa92593bed760aa6fa3f7921a49fea00f" "Qwen_Image-Q6_K.gguf" 16824990240 "0c60643ee869161ee7acd530f7faf1cb2361f131e1ebae27b95fdc481b6df2b2"
    ;;
  9f951bc71a8f27960fb74b41752b2ed0fceeef18f08ec2c2a2bdade9bc0143d5)
    prefer_download_hf_artifact "image-download" "$1" "Comfy-Org/Qwen-Image_ComfyUI" "b8f0a47470ec2a0724d6267ca696235e441baa5d" "split_files/text_encoders/qwen_2.5_vl_7b.safetensors" 16584415576 "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a"
    ;;
  1ebfe982684a301826b735b09cfcb7e7ae387bc8cf9d422fee426bf45a2f446c)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen-Image-GGUF" "8aa13c32cf6dda8ad5cb5e3a1beb93150faa246b" "qwen-image-Q8_0.gguf" 21761817120 "43142b32778dc0568c27395abc6f8291ac53f1de0b98eed919712cf161f248de"
    ;;
  ac2728487ff2918bac75ee1c62c0fd974cdece6bd502faefc3989c050c234678)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen-Image-Edit-2511-GGUF" "0d33d9692b4b26212297240d87b0d4719aa4fd06" "qwen-image-edit-2511-Q4_K_M.gguf" 13244758624 "8677bac90627adbbc11efab87b1870e701c4eb3689ee865a3de8ab81b705a723"
    ;;
  947ebf8d6870ad91d0c511caefab3f90b492077a01f5f2d8e334e2f5f8248295)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen-Image-Edit-2511-GGUF" "0d33d9692b4b26212297240d87b0d4719aa4fd06" "qwen-image-edit-2511-Q6_K.gguf" 16852417120 "fdc28e5b8f7d9cfe0399fd1700c375f25f000fc4159bbdb0d4a809ae898eb759"
    ;;
  d6a2d371ee99322045f393ca3139ba9e5cc794efa3276db4c3918b01ebbd1ba5)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen-Image-Edit-2511-GGUF" "0d33d9692b4b26212297240d87b0d4719aa4fd06" "qwen-image-edit-2511-Q8_0.gguf" 21761817184 "ab4f0622fb002fccaaa679a2ecce6fd1b3190d8ea28a5b7b2b17b8669bc24afa"
    ;;
  a9c4f3a30836c7c2c884f2e3dde4baa508630a610060b601b92e0eb1489a20d2)
    prefer_download_hf_artifact "image-download" "$1" "stabilityai/stable-diffusion-xl-base-1.0" "462165984030d82259a11f4367a4eed129e94a7b" "sd_xl_base_1.0.safetensors" 6938078334 "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b"
    ;;
  3724203525019941ed98882738819c5ec584b1afc8365cbbe8f035aa6e7cdc1c)
    prefer_download_hf_artifact "image-download" "$1" "leejet/Z-Image-Turbo-GGUF" "c61c0e422dc8b541b7548cf33a4ef8302b0f8085" "z_image_turbo-Q4_K.gguf" 3864250304 "14b375ab4f226bc5378f68f37e899ef3c2242b8541e61e2bc1aff40976086fbd"
    ;;
  31a793bd611bfa467570c448d3ff7bc0375910cad989d831225c73acf3bd20e7)
    prefer_download_hf_artifact "image-download" "$1" "black-forest-labs/FLUX.1-schnell" "741f7c3ce8b383c54771c7003378a50191e9efe9" "ae.safetensors" 335304388 "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38"
    ;;
  b719a79fbdae383139a34765ea67544f968c151943e90d2cc81e0eb39c5ed4b9)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen3-4B-Instruct-2507-GGUF" "a06e946bb6b655725eafa393f4a9745d460374c9" "Qwen3-4B-Instruct-2507-Q4_K_M.gguf" 2497281120 "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
    ;;
  04616f33385eb60de990bd2e0e5895f1e32c1f8e7426b18abc1e7c1d54bb0c24)
    prefer_download_hf_artifact "image-download" "$1" "leejet/Z-Image-Turbo-GGUF" "c61c0e422dc8b541b7548cf33a4ef8302b0f8085" "z_image_turbo-Q6_K.gguf" 5263239104 "319f627beac8059b7546f36a7b4d5097b7f4ee6a1fc37585d0f75ca1d12d01af"
    ;;
  8470d08965457ec86390102406e1dd3abf4958e562f60352a25f12b9c791687c)
    prefer_download_hf_artifact "image-download" "$1" "leejet/Z-Image-Turbo-GGUF" "c61c0e422dc8b541b7548cf33a4ef8302b0f8085" "z_image_turbo-Q8_0.gguf" 6577440704 "df1c5baa86d1398c979495a6072dbcee79444fdb884a2445582ba0769c44e9a1"
    ;;
  768de660218e86a55540d8463b08f716891a80052e804da1dac9ef5e066e5162)
    prefer_download_hf_artifact "image-download" "$1" "unsloth/Qwen3-4B-Instruct-2507-GGUF" "a06e946bb6b655725eafa393f4a9745d460374c9" "Qwen3-4B-Instruct-2507-Q8_0.gguf" 4280405600 "391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068"
    ;;
    *) echo "[image-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

image_download_model_keys() {
  prefer_download_model_keys     "image-download" "${IMAGE_DOWNLOAD_JOBS:-4}" 8     image_model_artifact_ids image_download_artifact_id "$@"
}

image_download_model_key() {
  image_download_model_keys "$1"
}
