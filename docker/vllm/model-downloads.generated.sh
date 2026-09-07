#!/usr/bin/env bash
set -euo pipefail

readonly VLLM_GENERATED_MODEL_KEYS="qwen3.8-27b-nvfp4"
GENERATED_MODEL_KEYS=$VLLM_GENERATED_MODEL_KEYS
LEGACY_SMALL_MODELS=$VLLM_GENERATED_MODEL_KEYS

vllm_model_key_artifact_ids() {
  case "$1" in
  qwen3.8-27b-nvfp4) printf '%s\n' "0ca4bce17072e379f4d3319bd6606ff68f83cbdec2a53ec8746759c9b5aa82c7" "3cccae3749a3111131d10f35761c8b29b766c84e32a162fa2a11cfb223dda41b" "baedc776433cdcf64d1b88eb1d6179afdc873d1cd5542434dd8347fca7abe500" "0271fe18c8896629ec57f42d99ef448922317b4aa1f4cbfd3ba373ad70d8ac9a" "db29370ee38aa771d69dfe497c6f9aaef8f8e54162e905074ba3a13711d4e818" "28091425408b16d627a47d477ecb3711b6fd6b13288515d1e26522e78496a639" "142422a38913002d8c83b1f69d647f65537d2cd0a145431d58827dafbcfd20cc" "e037f2ba7e064bb94d574f2a4ec38c9353e5dab466ab7bc06410689d70340269" "63b8b2ccc62729adf12500bb35b84359ae4acc1a635c2b61161e4783d76753ce" "5994602ea711246dc2f6eb935971c72e40b4e3a3595894482c01378a717ff1c8" "79f2e9cdcbeb01584d508bd39368fc0277c4e831722f384631ee9e1b1016340c" "060d1e081c643a843700c8fec5167257a6aa33fa28ebbd71672b0dcda7b19932" "d636c697dfe3c43183c1b18933a86bb3a4272f78d71eed5e09156657ddbb52e9" "33fff47156a41856a2fe6575a3c70300e4829e0cb104edbb06e2276c893e9e4a" "46e6c5c98fee4733533023108b2cd3306ad3feda506cc0f13daec952ad6e3e16" "07c0e972890576269c9e7e01cac8db58336f0e7629cb980bdb4501f03631b9c0" "a44df7f24f30313218250dbfe7a94312e1acdda929de69bceb7175d6e7a1ff81" "ed505c6d048a82afe827a653d16a2fa6058360e5830abd6c9a9c43cc5b946ddc" "d47cd90a8a56595e846019c737366c7737f010a17e1f8dc851c1b235a3505d2a" ;;
    *) echo "[vllm-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

