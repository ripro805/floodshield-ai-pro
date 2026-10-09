# Optional Hugging Face integration

FloodShield's flood, disease, LSTM, and U-Net models are currently loaded from local `.pkl`/`.keras` artifacts by `backend/app/models_loader.py`. They are **not** downloaded from Hugging Face.

Priority 3 adds an optional Hugging Face Inference API provider for chatbot text generation only:

- `HF_INFERENCE_API_URL`
- `HF_INFERENCE_TOKEN`

When configured, the chatbot tries Ollama first, then the Hugging Face endpoint, then Anthropic, then the grounded local fallback. Prediction models remain local and deterministic.

To host a prediction model on Hugging Face in the future, export a compatible inference wrapper and validate its feature order against `models/*_features.pkl` before switching traffic. Do not replace the current local loader without an accuracy/regression comparison.
