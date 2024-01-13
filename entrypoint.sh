#!/bin/bash

export OPENAI_API_KEY="$1"
export OPENAI_MODEL="$2"
export OPENAI_TEMPERATURE="$3"
export OPENAI_MAX_TOKENS="$4"
export OPENAI_DEFAULT_CRITERIA="$5"
export OPENAI_EXTRA_CRITERIA="$5"
export OPENAI_PROMPT="$5"
export OPENAI_PROMPT_FOOTER="$5"
export GITHUB_TOKEN="$6"
export GITHUB_PR_ID="$7"

python /main.py