vllm_download_artifact_id() {
  case "$1" in
  0ca4bce17072e379f4d3319bd6606ff68f83cbdec2a53ec8746759c9b5aa82c7)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "LICENSE" 11343 "50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32"
    ;;
  3cccae3749a3111131d10f35761c8b29b766c84e32a162fa2a11cfb223dda41b)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "chat_template.jinja" 8952 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041"
    ;;
  baedc776433cdcf64d1b88eb1d6179afdc873d1cd5542434dd8347fca7abe500)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "config.json" 19252 "267be2125ee2ec272555748c87cc636b25a96107946f05491bd6043151c7fe4e"
    ;;
  0271fe18c8896629ec57f42d99ef448922317b4aa1f4cbfd3ba373ad70d8ac9a)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "generation_config.json" 214 "d0dbf670c6a372817b2ff92d5d47e3130d35de9c3a7164ba455fd7a88255b362"
    ;;
  db29370ee38aa771d69dfe497c6f9aaef8f8e54162e905074ba3a13711d4e818)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "hf_quant_config.json" 15113 "0c1004d622f835eef17ba193d8e966ecfd2d5218cbc8d25b7effff8cb4011893"
    ;;
  28091425408b16d627a47d477ecb3711b6fd6b13288515d1e26522e78496a639)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "merges.txt" 3353259 "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d"
    ;;
  142422a38913002d8c83b1f69d647f65537d2cd0a145431d58827dafbcfd20cc)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model-00001-of-00006.safetensors" 4013662656 "4b71c5d9d5027c88d1df9f53b93ad77b8d5e428d5d6f75ae42063704d94930b9"
    ;;
  e037f2ba7e064bb94d574f2a4ec38c9353e5dab466ab7bc06410689d70340269)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model-00002-of-00006.safetensors" 4104675536 "d0ceb042ef003ec63e00203823eb70d4815c9fc0430ba04a5442b6b8bde19093"
    ;;
  63b8b2ccc62729adf12500bb35b84359ae4acc1a635c2b61161e4783d76753ce)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model-00003-of-00006.safetensors" 4028901296 "b633a26c1d3b97bf061585363b99d4c01650b4e3f6d0cbb18e7c7e03ca2de1e4"
    ;;
  5994602ea711246dc2f6eb935971c72e40b4e3a3595894482c01378a717ff1c8)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model-00004-of-00006.safetensors" 4003421984 "485ea312626e2d1f3a820d9f7545809cef1e2e77414e3977a61d32dacd370bd0"
    ;;
  79f2e9cdcbeb01584d508bd39368fc0277c4e831722f384631ee9e1b1016340c)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model-00005-of-00006.safetensors" 4000515080 "2aa61bab1ed252fe3cdb479286b5b7add7e8ad567501add5f6eeef3987b03d31"
    ;;
  060d1e081c643a843700c8fec5167257a6aa33fa28ebbd71672b0dcda7b19932)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model-00006-of-00006.safetensors" 5380672368 "8214cd21a46832380c06be552c42d9514c6cc9f27d98e09e2a09e36a8bd6e6ce"
    ;;
  d636c697dfe3c43183c1b18933a86bb3a4272f78d71eed5e09156657ddbb52e9)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "model.safetensors.index.json" 205647 "f9ba0436d933e2362fb1bfa0508931c28b68f1fddbd5b94e6d50712e36a0636c"
    ;;
  33fff47156a41856a2fe6575a3c70300e4829e0cb104edbb06e2276c893e9e4a)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "nvfp4_experts_mtp.safetensors" 849400392 "c2b7cb6987e40f13b1ab6e552958afe47a759f86cac0c3c4a1c29f606dc080ef"
    ;;
  46e6c5c98fee4733533023108b2cd3306ad3feda506cc0f13daec952ad6e3e16)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
    ;;
  07c0e972890576269c9e7e01cac8db58336f0e7629cb980bdb4501f03631b9c0)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "tokenizer.json" 12809320 "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
    ;;
  a44df7f24f30313218250dbfe7a94312e1acdda929de69bceb7175d6e7a1ff81)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "tokenizer_config.json" 17927 "5a205aa76328f59df93a9091d0496aeda4615c6b0c495cbd37e14c79c0cd0f94"
    ;;
  ed505c6d048a82afe827a653d16a2fa6058360e5830abd6c9a9c43cc5b946ddc)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ;;
  d47cd90a8a56595e846019c737366c7737f010a17e1f8dc851c1b235a3505d2a)
    prefer_download_hf_artifact "vllm-download" "$1" "Inferact/Qwen3.8-27B-NVFP4" "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462" "vocab.json" 6722759 "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003"
    ;;
    *) echo "[vllm-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

