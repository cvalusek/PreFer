#!/usr/bin/env bash
set -euo pipefail

readonly SGLANG_GENERATED_MODEL_KEYS="qwen3.8-27b-nvfp4"
GENERATED_MODEL_KEYS=$SGLANG_GENERATED_MODEL_KEYS
LEGACY_SMALL_MODELS=$SGLANG_GENERATED_MODEL_KEYS

model_key_fingerprint() {
  case "$1" in
  qwen3.8-27b-nvfp4) printf '%s\n' 0ce1f36e252e7cd623e9d7db41ddbcc29efc05b4eed83d1d682f10ea45295f3a ;;
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

model_key_artifacts() {
  case "$1" in
  qwen3.8-27b-nvfp4)
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/.gitattributes"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/.quant_summary.txt"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/LICENSE"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/README.md"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/chat_template.jinja"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/conversion-manifest.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/generation_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/hf_quant_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/merges.txt"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model-00001-of-00003.safetensors"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model-00002-of-00003.safetensors"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model-00003-of-00003.safetensors"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/model.safetensors.index.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/preprocessor_config.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/qualification-criteria.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/qualification.json"
      printf '%s\n' "RadixArk/Qwen3.8-27B-NVFP4/tensor-audit.json"
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
  qwen3.8-27b-nvfp4)
      printf '%s\t%s\n' 1570 "RadixArk/Qwen3.8-27B-NVFP4/.gitattributes"
      printf '%s\t%s\n' 314291 "RadixArk/Qwen3.8-27B-NVFP4/.quant_summary.txt"
      printf '%s\t%s\n' 11544 "RadixArk/Qwen3.8-27B-NVFP4/LICENSE"
      printf '%s\t%s\n' 4574 "RadixArk/Qwen3.8-27B-NVFP4/README.md"
      printf '%s\t%s\n' 8952 "RadixArk/Qwen3.8-27B-NVFP4/chat_template.jinja"
      printf '%s\t%s\n' 73003 "RadixArk/Qwen3.8-27B-NVFP4/config.json"
      printf '%s\t%s\n' 23587 "RadixArk/Qwen3.8-27B-NVFP4/conversion-manifest.json"
      printf '%s\t%s\n' 214 "RadixArk/Qwen3.8-27B-NVFP4/generation_config.json"
      printf '%s\t%s\n' 53749 "RadixArk/Qwen3.8-27B-NVFP4/hf_quant_config.json"
      printf '%s\t%s\n' 3353259 "RadixArk/Qwen3.8-27B-NVFP4/merges.txt"
      printf '%s\t%s\n' 9965652544 "RadixArk/Qwen3.8-27B-NVFP4/model-00001-of-00003.safetensors"
      printf '%s\t%s\n' 9985757064 "RadixArk/Qwen3.8-27B-NVFP4/model-00002-of-00003.safetensors"
      printf '%s\t%s\n' 1970287672 "RadixArk/Qwen3.8-27B-NVFP4/model-00003-of-00003.safetensors"
      printf '%s\t%s\n' 214866 "RadixArk/Qwen3.8-27B-NVFP4/model.safetensors.index.json"
      printf '%s\t%s\n' 390 "RadixArk/Qwen3.8-27B-NVFP4/preprocessor_config.json"
      printf '%s\t%s\n' 1145 "RadixArk/Qwen3.8-27B-NVFP4/qualification-criteria.json"
      printf '%s\t%s\n' 2717 "RadixArk/Qwen3.8-27B-NVFP4/qualification.json"
      printf '%s\t%s\n' 539 "RadixArk/Qwen3.8-27B-NVFP4/tensor-audit.json"
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
  qwen3.8-27b-nvfp4)
    printf '%s\n' "7730912859c10cda3ca68bae6dccbf7d20a4bb4d903a716ff03fe21825f713b7" "9fcf0e3d01dddeb0706cee411148baafecf6d838014603887e9853bf20ba99ab" "0df27f305811c8941e9c6d993da0de3e301e372a9d78fa2c757ea307655ac872" "fdeab13bd6cb362cd5ea348ef47485f5f2293b6af4addd400b80a48aeb3e1647" "1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4" "bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c" "f9749a4da39e1c3dc1433dbd28b6f6346575eb8438190a76628d90e7b728fdd8" "919d7ee15a0fadbddfc063ea3ab00cd3e40eff57da0e06367feb477d0dfd7c05" "3e6b53eec281228ca50a1417d3d768d33ee1d8578aeafb516fe50aa81401db7d" "e7e3e7f9a82fa7f51aabb6ade09bb28fa48f5d0c182c27058d4429e42c93435a" "93758408a062a258fd549c4e4ba9e28bfa2b045e2ab55cd6b27487fb01afc3db" "1b005625d88e08b27423395b98ec92f1bc2fcc747355bba89a8581f61e25757b" "68ad6bf748e17568538d93aa614efd5cd86ae3b458364276787fc87ae98aa167" "8a0d6be7fd2bcbb0483918329bc56b1ab010eb4e59d92332a4ebdd81ebfb226b" "ba5d8f1df983d9283c17076c60f2426e27f4917cfdd25e4e436826bdc563245c" "09d26ecac6b59b0885c1fcb494a6031690f16c9f21cdce8a43e3a1a6e522609c" "3c2618df1abcadf08501a56b79ac294b4d83bce17b57d1602a994635d5bcf4d1" "af8df8fb4997b9844e57f120f63408396d6852fc16472ff0fcd8542eaa94be8f" "3001036477fa91b75a2b38182de57581aa886607f24a1a4fddea200e1b4c291b" "f3c3ca7e0bd239424a4fea839b50a052e6727c3c89c8fefaa7d1811a94bcfa63" "d46158d901e1e5079969870d919555b038173ce4ef182146087ac682bc638785" "1d6ee74940f64d6aae63bf1f31e9f5c07fb279da96d73c9744736b58e4b96163"
    ;;
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}

