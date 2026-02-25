
name: Daily Deal Digest

on:
  schedule:
    - cron: "0 23 * * 1-5"
  workflow_dispatch:

jobs:
  run-digest:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install anthropic

      - name: Run daily digest
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python digest.py