vllm_download_artifact_id_s3() {
  case "$1" in
  0ca4bce17072e379f4d3319bd6606ff68f83cbdec2a53ec8746759c9b5aa82c7)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "LICENSE" 11343 "50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  3cccae3749a3111131d10f35761c8b29b766c84e32a162fa2a11cfb223dda41b)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "chat_template.jinja" 8952 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  baedc776433cdcf64d1b88eb1d6179afdc873d1cd5542434dd8347fca7abe500)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "config.json" 19252 "267be2125ee2ec272555748c87cc636b25a96107946f05491bd6043151c7fe4e" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  0271fe18c8896629ec57f42d99ef448922317b4aa1f4cbfd3ba373ad70d8ac9a)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "generation_config.json" 214 "d0dbf670c6a372817b2ff92d5d47e3130d35de9c3a7164ba455fd7a88255b362" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  db29370ee38aa771d69dfe497c6f9aaef8f8e54162e905074ba3a13711d4e818)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "hf_quant_config.json" 15113 "0c1004d622f835eef17ba193d8e966ecfd2d5218cbc8d25b7effff8cb4011893" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  28091425408b16d627a47d477ecb3711b6fd6b13288515d1e26522e78496a639)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "merges.txt" 3353259 "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  142422a38913002d8c83b1f69d647f65537d2cd0a145431d58827dafbcfd20cc)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model-00001-of-00006.safetensors" 4013662656 "4b71c5d9d5027c88d1df9f53b93ad77b8d5e428d5d6f75ae42063704d94930b9" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  e037f2ba7e064bb94d574f2a4ec38c9353e5dab466ab7bc06410689d70340269)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model-00002-of-00006.safetensors" 4104675536 "d0ceb042ef003ec63e00203823eb70d4815c9fc0430ba04a5442b6b8bde19093" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  63b8b2ccc62729adf12500bb35b84359ae4acc1a635c2b61161e4783d76753ce)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model-00003-of-00006.safetensors" 4028901296 "b633a26c1d3b97bf061585363b99d4c01650b4e3f6d0cbb18e7c7e03ca2de1e4" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  5994602ea711246dc2f6eb935971c72e40b4e3a3595894482c01378a717ff1c8)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model-00004-of-00006.safetensors" 4003421984 "485ea312626e2d1f3a820d9f7545809cef1e2e77414e3977a61d32dacd370bd0" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  79f2e9cdcbeb01584d508bd39368fc0277c4e831722f384631ee9e1b1016340c)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model-00005-of-00006.safetensors" 4000515080 "2aa61bab1ed252fe3cdb479286b5b7add7e8ad567501add5f6eeef3987b03d31" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  060d1e081c643a843700c8fec5167257a6aa33fa28ebbd71672b0dcda7b19932)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model-00006-of-00006.safetensors" 5380672368 "8214cd21a46832380c06be552c42d9514c6cc9f27d98e09e2a09e36a8bd6e6ce" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  d636c697dfe3c43183c1b18933a86bb3a4272f78d71eed5e09156657ddbb52e9)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "model.safetensors.index.json" 205647 "f9ba0436d933e2362fb1bfa0508931c28b68f1fddbd5b94e6d50712e36a0636c" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  33fff47156a41856a2fe6575a3c70300e4829e0cb104edbb06e2276c893e9e4a)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "nvfp4_experts_mtp.safetensors" 849400392 "c2b7cb6987e40f13b1ab6e552958afe47a759f86cac0c3c4a1c29f606dc080ef" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  46e6c5c98fee4733533023108b2cd3306ad3feda506cc0f13daec952ad6e3e16)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "preprocessor_config.json" 390 "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  07c0e972890576269c9e7e01cac8db58336f0e7629cb980bdb4501f03631b9c0)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "tokenizer.json" 12809320 "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  a44df7f24f30313218250dbfe7a94312e1acdda929de69bceb7175d6e7a1ff81)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "tokenizer_config.json" 17927 "5a205aa76328f59df93a9091d0496aeda4615c6b0c495cbd37e14c79c0cd0f94" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  ed505c6d048a82afe827a653d16a2fa6058360e5830abd6c9a9c43cc5b946ddc)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "video_preprocessor_config.json" 385 "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
  d47cd90a8a56595e846019c737366c7737f010a17e1f8dc851c1b235a3505d2a)
    prefer_download_s3_artifact "vllm-s3" "$1" "Inferact/Qwen3.8-27B-NVFP4" "vocab.json" 6722759 "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003" "$VLLM_S3_BUCKET_NAME" "${VLLM_S3_MODEL_PREFIX:-}"
    ;;
    *) echo "[vllm-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}

vllm_s3_stage_artifact() {
  local artifact_id="$1"
  local status=0
  if vllm_download_artifact_id_s3 "$artifact_id"; then return 0; else status=$?; fi
  echo "[vllm-download] artifact $artifact_id: S3 unavailable or invalid (status $status); falling back to Hugging Face" >&2
  vllm_download_artifact_id "$artifact_id"
}

vllm_download_model_keys() {
  prefer_download_model_keys \
    "vllm-download" "${VLLM_DOWNLOAD_JOBS:-4}" 8 \
    vllm_model_key_artifact_ids vllm_download_artifact_id "$@"
}

vllm_download_model_keys_s3() {
  prefer_download_model_keys \
    "vllm-s3-download" "${VLLM_DOWNLOAD_JOBS:-4}" 8 \
    vllm_model_key_artifact_ids vllm_s3_stage_artifact "$@"
}

vllm_download_model_key() { vllm_download_model_keys "$1"; }
download_model_key() { vllm_download_model_key "$1"; }
