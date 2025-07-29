export HF_ENDPOINT=https://hf-mirror.com

MODEL_NAME=$1
# huggingface-cli download --resume-download $MODEL_NAME
hf download $MODEL_NAME