sglang_download_artifact_id() {
  case "$1" in
  7730912859c10cda3ca68bae6dccbf7d20a4bb4d903a716ff03fe21825f713b7)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" ".gitattributes" 1570 "34448b82c17d60fec9b65b1f093c115ddbaadc04beb1b0140b6bfed2e012a930"
    ;;
  9fcf0e3d01dddeb0706cee411148baafecf6d838014603887e9853bf20ba99ab)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" ".quant_summary.txt" 314291 "5920198f1770fc91c0f8032108e6d861ce7e0ef196eca140c9681231d8d99967"
    ;;
  0df27f305811c8941e9c6d993da0de3e301e372a9d78fa2c757ea307655ac872)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "LICENSE" 11544 "bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a"
    ;;
  fdeab13bd6cb362cd5ea348ef47485f5f2293b6af4addd400b80a48aeb3e1647)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "README.md" 4574 "3cfd18e07422e6eff20fcdf8dcdb3c864976dcef0e1e0f2c3f8bf788603203c2"
    ;;
  1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "chat_template.jinja" 8952 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041"
    ;;
  bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "config.json" 73003 "7ff41ec6f96ad50efea3c92751cd261b63839d39936eb6e6ffc9066db8672740"
    ;;
  f9749a4da39e1c3dc1433dbd28b6f6346575eb8438190a76628d90e7b728fdd8)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "conversion-manifest.json" 23587 "c71e938cadabd25b2d6ec6b1bd15afecb618674cd8004cf1ecf04e28badbbf55"
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
  09d26ecac6b59b0885c1fcb494a6031690f16c9f21cdce8a43e3a1a6e522609c)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "qualification-criteria.json" 1145 "8e3b57367245354acb040a133e63df8eb1f4aef787e036156b944dfda217352a"
    ;;
  3c2618df1abcadf08501a56b79ac294b4d83bce17b57d1602a994635d5bcf4d1)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "qualification.json" 2717 "7be9d60606fc9590ca7b5717018e12050deaa6d7d93abb5e8cad0845240983a8"
    ;;
  af8df8fb4997b9844e57f120f63408396d6852fc16472ff0fcd8542eaa94be8f)
    prefer_download_hf_artifact "sglang-download" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "319f741cce68d7914884900c138a1fbb70a42f30" "tensor-audit.json" 539 "8a7801e2b46298432a129689879c9e4f8c69444e0b71b4c971470c2747794679"
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

sglang_s3_download_artifact_id() {
  if [ -z "${SGLANG_S3_BUCKET_NAME:-}" ]; then
    echo "[sglang-download] SGLANG_S3_BUCKET_NAME is required for S3 staging" >&2
    return 2
  fi
  case "$1" in
  7730912859c10cda3ca68bae6dccbf7d20a4bb4d903a716ff03fe21825f713b7)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" ".gitattributes" 1570 "34448b82c17d60fec9b65b1f093c115ddbaadc04beb1b0140b6bfed2e012a930" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  9fcf0e3d01dddeb0706cee411148baafecf6d838014603887e9853bf20ba99ab)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" ".quant_summary.txt" 314291 "5920198f1770fc91c0f8032108e6d861ce7e0ef196eca140c9681231d8d99967" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  0df27f305811c8941e9c6d993da0de3e301e372a9d78fa2c757ea307655ac872)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "LICENSE" 11544 "bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  fdeab13bd6cb362cd5ea348ef47485f5f2293b6af4addd400b80a48aeb3e1647)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "README.md" 4574 "3cfd18e07422e6eff20fcdf8dcdb3c864976dcef0e1e0f2c3f8bf788603203c2" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  1872540f100537b1a3934324582e5d9a5088aeed741a555bc27e960a482355a4)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "chat_template.jinja" 8952 "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  bd4d870488e327b76b72c88c8720083052627fbb0b93f1fa10ff858ebb155b2c)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "config.json" 73003 "7ff41ec6f96ad50efea3c92751cd261b63839d39936eb6e6ffc9066db8672740" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  f9749a4da39e1c3dc1433dbd28b6f6346575eb8438190a76628d90e7b728fdd8)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "conversion-manifest.json" 23587 "c71e938cadabd25b2d6ec6b1bd15afecb618674cd8004cf1ecf04e28badbbf55" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
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
  09d26ecac6b59b0885c1fcb494a6031690f16c9f21cdce8a43e3a1a6e522609c)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "qualification-criteria.json" 1145 "8e3b57367245354acb040a133e63df8eb1f4aef787e036156b944dfda217352a" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  3c2618df1abcadf08501a56b79ac294b4d83bce17b57d1602a994635d5bcf4d1)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "qualification.json" 2717 "7be9d60606fc9590ca7b5717018e12050deaa6d7d93abb5e8cad0845240983a8" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
    ;;
  af8df8fb4997b9844e57f120f63408396d6852fc16472ff0fcd8542eaa94be8f)
    prefer_download_s3_artifact "sglang-s3" "$1" "RadixArk/Qwen3.8-27B-NVFP4" "tensor-audit.json" 539 "8a7801e2b46298432a129689879c9e4f8c69444e0b71b4c971470c2747794679" "$SGLANG_S3_BUCKET_NAME" "${SGLANG_S3_MODEL_PREFIX:-}"
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
  prefer_download_model_keys \
    "sglang-download" "${SGLANG_DOWNLOAD_JOBS:-4}" 8 \
    sglang_model_artifact_ids sglang_download_artifact_id "$@"
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
