"""
training.py — QLoRA fine-tuning pipeline for dispute classifier
C4 Spec Section 12
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# QLoRAConfig
# ---------------------------------------------------------------------------

@dataclass
class QLoRAConfig:
    """
    Configuration for QLoRA fine-tuning of the dispute classifier.

    Defaults follow best-practice recommendations for Mistral-7B with
    4-bit quantisation and LoRA rank 16.
    """
    base_model_name: str = "mistralai/Mistral-7B-v0.1"
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    load_in_4bit: bool = True
    target_modules: list = field(
        default_factory=lambda: ["q_proj", "v_proj"]
    )
    n_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-4
    max_seq_length: int = 512


# ---------------------------------------------------------------------------
# QLoRATrainer
# ---------------------------------------------------------------------------

class QLoRATrainer:
    """
    QLoRA fine-tuning pipeline for the C4 dispute classifier.

    Wraps the ``transformers`` + ``peft`` training loop.  When those
    libraries are unavailable (CPU-only CI, unit tests) the trainer logs
    each pipeline step and returns mock metrics, allowing the rest of the
    codebase to import and test without GPU dependencies.
    """

    def __init__(self, config: Optional[QLoRAConfig] = None) -> None:
        """
        Args:
            config: Training configuration.  Defaults to
                    :class:`QLoRAConfig` with stock values when ``None``.
        """
        self.config = config if config is not None else QLoRAConfig()
        self._model = None
        self._tokenizer = None
        self._peft_available = self._check_peft_available()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_peft_available(self) -> bool:
        """Return True if both ``transformers`` and ``peft`` are importable."""
        try:
            import peft  # noqa: F401
            import transformers  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "transformers or peft not available — QLoRATrainer will "
                "return mock metrics without performing real training."
            )
            return False

    def _load_base_model(self):
        """
        Load the base model and tokenizer with 4-bit quantisation.

        Requires ``transformers``, ``peft``, and a CUDA-capable GPU.
        """
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        logger.info("Loading base model: %s", self.config.base_model_name)

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=self.config.load_in_4bit,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.base_model_name,
            use_fast=True,
        )
        self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model_name,
            quantization_config=quantization_config,
            device_map="auto",
        )
        logger.info("Base model loaded successfully.")

    def _apply_lora(self):
        """Attach LoRA adapters to the loaded base model."""
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        logger.info(
            "Applying LoRA: r=%d alpha=%d dropout=%.2f modules=%s",
            self.config.lora_r,
            self.config.lora_alpha,
            self.config.lora_dropout,
            self.config.target_modules,
        )
        self._model = prepare_model_for_kbit_training(self._model)
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=self.config.target_modules,
            bias="none",
            task_type="CAUSAL_LM",
        )
        self._model = get_peft_model(self._model, lora_config)
        self._model.print_trainable_parameters()

    def _tokenize_dataset(self, data: List[dict]):
        """
        Tokenize a list of formatted training records.

        Args:
            data: List of dicts with keys ``system``, ``user``, ``assistant``.

        Returns:
            A ``datasets.Dataset`` with ``input_ids``, ``attention_mask``,
            and ``labels`` columns.
        """
        from datasets import Dataset

        def _to_text(record: dict) -> str:
            return (
                f"<s>[INST] <<SYS>>\n{record['system']}\n<</SYS>>\n\n"
                f"{record['user']} [/INST] {record['assistant']} </s>"
            )

        texts = [_to_text(r) for r in data]
        tokenized = self._tokenizer(
            texts,
            truncation=True,
            max_length=self.config.max_seq_length,
            padding="max_length",
            return_tensors="pt",
        )
        tokenized["labels"] = tokenized["input_ids"].clone()
        return Dataset.from_dict(
            {
                "input_ids": tokenized["input_ids"].tolist(),
                "attention_mask": tokenized["attention_mask"].tolist(),
                "labels": tokenized["labels"].tolist(),
            }
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare_dataset(self, cases: List[dict]) -> List[dict]:
        """
        Format raw payment case records into LLM training records.

        Args:
            cases: List of dicts, each expected to have keys:
                   ``rejection_code``, ``narrative``, ``amount``,
                   ``currency``, ``counterparty``, ``dispute_class``
                   (the ground-truth label string).

        Returns:
            List of dicts with keys ``system``, ``user``, ``assistant``
            where ``assistant`` is the target class token.
        """
        # Import here to avoid circular dependency at module load time
        from .prompt import DisputePromptBuilder

        builder = DisputePromptBuilder()
        formatted: List[dict] = []

        for case in cases:
            prompt = builder.build(
                rejection_code=case.get("rejection_code", "N/A"),
                narrative=case.get("narrative", ""),
                amount=case.get("amount", ""),
                currency=case.get("currency", ""),
                counterparty=case.get("counterparty", ""),
                language=case.get("language", "EN"),
            )
            formatted.append(
                {
                    "system": prompt["system"],
                    "user": prompt["user"],
                    "assistant": case["dispute_class"],
                }
            )
        logger.info("Prepared %d training records.", len(formatted))
        return formatted

    def train(
        self,
        train_data: List[dict],
        val_data: List[dict],
    ) -> dict:
        """
        Run the QLoRA fine-tuning loop.

        If ``transformers``/``peft`` are unavailable, logs each step and
        returns mock metrics so that tests can exercise this code path on
        CPU without a GPU.

        Args:
            train_data: Training records from :meth:`prepare_dataset`.
            val_data:   Validation records from :meth:`prepare_dataset`.

        Returns:
            dict with keys ``train_loss``, ``val_loss``, ``epochs``,
            ``train_samples``, ``val_samples``.
        """
        logger.info(
            "Starting QLoRA training: model=%s r=%d epochs=%d lr=%.1e "
            "batch=%d train_samples=%d val_samples=%d",
            self.config.base_model_name,
            self.config.lora_r,
            self.config.n_epochs,
            self.config.learning_rate,
            self.config.batch_size,
            len(train_data),
            len(val_data),
        )

        if not self._peft_available:
            logger.warning("Returning mock training metrics (no GPU/peft available).")
            return {
                "train_loss": 0.42,
                "val_loss": 0.48,
                "epochs": self.config.n_epochs,
                "train_samples": len(train_data),
                "val_samples": len(val_data),
            }

        # --- Real training path ---
        from transformers import Trainer, TrainingArguments

        self._load_base_model()
        self._apply_lora()

        train_dataset = self._tokenize_dataset(train_data)
        val_dataset = self._tokenize_dataset(val_data)

        training_args = TrainingArguments(
            output_dir="./c4_qlora_output",
            num_train_epochs=self.config.n_epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            gradient_accumulation_steps=4,
            learning_rate=self.config.learning_rate,
            fp16=True,
            logging_steps=10,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            report_to="none",
        )

        trainer = Trainer(
            model=self._model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
        )

        train_result = trainer.train()
        eval_result = trainer.evaluate()

        logger.info(
            "Training complete: train_loss=%.4f val_loss=%.4f",
            train_result.training_loss,
            eval_result.get("eval_loss", float("nan")),
        )
        return {
            "train_loss": train_result.training_loss,
            "val_loss": eval_result.get("eval_loss", float("nan")),
            "epochs": self.config.n_epochs,
            "train_samples": len(train_data),
            "val_samples": len(val_data),
        }

    def evaluate(self, model, test_data: List[dict]) -> dict:
        """
        Evaluate a trained model on *test_data* and return classification
        metrics.

        When the real model is not available (mock mode) returns plausible
        mock metrics.

        Args:
            model:      A fine-tuned model object (as returned by the
                        ``transformers`` Trainer, or ``None`` for mock mode).
            test_data:  Test records from :meth:`prepare_dataset`.

        Returns:
            dict with keys:

            - ``accuracy``            (float): fraction correctly classified
            - ``false_negative_rate`` (float): fraction of dispute cases
              classified as NOT_DISPUTE
            - ``confusion_matrix``    (list of lists): 4×4 matrix with rows
              ordered [NOT_DISPUTE, DISPUTE_CONFIRMED, DISPUTE_POSSIBLE,
              NEGOTIATION]
        """
        _classes = [
            "NOT_DISPUTE",
            "DISPUTE_CONFIRMED",
            "DISPUTE_POSSIBLE",
            "NEGOTIATION",
        ]
        _class_index = {c: i for i, c in enumerate(_classes)}
        n = len(_classes)

        if model is None or not self._peft_available:
            logger.warning("Returning mock evaluation metrics (no model or peft available).")
            confusion_matrix = [[0] * n for _ in range(n)]
            for i in range(n):
                confusion_matrix[i][i] = 25  # perfect mock diagonal
            return {
                "accuracy": 0.91,
                "false_negative_rate": 0.03,
                "confusion_matrix": confusion_matrix,
            }

        # --- Real evaluation path ---
        correct = 0
        false_negatives = 0
        dispute_total = 0
        confusion_matrix = [[0] * n for _ in range(n)]

        for record in test_data:
            expected = record["assistant"]
            expected_idx = _class_index.get(expected, 0)

            inputs = self._tokenizer(
                f"<s>[INST] <<SYS>>\n{record['system']}\n<</SYS>>\n\n"
                f"{record['user']} [/INST]",
                return_tensors="pt",
            )
            import torch
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=10,
                    do_sample=False,
                )
            raw = self._tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
            ).strip().upper()

            predicted = raw if raw in _class_index else "DISPUTE_POSSIBLE"
            predicted_idx = _class_index.get(predicted, 2)

            confusion_matrix[expected_idx][predicted_idx] += 1
            if predicted == expected:
                correct += 1

            if expected in ("DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE"):
                dispute_total += 1
                if predicted == "NOT_DISPUTE":
                    false_negatives += 1

        total = len(test_data)
        accuracy = correct / total if total > 0 else 0.0
        fnr = false_negatives / dispute_total if dispute_total > 0 else 0.0

        return {
            "accuracy": accuracy,
            "false_negative_rate": fnr,
            "confusion_matrix": confusion_matrix,
        }
