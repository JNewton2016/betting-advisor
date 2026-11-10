from feature_eng import build_dataset
from odds_helpers import odds_to_proba, normalise_result_proba, normalise_ou_proba

from sklearn.metrics import log_loss, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

import pandas as pd
import numpy as np

usable, feature_cols = build_dataset()

#==================
# Train/Test Split
#==================

train_end = "2024-08-01"
test_start = "2026-08-01"

train = usable[usable["match_date"] < train_end] #2015/16-2023/24
validate = usable[(usable["match_date"] >= train_end) & (usable["match_date"] < test_start)] #2024/25-2025/26
test = usable[usable["match_date"] >= test_start] #2026/27-


#====================
# Brier Score Loss
#====================

classes = ["A", "D", "H"]

def evaluate(y_labels, proba):
    y_onehot = pd.get_dummies(y_labels).reindex(columns=classes, fill_value=0).values.astype(float)
    brier = np.mean(np.sum((proba - y_onehot) ** 2, axis=1))
    logloss = log_loss(y_labels, proba, labels=classes)
    acc = accuracy_score(y_labels, np.array(classes)[proba.argmax(axis=1)])

    return brier, logloss, acc

## naive baseline - predict training-set proportions for each clas  s(match)
props = train["result"].value_counts(normalize=True).reindex(classes).values
baseline = np.tile(props, (len(validate), 1))

brier, logloss, acc = evaluate(validate["result"], baseline)
print(f"Baseline: Brier {brier:.4f}  LogLoss {logloss:.4f}  Acc {acc:.4f}")


#======================
# Logistic Regression Model
#======================

logreg = LogisticRegression(max_iter=1000)

model = Pipeline([
    ("scaler", StandardScaler()),
    ("logreg", logreg)
])

model.fit(train[feature_cols], train["result"])

y_proba = model.predict_proba(validate[feature_cols])

brier, logloss, acc = evaluate(validate["result"], y_proba)
print(f"Logistic: Brier {brier:.4f}  LogLoss {logloss:.4f}  Acc {acc:.4f}")