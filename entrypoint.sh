#!/bin/bash

export OPENAI_API_KEY="$1"
export OPENAI_MODEL="$2"
export OPENAI_TEMPERATURE="$3"
export OPENAI_MAX_TOKENS="$4"
export OPENAI_RULES_JSON_ARRAY="$5"
export OPENAI_PROMPT_EXTRAS="$5"
export OPENAI_PROMPT_FOOTER="$5"
export GITHUB_TOKEN="$6"
export GITHUB_PR_ID="$7"

python /main.py
