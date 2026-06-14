import os
import json
import numpy as np
import logging
from sklearn.metrics import accuracy_score, f1_score

logger = logging.getLogger(__name__)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, predictions)
    f1 = f1_score(labels, predictions, average="binary")
    return {"accuracy": acc, "f1": f1}

def train():
    try:
        from datasets import load_dataset
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
    except ImportError as e:
        logger.error(f"Failed to import ML packages: {e}")
        write_error_metrics(f"Missing packages: {str(e)}")
        return
        
    print("Loading LIAR dataset from HuggingFace...")
    try:
        dataset = load_dataset("liar")
    except Exception as e:
        logger.error(f"Failed to download LIAR dataset: {e}")
        write_error_metrics(f"Failed to download dataset: {str(e)}")
        return
        
    features = dataset["train"].features
    label_names = features["label"].names if "label" in features and hasattr(features["label"], "names") else None
    print(f"LIAR dataset labels: {label_names}")
    
    print("Loading distilbert-base-uncased tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    except Exception as e:
        logger.error(f"Failed to load tokenizer: {e}")
        write_error_metrics(f"Failed to load tokenizer: {str(e)}")
        return

    def preprocess_function(examples):
        binary_labels = []
        for l in examples["label"]:
            if label_names:
                name = label_names[l]
                # pants-fire, false, barely-true -> label 1 (misleading)
                # half-true, mostly-true, true -> label 0 (credible)
                if name in ["pants-fire", "false", "barely-true"]:
                    binary_labels.append(1)
                else:
                    binary_labels.append(0)
            else:
                # Fallback to index mapping (0: false, 3: pants-fire, 4: barely-true)
                if l in [0, 3, 4]:
                    binary_labels.append(1)
                else:
                    binary_labels.append(0)
        
        tokenized = tokenizer(examples["statement"], truncation=True, max_length=128)
        tokenized["label"] = binary_labels
        return tokenized

    print("Preprocessing dataset...")
    encoded_dataset = dataset.map(preprocess_function, batched=True, remove_columns=dataset["train"].column_names)
    
    print("Loading pre-trained DistilBERT model...")
    try:
        model = AutoModelForSequenceClassification.from_pretrained("distilbert-base-uncased", num_labels=2)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        write_error_metrics(f"Failed to load base model: {str(e)}")
        return
        
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
    model_dir = os.path.join(output_dir, "truthlens_distilbert")
    os.makedirs(output_dir, exist_ok=True)
    
    training_args = TrainingArguments(
        output_dir=os.path.join(output_dir, "results"),
        num_train_epochs=2,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=100,
        learning_rate=2e-5,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        disable_tqdm=True
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=encoded_dataset["train"],
        eval_dataset=encoded_dataset["validation"],
        compute_metrics=compute_metrics,
    )
    
    print("Fine-tuning model on LIAR dataset (CPU execution)...")
    trainer.train()
    
    print("Evaluating model...")
    eval_results = trainer.evaluate(encoded_dataset["test"])
    print(f"Eval results: {eval_results}")
    
    print(f"Saving fine-tuned model to {model_dir}...")
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)
    
    metrics = {
        "accuracy": eval_results.get("eval_accuracy", 0.0),
        "f1": eval_results.get("eval_f1", 0.0),
        "epochs": 2,
        "dataset": "LIAR (collapsed binary)",
        "base_model": "distilbert-base-uncased"
    }
    
    metrics_path = os.path.join(output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print("Training finished successfully.")

def write_error_metrics(err_msg: str):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
    os.makedirs(output_dir, exist_ok=True)
    metrics_path = os.path.join(output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "accuracy": 0.0,
            "f1": 0.0,
            "error": err_msg,
            "note": "Training skipped or failed. Fallbacks active."
        }, f, indent=2)

if __name__ == "__main__":
    train()
